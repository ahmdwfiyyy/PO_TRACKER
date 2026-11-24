from datetime import timedelta

from app.core.config import today
from app.db import utcnow
from app.models import PurchaseOrder
from tests.conftest import po_payload


def test_create_po(client, world):
    res = client.post("/api/pos", json=po_payload(world.vendor_a_id), headers=world.purchasing)
    assert res.status_code == 201, res.text
    po = res.json()
    assert po["status"] == "ISSUED"
    assert [i["line_no"] for i in po["items"]] == [1, 2]
    assert po["items"][1]["quantity_ordered"] == 2.5
    assert po["items"][0]["quantity_outstanding"] == 100
    assert po["created_by_name"] == "Pat Purchasing"
    assert po["locked"] is False
    # Creation is in the timeline
    assert [(h["old_status"], h["new_status"]) for h in po["history"]] == [(None, "ISSUED")]


def test_duplicate_po_number_is_rejected(client, world):
    client.post("/api/pos", json=po_payload(world.vendor_a_id, "PO-9"), headers=world.purchasing)
    res = client.post("/api/pos", json=po_payload(world.vendor_b_id, "po-9"), headers=world.purchasing)
    assert res.status_code == 409


def test_validation(client, world):
    bad_dates = po_payload(world.vendor_a_id, required_date="2026-10-01")
    assert client.post("/api/pos", json=bad_dates, headers=world.purchasing).status_code == 400
    no_items = po_payload(world.vendor_a_id, items=[])
    assert client.post("/api/pos", json=no_items, headers=world.purchasing).status_code == 422
    zero_qty = po_payload(world.vendor_a_id, items=[{"item_name": "X", "quantity_ordered": 0, "unit": "pcs"}])
    assert client.post("/api/pos", json=zero_qty, headers=world.purchasing).status_code == 422
    unknown_vendor = po_payload(9999)
    assert client.post("/api/pos", json=unknown_vendor, headers=world.purchasing).status_code == 404


def test_edit_items_before_acknowledgement(client, world):
    po = client.post("/api/pos", json=po_payload(world.vendor_a_id), headers=world.purchasing).json()
    items = [
        {"item_name": "Gloves XL", "quantity_ordered": 50, "unit": "pair"},
        {"item_name": "Wipes", "quantity_ordered": 3, "unit": "kg"},
        {"item_name": "Tape", "quantity_ordered": 10, "unit": "roll"},
    ]
    res = client.put(f"/api/pos/{po['id']}", json={"items": items, "notes": "updated"}, headers=world.purchasing)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [(i["line_no"], i["item_name"]) for i in body["items"]] == [(1, "Gloves XL"), (2, "Wipes"), (3, "Tape")]
    assert body["notes"] == "updated"

    res = client.put(f"/api/pos/{po['id']}", json={"items": items[:1]}, headers=world.purchasing)
    assert [i["item_name"] for i in res.json()["items"]] == ["Gloves XL"]


def test_acknowledged_po_only_allows_notes_and_dates(client, world, db):
    po = client.post("/api/pos", json=po_payload(world.vendor_a_id), headers=world.purchasing).json()
    db.get(PurchaseOrder, po["id"]).acknowledged_at = utcnow()
    db.commit()

    res = client.put(f"/api/pos/{po['id']}", json={"items": po_payload(1)["items"]}, headers=world.purchasing)
    assert res.status_code == 409
    res = client.put(f"/api/pos/{po['id']}", json={"vendor_id": world.vendor_b_id}, headers=world.purchasing)
    assert res.status_code == 409
    res = client.put(
        f"/api/pos/{po['id']}", json={"notes": "chase vendor", "required_date": "2026-12-20"}, headers=world.purchasing
    )
    assert res.status_code == 200
    assert res.json()["locked"] is True
    assert res.json()["required_date"] == "2026-12-20"


def test_cancel(client, world):
    po = client.post("/api/pos", json=po_payload(world.vendor_a_id), headers=world.purchasing).json()
    res = client.post(f"/api/pos/{po['id']}/cancel", json={"reason": "Ordered by mistake"}, headers=world.purchasing)
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "CANCELLED"
    assert body["history"][-1]["note"] == "Ordered by mistake"
    assert client.post(f"/api/pos/{po['id']}/cancel", json={}, headers=world.purchasing).status_code == 409
    assert client.put(f"/api/pos/{po['id']}", json={"notes": "x"}, headers=world.purchasing).status_code == 409


def test_search_and_filters(client, world):
    late = po_payload(
        world.vendor_a_id,
        "PO-LATE",
        issue_date=str(today() - timedelta(days=30)),
        required_date=str(today() - timedelta(days=1)),
    )
    client.post("/api/pos", json=late, headers=world.purchasing)
    other = po_payload(world.vendor_b_id, "PO-OK", items=[{"item_name": "Kapton tape", "quantity_ordered": 1, "unit": "roll"}])
    other["required_date"] = str(today() + timedelta(days=30))
    client.post("/api/pos", json=other, headers=world.purchasing)

    def numbers(**params):
        res = client.get("/api/pos", params=params, headers=world.purchasing)
        assert res.status_code == 200, res.text
        return sorted(p["po_number"] for p in res.json()["items"])

    assert numbers(q="kapton") == ["PO-OK"]  # by item name
    assert numbers(q="vendor a") == ["PO-LATE"]  # by vendor name
    assert numbers(q="late") == ["PO-LATE"]  # by PO number
    assert numbers(overdue="true") == ["PO-LATE"]
    assert numbers(overdue="false") == ["PO-OK"]
    assert numbers(vendor_id=world.vendor_b_id) == ["PO-OK"]
    assert numbers(status="ISSUED") == ["PO-LATE", "PO-OK"]
    assert numbers(has_discrepancy="true") == []
    assert numbers(state="closed") == []

    listed = client.get("/api/pos", headers=world.purchasing).json()["items"]
    late_row = next(p for p in listed if p["po_number"] == "PO-LATE")
    assert late_row["overdue"] is True
    assert late_row["item_summary"] == "Gloves, Wipes"


def test_vendor_and_user_management(client, world):
    res = client.post("/api/vendors", json={"name": "Vendor C", "email": "C@Example.com"}, headers=world.purchasing)
    assert res.status_code == 201
    vendor = res.json()
    assert vendor["email"] == "c@example.com"
    assert client.post("/api/vendors", json={"name": "vendor c"}, headers=world.purchasing).status_code == 409

    login_body = {"name": "Cat", "email": "c@test.com", "password": "Password123!", "role": "vendor", "vendor_id": vendor["id"]}
    assert client.post("/api/users", json=login_body, headers=world.purchasing).status_code == 201
    # Duplicate email, vendor login without a vendor, short password
    assert client.post("/api/users", json=login_body, headers=world.purchasing).status_code == 409
    no_vendor = {**login_body, "email": "d@test.com", "vendor_id": None}
    assert client.post("/api/users", json=no_vendor, headers=world.purchasing).status_code == 400
    short = {**login_body, "email": "e@test.com", "password": "short"}
    assert client.post("/api/users", json=short, headers=world.purchasing).status_code == 400

    vendors = {v["name"]: v for v in client.get("/api/vendors", headers=world.purchasing).json()}
    assert vendors["Vendor C"]["user_count"] == 1
