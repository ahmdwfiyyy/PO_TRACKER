"""Role checks and vendor isolation (spec section 14: vendor A cannot see vendor B's POs)."""
from tests.conftest import po_payload


def create(client, world, vendor_id, number):
    res = client.post("/api/pos", json=po_payload(vendor_id, number), headers=world.purchasing)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_vendor_sees_only_own_pos(client, world):
    a = create(client, world, world.vendor_a_id, "PO-A")
    b = create(client, world, world.vendor_b_id, "PO-B")

    listed = client.get("/api/pos", headers=world.vendor_a).json()
    assert [p["po_number"] for p in listed["items"]] == ["PO-A"]
    assert client.get(f"/api/pos/{a}", headers=world.vendor_a).status_code == 200
    # Another vendor's PO looks like it does not exist
    assert client.get(f"/api/pos/{b}", headers=world.vendor_a).status_code == 404
    assert client.get(f"/api/pos/{a}", headers=world.vendor_b).status_code == 404


def test_vendor_cannot_find_other_vendor_po_by_search(client, world):
    create(client, world, world.vendor_b_id, "PO-SECRET")
    res = client.get("/api/pos", params={"q": "SECRET"}, headers=world.vendor_a).json()
    assert res["total"] == 0


def test_purchasing_sees_all(client, world):
    create(client, world, world.vendor_a_id, "PO-A")
    create(client, world, world.vendor_b_id, "PO-B")
    assert client.get("/api/pos", headers=world.purchasing).json()["total"] == 2


def test_receiving_sees_no_po_until_it_has_a_shipment(client, world):
    po = create(client, world, world.vendor_a_id, "PO-A")
    assert client.get("/api/pos", headers=world.receiving).json()["total"] == 0
    assert client.get(f"/api/pos/{po}", headers=world.receiving).status_code == 404


def test_only_purchasing_manages_pos(client, world):
    payload = po_payload(world.vendor_a_id)
    for headers in (world.vendor_a, world.receiving):
        assert client.post("/api/pos", json=payload, headers=headers).status_code == 403
    po = create(client, world, world.vendor_a_id, "PO-A")
    assert client.put(f"/api/pos/{po}", json={"notes": "x"}, headers=world.vendor_a).status_code == 403
    assert client.post(f"/api/pos/{po}/cancel", json={}, headers=world.vendor_a).status_code == 403


def test_only_purchasing_manages_vendors_and_users(client, world):
    for headers in (world.vendor_a, world.receiving):
        assert client.get("/api/vendors", headers=headers).status_code == 403
        assert client.post("/api/vendors", json={"name": "X"}, headers=headers).status_code == 403
        assert client.get("/api/users", headers=headers).status_code == 403
        user = {"name": "X", "email": "x@test.com", "password": "Password123!", "role": "purchasing"}
        assert client.post("/api/users", json=user, headers=headers).status_code == 403


def test_anonymous_is_rejected(client, world):
    assert client.get("/api/pos").status_code == 401
    assert client.get("/api/vendors").status_code == 401
