"""End-to-end delivery flow (spec section 14):
PO created -> Preparing -> shipped (partial + final) -> received -> Delivered automatically,
plus the discrepancy path and the rules that guard each step."""
from datetime import timedelta
from decimal import Decimal as D

from sqlalchemy import func, select

from app.core.config import today
from app.models import DiscrepancyType, EmailLog, Notification
from app.services.shipments import Line, find_mismatches
from tests.conftest import po_payload

TOMORROW = str(today() + timedelta(days=1))


# --------------------------------------------------------------------------- helpers
def new_po(client, world, vendor_id=None, number="PO-1"):
    res = client.post("/api/pos", json=po_payload(vendor_id or world.vendor_a_id, number), headers=world.purchasing)
    assert res.status_code == 201, res.text
    return res.json()


def acknowledge(client, world, po, headers=None, items=None):
    return client.post(f"/api/pos/{po['id']}/acknowledge", json={"items": items or []}, headers=headers or world.vendor_a)


def ship(client, world, po, quantities, headers=None, **extra):
    """quantities: {line_no: qty}"""
    ids = {i["line_no"]: i["id"] for i in po["items"]}
    body = {
        "courier": "DHL",
        "tracking_number": "TRK1",
        "expected_delivery_date": TOMORROW,
        "items": [{"po_item_id": ids[n], "quantity": q} for n, q in quantities.items()],
        **extra,
    }
    return client.post(f"/api/pos/{po['id']}/shipments", json=body, headers=headers or world.vendor_a)


def receive(client, world, shipment, lines=None, discrepancies=None):
    """lines: {po_item_id: (received, accepted, name)}; defaults to exactly what was shipped."""
    items = []
    for si in shipment["items"]:
        received, accepted, name = (lines or {}).get(
            si["po_item_id"], (si["quantity_shipped"], si["quantity_shipped"], si["item_name"])
        )
        items.append(
            {"po_item_id": si["po_item_id"], "item_name_entered": name, "quantity_received": received, "quantity_accepted": accepted}
        )
    return client.post(
        f"/api/shipments/{shipment['id']}/receive",
        json={"items": items, "discrepancies": discrepancies or []},
        headers=world.receiving,
    )


# --------------------------------------------------------------------------- happy path
def test_full_flow_partial_then_final_delivers_automatically(client, world, db):
    po = new_po(client, world)
    assert po["can_ship"] is False

    res = acknowledge(client, world, po)
    assert res.status_code == 200, res.text
    po = res.json()
    assert po["status"] == "PREPARING"
    assert po["locked"] is True and po["can_ship"] is True

    # Partial: 60 of 100 gloves, no wipes
    res = ship(client, world, po, {1: 60})
    assert res.status_code == 201, res.text
    po = res.json()
    first = po["shipments"][0]
    assert po["status"] == "ON_THE_WAY"
    assert first["shipment_no"] == "PO-1-S1" and first["is_partial"] is True

    # Receiving sees it as incoming
    incoming = client.get("/api/shipments", params={"status": "ON_THE_WAY"}, headers=world.receiving).json()
    assert [s["shipment_no"] for s in incoming["items"]] == ["PO-1-S1"]

    res = receive(client, world, first)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "DELIVERED"
    po = client.get(f"/api/pos/{po['id']}", headers=world.purchasing).json()
    assert po["status"] == "PARTIALLY_DELIVERED"
    assert po["items"][0]["quantity_outstanding"] == 40

    # Final shipment: the rest
    po = ship(client, world, po, {1: 40, 2: 2.5}).json()
    final = po["shipments"][1]
    assert final["is_partial"] is False
    assert po["status"] == "PARTIALLY_DELIVERED"  # still partial while the rest is on the way
    assert receive(client, world, final).status_code == 200

    po = client.get(f"/api/pos/{po['id']}", headers=world.vendor_a).json()
    assert po["status"] == "DELIVERED"
    assert po["can_ship"] is False
    statuses = [h["new_status"] for h in po["history"] if h["entity_type"] == "po"]
    assert statuses == ["ISSUED", "PREPARING", "ON_THE_WAY", "PARTIALLY_DELIVERED", "DELIVERED"]

    # Purchasing was notified along the way, and every notification was also (mock) emailed
    types = db.scalars(select(Notification.type)).all()
    assert {"po_acknowledged", "shipment_dispatched", "shipment_delivered", "po_delivered"} <= set(types)
    assert db.scalar(select(func.count()).select_from(EmailLog)) == len(types)

    # Delivered history stays visible to the vendor
    history = client.get("/api/pos", params={"state": "closed"}, headers=world.vendor_a).json()
    assert [p["po_number"] for p in history["items"]] == ["PO-1"]


