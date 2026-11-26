# Carsem PO Tracker

Tracks the delivery of purchase order (PO) items between Carsem **Purchasing**, **Receiving** and **vendors**:
Issued → Preparing → On the way → (Partially) Delivered, with discrepancies flagged to Purchasing.

Each role (Purchasing, Receiving, Vendor) signs in and sees only what it should; access is enforced on the backend.

## Features

- **Purchasing:** dashboard (POs by status, overdue POs and shipments, open discrepancies, recent activity);
  create/edit/cancel POs; search and filters; resolve discrepancies; manage vendors and logins.
- **Vendor:** sees only their own POs (open and history); acknowledges a PO (can flag different names or quantities);
  dispatches full or partial shipments with courier, tracking number, expected date and DO/invoice.
- **Receiving:** incoming shipments sorted by expected date; tablet-friendly receive form that highlights short,
  extra, wrong or damaged goods while typing; declares discrepancies with photos.
- **Automatic PO status:** Issued → Preparing → On the way → Partially delivered → Delivered, worked out from
  what was shipped and accepted, with a full timeline.
- **Notifications:** bell with unread count for every step, each also sent as a (mocked) email to the `email_log`
  table. Overdue POs and shipments are alerted once, by a background check (`OVERDUE_CHECK_MINUTES`, default 60)
  and on dashboard load.

## Stack

FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · React 18 + TypeScript + Vite + Tailwind v4 · Docker Compose

## Run it

```bash
cp .env.example .env              # then change SECRET_KEY
docker compose up --build -d      # db, backend (runs migrations on start), frontend
docker compose exec backend python seed.py
```

`seed.py --reset` deletes **all** data and re-creates the demo, with POs in every stage
(on the way, overdue, partially delivered, open discrepancy, delivered, new).

- App: http://localhost
- API docs: http://localhost:8000/docs

### Demo accounts (password: `Password123!`, or `SEED_PASSWORD` from `.env`)

| Role | Email |
|---|---|
| Purchasing | purchasing@carsem.com |
| Receiving | receiving@carsem.com |
| Vendor (Apex Industrial Supplies) | vendor@apex.example.com |
| Vendor (Borneo Precision Parts) | vendor@borneo.example.com |

## Development

```bash
# Backend tests (separate po_tracker_test database, created automatically on first DB start)
docker compose exec backend pytest

# Quick backend tests without Docker (SQLite stand-in)
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt
TEST_DATABASE_URL=sqlite:///test.db .venv/Scripts/python -m pytest

# New migration after changing app/models
docker compose exec backend alembic revision --autogenerate -m "describe the change"
docker compose cp backend:/app/alembic/versions ./backend/alembic

# Frontend with hot reload (proxies /api to the backend on localhost:8000)
cd frontend && npm install && npm run dev     # http://localhost:5173
```

## Project layout

```
backend/
  app/
    core/       config, security (hashing, JWT, login lockout), deps (current user, role checks)
    models/     SQLAlchemy tables and status enums
    schemas/    Pydantic request/response models
    routers/    auth, vendors, users, pos, shipments, attachments, discrepancies, notifications, dashboard (all under /api)
    services/   status (derived PO status rules), access (who sees which PO), po (create_po, edit, cancel, search),
                shipments (acknowledge, dispatch, receive, discrepancies), discrepancies (list, resolve),
                overdue (alerts), dashboard, notify + email (mocked), storage + attachments (uploads)
  alembic/      migrations
  tests/
  seed.py
frontend/src/
  api/          fetch client, types, formatting
  components/   UI kit (Carsem Shipping Portal style), layout, status badges
  context/      AuthContext
  pages/        login, dashboard, PO list/detail/form, discrepancies, incoming shipments, receive form, vendors & users
```

## Access rules

Enforced on the backend for every request:

| Role | Sees |
|---|---|
| Purchasing | Everything; manages POs, vendors and users |
| Vendor | Only their own vendor's POs, including delivered/cancelled history |
| Receiving | POs that have at least one shipment |

A PO the user may not see returns **404**, so its existence is not revealed.
