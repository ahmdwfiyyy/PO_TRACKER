import pytest

from app.core.config import get_settings
from tests.test_flow import acknowledge, new_po, receive, ship

PDF = b"%PDF-1.4\n% test file\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def upload_dir(tmp_path, monkeypatch):
    """Keep test uploads out of the real uploads folder."""
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    return tmp_path


def upload(client, headers, entity_type, entity_id, content=PDF, name="DO-123.pdf"):
    return client.post(
        "/api/attachments",
        data={"entity_type": entity_type, "entity_id": str(entity_id)},
        files={"file": (name, content, "application/octet-stream")},
        headers=headers,
    )


@pytest.fixture
def shipment(client, world):
    po = acknowledge(client, world, new_po(client, world)).json()
    return ship(client, world, po, {1: 10}).json()["shipments"][0]


def test_vendor_uploads_do_and_only_allowed_users_download(client, world, shipment, upload_dir):
    res = upload(client, world.vendor_a, "shipment", shipment["id"])
    assert res.status_code == 201, res.text
    attachment = res.json()
    assert attachment["mime_type"] == "application/pdf"
    assert attachment["filename"] == "DO-123.pdf"
    # Stored under a generated name, never the user's
    stored = list(upload_dir.iterdir())
    assert len(stored) == 1 and stored[0].name != "DO-123.pdf"

    for headers in (world.vendor_a, world.purchasing, world.receiving):
        res = client.get(f"/api/attachments/{attachment['id']}", headers=headers)
        assert res.status_code == 200
        assert res.content == PDF
    assert client.get(f"/api/attachments/{attachment['id']}", headers=world.vendor_b).status_code == 404
    assert client.get(f"/api/attachments/{attachment['id']}").status_code == 401

    detail = client.get(f"/api/shipments/{shipment['id']}", headers=world.receiving).json()
    assert [a["filename"] for a in detail["attachments"]] == ["DO-123.pdf"]


def test_upload_rules(client, world, shipment, monkeypatch):
    # Wrong role for the target, and someone else's shipment
    assert upload(client, world.receiving, "shipment", shipment["id"]).status_code == 403
    assert upload(client, world.vendor_b, "shipment", shipment["id"]).status_code == 404
    assert upload(client, world.vendor_a, "shipment", 9999).status_code == 404
    # Content is checked, not the file name
    assert upload(client, world.vendor_a, "shipment", shipment["id"], b"MZ\x90\x00 not a pdf", "x.pdf").status_code == 400
    assert upload(client, world.vendor_a, "shipment", shipment["id"], b"", "x.pdf").status_code == 400
    # Path tricks in the name are stripped
    res = upload(client, world.vendor_a, "shipment", shipment["id"], PNG, "..\\..\\evil.png")
    assert res.status_code == 201 and res.json()["filename"] == "evil.png"
    # Size limit
    monkeypatch.setattr(get_settings(), "max_upload_mb", 0)
    assert upload(client, world.vendor_a, "shipment", shipment["id"]).status_code == 400


def test_receiving_photos_on_receipt_and_discrepancy(client, world, shipment):
    item = shipment["items"][0]["po_item_id"]
    received = receive(
        client, world, shipment, {item: (10, 8, "Gloves")},
        discrepancies=[{"po_item_id": item, "type": "DAMAGED", "description": "2 torn"}],
    ).json()
    assert upload(client, world.receiving, "receipt", received["receipt"]["id"], PNG, "dock.png").status_code == 201
    disc_id = received["discrepancies"][0]["id"]
    assert upload(client, world.receiving, "discrepancy", disc_id, PNG, "torn.png").status_code == 201
    assert upload(client, world.vendor_a, "discrepancy", disc_id, PNG, "x.png").status_code == 403

    detail = client.get(f"/api/shipments/{shipment['id']}", headers=world.vendor_a).json()
    assert [a["filename"] for a in detail["receipt"]["attachments"]] == ["dock.png"]
    assert [a["filename"] for a in detail["discrepancies"][0]["attachments"]] == ["torn.png"]
