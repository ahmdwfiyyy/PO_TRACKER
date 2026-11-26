"""Phase 3: notifications, discrepancy resolution, overdue alerts, dashboard."""
from datetime import timedelta

from sqlalchemy import func, select

from app.core.config import today
from app.models import Notification, PurchaseOrder, Shipment
from app.services.overdue import check_overdue
from tests.conftest import po_payload
from tests.test_flow import acknowledge, new_po, receive, ship


def damaged_po(client, world):
    """A PO whose single shipment was received with 2 damaged gloves (open discrepancy)."""
    po = acknowledge(client, world, new_po(client, world)).json()
    shipment = ship(client, world, po, {1: 100, 2: 2.5}).json()["shipments"][0]
    gloves = shipment["items"][0]["po_item_id"]
    received = receive(
        client, world, shipment, {gloves: (100, 98, "Gloves")},
        discrepancies=[{"po_item_id": gloves, "type": "DAMAGED", "description": "2 torn"}],
    ).json()
    return po, received


# --------------------------------------------------------------------------- notifications
def test_notifications_are_private_and_can_be_marked_read(client, world):
    acknowledge(client, world, new_po(client, world))

    mine = client.get("/api/notifications", headers=world.purchasing).json()
    assert mine["unread"] == 1
    note = mine["items"][0]
    assert note["type"] == "po_acknowledged" and note["link"] == "/pos/1"

    # Another user can neither see nor mark it
    assert client.get("/api/notifications", headers=world.vendor_b).json()["items"] == []
    assert client.post(f"/api/notifications/{note['id']}/read", headers=world.vendor_b).status_code == 404

    assert client.post(f"/api/notifications/{note['id']}/read", headers=world.purchasing).json()["is_read"] is True
    assert client.get("/api/notifications", headers=world.purchasing).json()["unread"] == 0


def test_mark_all_read(client, world):
    po, _ = damaged_po(client, world)
    assert client.get("/api/notifications", headers=world.purchasing).json()["unread"] > 1
    assert client.post("/api/notifications/read-all", headers=world.purchasing).status_code == 204
    assert client.get("/api/notifications", headers=world.purchasing).json()["unread"] == 0
    # The vendor's own notifications are untouched
    assert client.get("/api/notifications", headers=world.vendor_a).json()["unread"] > 0


# --------------------------------------------------------------------------- discrepancies
def test_resolve_discrepancy(client, world):
    po, received = damaged_po(client, world)
    disc = received["discrepancies"][0]

    listed = client.get("/api/discrepancies", params={"status": "OPEN"}, headers=world.purchasing).json()
    assert [(d["id"], d["po_number"], d["vendor"]["name"]) for d in listed] == [(disc["id"], "PO-1", "Vendor A")]
    assert client.get("/api/discrepancies", headers=world.vendor_b).json() == []  # not their PO
    assert len(client.get("/api/discrepancies", headers=world.vendor_a).json()) == 1

    body = {"resolution_note": "Vendor will send 2 replacements"}
    for headers in (world.vendor_a, world.receiving):
        assert client.post(f"/api/discrepancies/{disc['id']}/resolve", json=body, headers=headers).status_code == 403
    assert client.post(f"/api/discrepancies/{disc['id']}/resolve", json={"resolution_note": " "}, headers=world.purchasing).status_code == 422

    res = client.post(f"/api/discrepancies/{disc['id']}/resolve", json=body, headers=world.purchasing)
    assert res.status_code == 200, res.text
    resolved = res.json()
    assert resolved["status"] == "RESOLVED"
    assert resolved["resolved_by_name"] == "Pat Purchasing"
    assert resolved["shipment_status"] == "RESOLVED"
    assert client.post(f"/api/discrepancies/{disc['id']}/resolve", json=body, headers=world.purchasing).status_code == 409

    detail = client.get(f"/api/pos/{po['id']}", headers=world.purchasing).json()
    assert detail["has_open_discrepancy"] is False
    assert detail["items"][0]["quantity_outstanding"] == 2  # damaged qty still to be replaced
    assert any(h["new_status"] == "RESOLVED" for h in detail["history"])


