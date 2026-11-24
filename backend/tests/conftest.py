"""Tests run against a separate Postgres database (po_tracker_test), never the demo data."""
import os

os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://po_tracker:po_tracker@localhost:5432/po_tracker_test"
)

from dataclasses import dataclass  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.security import clear_failures  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, Vendor  # noqa: E402
from app.services.users import create_user  # noqa: E402

PASSWORD = "Password123!"


@pytest.fixture(scope="session", autouse=True)
def schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def clean_tables():
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
        else:  # quick local runs without Docker: TEST_DATABASE_URL=sqlite:///test.db
            for table in reversed(Base.metadata.sorted_tables):
                conn.execute(table.delete())
    clear_failures()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


@dataclass
class World:
    """Two vendors and one account per role, with ready-made auth headers."""

    vendor_a_id: int
    vendor_b_id: int
    purchasing: dict
    receiving: dict
    vendor_a: dict
    vendor_b: dict


def login(client: TestClient, email: str, password: str = PASSWORD) -> dict:
    res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.fixture
def world(db, client) -> World:
    va, vb = Vendor(name="Vendor A"), Vendor(name="Vendor B")
    db.add_all([va, vb])
    db.flush()
    create_user(db, name="Pat Purchasing", email="p@test.com", password=PASSWORD, role=Role.PURCHASING)
    create_user(db, name="Rui Receiving", email="r@test.com", password=PASSWORD, role=Role.RECEIVING)
    create_user(db, name="Ann VendorA", email="a@test.com", password=PASSWORD, role=Role.VENDOR, vendor_id=va.id)
    create_user(db, name="Ben VendorB", email="b@test.com", password=PASSWORD, role=Role.VENDOR, vendor_id=vb.id)
    db.commit()
    return World(
        vendor_a_id=va.id,
        vendor_b_id=vb.id,
        purchasing=login(client, "p@test.com"),
        receiving=login(client, "r@test.com"),
        vendor_a=login(client, "a@test.com"),
        vendor_b=login(client, "b@test.com"),
    )


def po_payload(vendor_id: int, number: str = "PO-1", **extra) -> dict:
    return {
        "po_number": number,
        "vendor_id": vendor_id,
        "issue_date": "2026-11-01",
        "required_date": "2026-12-01",
        "items": [
            {"item_name": "Gloves", "item_code": "GLV", "quantity_ordered": 100, "unit": "pair"},
            {"item_name": "Wipes", "quantity_ordered": 2.5, "unit": "kg"},
        ],
        **extra,
    }