def test_acknowledge_with_different_quantity_notifies_purchasing(client, world, db):
    po = new_po(client, world)
    item = po["items"][0]
    res = acknowledge(client, world, po, items=[{"po_item_id": item["id"], "confirmed_qty": 90}])
    po = res.json()
    assert po["items"][0]["vendor_confirmed_qty"] == 90
    assert po["items"][0]["quantity_ordered"] == 100  # the PO stays authoritative
    assert po["items"][1]["vendor_confirmed_name"] == "Wipes"
    assert db.scalar(select(Notification.type)) == "po_acknowledged_with_changes"
    assert "1 difference" in po["history"][-1]["note"]


# --------------------------------------------------------------------------- rules
def test_vendor_rules(client, world):
    po = new_po(client, world)
    assert ship(client, world, po, {1: 10}).status_code == 409  # must acknowledge first
    assert acknowledge(client, world, po, headers=world.vendor_b).status_code == 404  # not their PO
    assert acknowledge(client, world, po, headers=world.receiving).status_code == 403
    assert acknowledge(client, world, po, headers=world.purchasing).status_code == 403
    po = acknowledge(client, world, po).json()
    assert acknowledge(client, world, po).status_code == 409  # only once

    assert ship(client, world, po, {1: 101}).status_code == 400  # more than ordered
    assert ship(client, world, po, {1: 10}, headers=world.vendor_b).status_code == 404
    past = ship(client, world, po, {1: 10}, expected_delivery_date=str(today() - timedelta(days=1)))
    assert past.status_code == 400

    assert ship(client, world, po, {1: 70}).status_code == 201
    res = ship(client, world, po, {1: 31})  # only 30 left (70 in transit)
    assert res.status_code == 400
    assert "only 30 pair left" in res.json()["detail"]


def test_cancelled_po_cannot_be_acknowledged_or_shipped(client, world):
    po = new_po(client, world)
    client.post(f"/api/pos/{po['id']}/cancel", json={}, headers=world.purchasing)
    assert acknowledge(client, world, po).status_code == 409


def test_only_receiving_records_receipts(client, world):
    po = acknowledge(client, world, new_po(client, world)).json()
    shipment = ship(client, world, po, {1: 10}).json()["shipments"][0]
    for headers in (world.vendor_a, world.purchasing):
        res = client.post(f"/api/shipments/{shipment['id']}/receive", json={"items": []}, headers=headers)
        assert res.status_code == 403
    assert receive(client, world, shipment).status_code == 200
    assert receive(client, world, shipment).status_code == 409  # already received


def test_shipments_are_scoped_like_pos(client, world):
    po = acknowledge(client, world, new_po(client, world)).json()
    shipment = ship(client, world, po, {1: 10}).json()["shipments"][0]
    assert client.get(f"/api/shipments/{shipment['id']}", headers=world.vendor_b).status_code == 404
    assert client.get("/api/shipments", headers=world.vendor_b).json()["total"] == 0
    assert client.get("/api/shipments", headers=world.vendor_a).json()["total"] == 1
    # Receiving can now see the PO, because it has a shipment
    assert client.get(f"/api/pos/{po['id']}", headers=world.receiving).status_code == 200


