"""Unit tests for the status rules in app/services/status.py (no database needed)."""
from datetime import date
from decimal import Decimal as D

import pytest

from app.models import POStatus, ShipmentStatus
from app.services.status import (
    ItemProgress,
    can_change_shipment_status,
    derive_po_status,
    is_po_overdue,
    is_shipment_overdue,
)


def derive(items=None, *, cancelled=False, acknowledged=False, on_the_way=False):
    return derive_po_status(
        cancelled=cancelled,
        acknowledged=acknowledged,
        items=items if items is not None else [ItemProgress(D(10), D(0))],
        has_shipment_on_the_way=on_the_way,
    )


def test_new_po_is_issued():
    assert derive() == POStatus.ISSUED


def test_acknowledged_is_preparing():
    assert derive(acknowledged=True) == POStatus.PREPARING


def test_shipment_on_the_way():
    assert derive(acknowledged=True, on_the_way=True) == POStatus.ON_THE_WAY


def test_some_accepted_is_partially_delivered():
    items = [ItemProgress(D(10), D(4)), ItemProgress(D(5), D(0))]
    assert derive(items, acknowledged=True) == POStatus.PARTIALLY_DELIVERED


def test_partial_stays_partial_while_rest_is_on_the_way():
    items = [ItemProgress(D(10), D(4))]
    assert derive(items, acknowledged=True, on_the_way=True) == POStatus.PARTIALLY_DELIVERED


def test_everything_accepted_is_delivered_automatically():
    items = [ItemProgress(D(10), D(10)), ItemProgress(D("2.5"), D("2.5"))]
    assert derive(items, acknowledged=True) == POStatus.DELIVERED


def test_over_acceptance_still_counts_as_delivered():
    assert derive([ItemProgress(D(10), D(12))], acknowledged=True) == POStatus.DELIVERED


def test_cancelled_wins_over_everything():
    assert derive([ItemProgress(D(10), D(10))], cancelled=True, acknowledged=True) == POStatus.CANCELLED


def test_all_damaged_falls_back_to_preparing_for_replacement():
    # Shipment arrived but nothing was accepted and nothing else is on the way
    assert derive([ItemProgress(D(10), D(0))], acknowledged=True) == POStatus.PREPARING


def test_po_without_items_is_not_delivered():
    assert derive([], acknowledged=True) == POStatus.PREPARING


@pytest.mark.parametrize(
    ("old", "new", "ok"),
    [
        (ShipmentStatus.ON_THE_WAY, ShipmentStatus.DELIVERED, True),
        (ShipmentStatus.ON_THE_WAY, ShipmentStatus.DISCREPANCY, True),
        (ShipmentStatus.DISCREPANCY, ShipmentStatus.RESOLVED, True),
        (ShipmentStatus.DELIVERED, ShipmentStatus.ON_THE_WAY, False),
        (ShipmentStatus.DISCREPANCY, ShipmentStatus.DELIVERED, False),
        (ShipmentStatus.RESOLVED, ShipmentStatus.DISCREPANCY, False),
        (ShipmentStatus.ON_THE_WAY, ShipmentStatus.RESOLVED, False),
    ],
)
def test_shipment_transitions(old, new, ok):
    assert can_change_shipment_status(old, new) is ok


TODAY = date(2026, 11, 24)


def test_po_overdue_rules():
    assert is_po_overdue(POStatus.PREPARING, date(2026, 11, 23), TODAY)
    assert not is_po_overdue(POStatus.PREPARING, TODAY, TODAY)  # due today is not late yet
    assert not is_po_overdue(POStatus.DELIVERED, date(2026, 11, 1), TODAY)
    assert not is_po_overdue(POStatus.CANCELLED, date(2026, 11, 1), TODAY)
    assert not is_po_overdue(POStatus.ISSUED, None, TODAY)


def test_shipment_overdue_rules():
    assert is_shipment_overdue(ShipmentStatus.ON_THE_WAY, date(2026, 11, 20), TODAY)
    assert not is_shipment_overdue(ShipmentStatus.DELIVERED, date(2026, 11, 20), TODAY)
    assert not is_shipment_overdue(ShipmentStatus.ON_THE_WAY, None, TODAY)