def test_shipment_stays_in_discrepancy_until_all_are_resolved(client, world):
    po, received = damaged_po(client, world)
    shipment_id = received["id"]
    client.post(f"/api/shipments/{shipment_id}/discrepancies", json={"type": "OTHER", "description": "Wrong labels"}, headers=world.receiving)
    first, second = sorted(d["id"] for d in client.get("/api/discrepancies", headers=world.purchasing).json())

    client.post(f"/api/discrepancies/{first}/resolve", json={"resolution_note": "ok"}, headers=world.purchasing)
    assert client.get(f"/api/shipments/{shipment_id}", headers=world.purchasing).json()["status"] == "DISCREPANCY"
    client.post(f"/api/discrepancies/{second}/resolve", json={"resolution_note": "ok"}, headers=world.purchasing)
    assert client.get(f"/api/shipments/{shipment_id}", headers=world.purchasing).json()["status"] == "RESOLVED"


# --------------------------------------------------------------------------- overdue
def late_po(client, world, db, number="PO-LATE"):
    body = po_payload(world.vendor_a_id, number, issue_date=str(today() - timedelta(days=30)),
                      required_date=str(today() - timedelta(days=3)))
    return client.post("/api/pos", json=body, headers=world.purchasing).json()


def overdue_notes(db):
    return db.scalar(select(func.count()).select_from(Notification).where(Notification.type.like("%overdue")))


def test_overdue_po_alerts_once_and_rearms(client, world, db):
    po = late_po(client, world, db)
    assert check_overdue(db, today()) == (1, 0)
    db.commit()
    assert overdue_notes(db) == 2  # Purchasing + the vendor
    assert check_overdue(db, today()) == (0, 0)  # not twice

    # Purchasing moves the date: no longer overdue, so the mark is cleared ...
    client.put(f"/api/pos/{po['id']}", json={"required_date": str(today() + timedelta(days=5))}, headers=world.purchasing)
    db.expire_all()
    check_overdue(db, today())
    db.commit()
    assert db.get(PurchaseOrder, po["id"]).overdue_notified_at is None
    # ... and it alerts again once the new date passes
    assert check_overdue(db, today() + timedelta(days=6)) == (1, 0)


def test_overdue_shipment_alert(client, world, db):
    po = acknowledge(client, world, new_po(client, world)).json()
    shipment = ship(client, world, po, {1: 10}).json()["shipments"][0]
    assert check_overdue(db, today()) == (0, 0)  # expected tomorrow
    assert check_overdue(db, today() + timedelta(days=3)) == (0, 1)
    db.commit()
    assert db.get(Shipment, shipment["id"]).overdue_notified_at is not None
    assert check_overdue(db, today() + timedelta(days=4)) == (0, 0)


def test_delivered_and_cancelled_pos_are_never_overdue(client, world, db):
    po = late_po(client, world, db)
    client.post(f"/api/pos/{po['id']}/cancel", json={}, headers=world.purchasing)
    assert check_overdue(db, today()) == (0, 0)


# --------------------------------------------------------------------------- dashboard
def test_dashboard(client, world, db):
    damaged_po(client, world)
    late_po(client, world, db)
    for headers in (world.vendor_a, world.receiving):
        assert client.get("/api/dashboard/summary", headers=headers).status_code == 403

    res = client.get("/api/dashboard/summary", headers=world.purchasing)
    assert res.status_code == 200, res.text
    d = res.json()
    assert d["status_counts"]["PARTIALLY_DELIVERED"] == 1 and d["status_counts"]["ISSUED"] == 1
    assert d["status_counts"]["DELIVERED"] == 0
    assert d["open_pos"] == 2 and d["overdue_pos"] == 1 and d["open_discrepancies"] == 1 and d["in_transit"] == 0
    assert [(o["po_number"], o["days_late"]) for o in d["overdue"]] == [("PO-LATE", 3)]
    assert d["discrepancies"][0]["po_number"] == "PO-1"
    assert d["activity"][0]["po_number"] == "PO-LATE"  # newest first
    assert {a["subject"] for a in d["activity"]} >= {"PO", "PO-1-S1"}
    # Loading the dashboard ran the overdue check
    assert overdue_notes(db) == 2