# --------------------------------------------------------------------------- discrepancies
def test_mismatch_requires_a_discrepancy(client, world):
    po = acknowledge(client, world, new_po(client, world)).json()
    shipment = ship(client, world, po, {1: 50}).json()["shipments"][0]
    item_id = shipment["items"][0]["po_item_id"]

    res = receive(client, world, shipment, {item_id: (45, 45, "Gloves")})
    assert res.status_code == 422
    assert "5 pair short" in res.json()["detail"]


def test_damaged_goods_stay_outstanding_and_can_be_replaced(client, world, db):
    po = acknowledge(client, world, new_po(client, world)).json()
    shipment = ship(client, world, po, {1: 100, 2: 2.5}).json()["shipments"][0]
    gloves = shipment["items"][0]["po_item_id"]

    res = receive(
        client, world, shipment,
        {gloves: (100, 90, "Gloves")},
        discrepancies=[{"po_item_id": gloves, "type": "DAMAGED", "description": "10 pairs torn"}],
    )
    assert res.status_code == 200, res.text
    received = res.json()
    assert received["status"] == "DISCREPANCY"
    assert received["discrepancies"][0]["item_name"] == "Gloves"
    assert received["receipt"]["items"][0]["quantity_accepted"] == 90

    po = client.get(f"/api/pos/{po['id']}", headers=world.purchasing).json()
    assert po["status"] == "PARTIALLY_DELIVERED"
    assert po["has_open_discrepancy"] is True
    assert po["items"][0]["quantity_outstanding"] == 10
    assert client.get("/api/pos", params={"has_discrepancy": "true"}, headers=world.purchasing).json()["total"] == 1

    # Both Purchasing and the vendor hear about it
    assert set(db.scalars(select(Notification.type))) >= {"discrepancy_declared"}
    assert db.scalar(select(func.count()).select_from(Notification).where(Notification.type == "discrepancy_declared")) == 2

    # The replacement is just a new shipment for the outstanding 10
    replacement = ship(client, world, po, {1: 10}).json()["shipments"][1]
    assert receive(client, world, replacement).status_code == 200
    assert client.get(f"/api/pos/{po['id']}", headers=world.purchasing).json()["status"] == "DELIVERED"


def test_discrepancy_after_delivery(client, world):
    po = acknowledge(client, world, new_po(client, world)).json()
    shipment = ship(client, world, po, {1: 10}).json()["shipments"][0]
    body = {"type": "DAMAGED", "description": "Found torn after unpacking"}
    assert client.post(f"/api/shipments/{shipment['id']}/discrepancies", json=body, headers=world.receiving).status_code == 409
    receive(client, world, shipment)
    res = client.post(f"/api/shipments/{shipment['id']}/discrepancies", json=body, headers=world.receiving)
    assert res.status_code == 201
    assert res.json()["status"] == "DISCREPANCY"
    assert client.post(f"/api/shipments/{shipment['id']}/discrepancies", json=body, headers=world.vendor_a).status_code == 403


# --------------------------------------------------------------------------- mismatch rules (pure)
def line(**kw):
    base = dict(po_item_id=1, label="Line 1 (Gloves)", unit="pcs", shipped=D(10), received=D(10), accepted=D(10),
                entered_name="Gloves", expected_names=("Gloves", ""))
    return Line(**{**base, **kw})


def kinds(**kw):
    return [k for _, k, _ in find_mismatches([line(**kw)])]


def test_find_mismatches():
    assert kinds() == []
    assert kinds(entered_name="  gLoves ") == []  # case and spaces ignored
    assert kinds(entered_name="Glove box", expected_names=("Gloves", "Glove box")) == []  # vendor's confirmed name
    assert kinds(entered_name="Tape") == [DiscrepancyType.WRONG_ITEM]
    assert kinds(received=D(8), accepted=D(8)) == [DiscrepancyType.SHORT]
    assert kinds(received=D(12), accepted=D(12)) == [DiscrepancyType.EXCESS]
    assert kinds(accepted=D(7)) == [DiscrepancyType.DAMAGED]
    assert kinds(received=D(8), accepted=D(6)) == [DiscrepancyType.SHORT, DiscrepancyType.DAMAGED]
