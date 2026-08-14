# Ganpati Utsav Management API

FastAPI + PostgreSQL backend for a residential society's Ganpati festival:
flat register, contribution (collection) tracking, expense tracking, live
financial summary and a one-call dashboard for the Flutter app.

* **Swagger UI** — <http://localhost:8000/docs>
* **ReDoc** — <http://localhost:8000/redoc>
* **OpenAPI JSON** — <http://localhost:8000/openapi.json> (importable into Postman / `openapi-generator` for Dart)
* **[Ganpati-API-Integration.md](Ganpati-API-Integration.md)** — the standalone
  integration guide to hand to the Flutter developer

---

## Flat count: 24 — confirmed

`A1..A12` + `B1..B12` = **24 flats**. The "28 flats" figure in the original
requirement was incorrect and has been confirmed as 24 by the society.

Nothing in the code assumes a number; the structure comes from one environment
variable, and `EXPECTED_TOTAL_FLATS` is the cross-check:

```env
SOCIETY_WINGS=A:12,B:12
EXPECTED_TOTAL_FLATS=24
```

Because the two agree, `GET /api/flats/config` returns
`matches_expectation: true` and `GET /api/dashboard` returns
`flat_config_warning: null`. If they ever disagree, the mismatch is reported by
that endpoint, by the seed script and in the server startup log.

To add flats later: extend `SOCIETY_WINGS` (e.g. `A:14,B:14`) and re-run
`python -m scripts.seed` (idempotent), or use `POST /api/flats` /
`POST /api/flats/bulk` at runtime.

---

## Quick start (local)

Requires **Python 3.11+** and **PostgreSQL 13+**.

```bash
# 1. Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configuration
cp .env.example .env
#    edit DATABASE_URL with your PostgreSQL credentials

# 3. Create the database (once)
createdb ganpati_db          # or: psql -c "CREATE DATABASE ganpati_db;"

# 4. Create the tables
alembic upgrade head

# 5. Seed flats + expense categories (+ optional sample transactions)
python -m scripts.seed --with-samples

# 6. Run
uvicorn app.main:app --reload
```

Open <http://localhost:8000/docs>.

### Tests

```bash
pytest
```

The suite runs on an in-memory SQLite database, so it needs **no PostgreSQL
server** and can never touch your real data. To run it against real Postgres:

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/ganpati_test pytest
```

### Docker (optional)

```bash
docker compose up -d --build
docker compose exec api alembic upgrade head
docker compose exec api python -m scripts.seed --with-samples
```

---

## Architecture

```
Flutter app
    │  HTTP/JSON
    ▼
routers/       thin HTTP layer — validate, call a service, wrap the response
    ▼
services/      ALL business logic: money rules, aggregation, audit writes
    ▼
models/        SQLAlchemy 2.x ORM (async), NUMERIC(12,2) money columns
    ▼
PostgreSQL
```

```
app/
├── main.py                 app factory, CORS, error handlers, router mounting
├── dependencies.py         DB session, pagination, filters, X-Actor header
├── core/
│   ├── config.py           env-driven settings (wings, CORS, DB, behaviour)
│   ├── database.py         async engine + session factory + get_db()
│   ├── exceptions.py       typed errors carrying stable error codes
│   └── error_handlers.py   turns every failure into the standard envelope
├── models/                 flat, collection, expense, category, audit, enums
├── schemas/                Pydantic v2 request/response models
├── services/               flat, collection, expense, category, finance, audit
├── routers/                flats, collections, expenses, categories,
│                           finance, dashboard, meta, audit
└── utils/                  money (Decimal), pagination, response envelope
alembic/                    migrations (0001_initial_schema.py)
scripts/seed.py             idempotent seed data
tests/                      pytest suite (60 tests)
```

### Design decisions worth knowing

| Decision | Why |
|---|---|
| `remaining_balance` is **never stored** | Always `SUM(collections) - SUM(expenses)` at query time, so it cannot drift. |
| Money is `NUMERIC(12,2)` + Python `Decimal` | No floating point anywhere in storage or arithmetic. JSON carries plain numbers (`2500.0`) because JSON has no decimal type. |
| Enums stored as `VARCHAR` + `CHECK` | Adding a payment method later is an ordinary migration, not `ALTER TYPE`. |
| Expense categories are a **table** | Manageable through the API without a code change. |
| One generic `audit_logs` table | Every create/update/delete of a financial row is recorded with a per-field diff and a full snapshot. |
| `RESTRICT` foreign keys | A flat with money recorded, or a category in use, cannot be deleted — 409 instead of data loss. |
| No authentication (as requested) | But every write already accepts an optional `X-Actor` header that lands in the audit log, and routers are dependency-injected so a single `Depends(get_current_user)` can be added later. |

---

## Database schema

```
┌──────────────────────┐          ┌────────────────────────┐
│ flats                │          │ expense_categories     │
├──────────────────────┤          ├────────────────────────┤
│ id            PK     │          │ id              PK     │
│ wing                 │          │ code        UNIQUE     │
│ flat_number   UNIQUE │          │ name        UNIQUE     │
│ display_name         │          │ description            │
│ owner_name           │          │ is_active              │
│ phone                │          │ sort_order             │
│ notes                │          │ is_system              │
│ is_active            │          │ created_at, updated_at │
│ sort_order           │          └───────────┬────────────┘
│ created_at,updated_at│                      │ 1
└──────────┬───────────┘                      │
           │ 1                                │
           │                                  │ N
           │ N                    ┌───────────┴────────────┐
┌──────────┴───────────┐          │ expenses               │
│ collections          │          ├────────────────────────┤
├──────────────────────┤          │ id              PK     │
│ id            PK     │          │ category_id     FK ────┘
│ flat_id       FK ────┘          │ title                  │
│ amount   NUMERIC(12,2)          │ description            │
│ payment_method       │          │ amount  NUMERIC(12,2)  │
│ status               │          │ payment_method         │
│ reference_no         │          │ spent_on       DATE    │
│ collected_on  DATE   │          │ vendor                 │
│ collected_by         │          │ reference_no           │
│ notes                │          │ paid_by                │
│ created_at,updated_at│          │ notes                  │
└──────────────────────┘          │ created_at, updated_at │
                                  └────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│ audit_logs   (no FKs on purpose — rows outlive deletions)  │
├───────────────────────────────────────────────────────────┤
│ id PK │ entity_type │ entity_id │ action                   │
│ changes JSONB  {"amount": {"old":"3000.00","new":"3500.00"}}│
│ snapshot JSONB │ actor │ note │ created_at                  │
└───────────────────────────────────────────────────────────┘
```

Relationships: `Flat 1—N Collection` (`ondelete RESTRICT`),
`ExpenseCategory 1—N Expense` (`ondelete RESTRICT`).
Constraints: `amount > 0` CHECK on both money tables, `UNIQUE(flat_number)`,
`UNIQUE(wing, display_name)`, `UNIQUE(expense_categories.code)`.

### Enums

| `payment_method` | `status` (collections) |
|---|---|
| `CASH`, `UPI`, `BANK_TRANSFER`, `OTHER` | `PENDING`, `CONFIRMED` (default), `CANCELLED` |

**Only `CONFIRMED` collections count** towards `total_collection` and
`remaining_balance`. `PENDING` (promised but not received) is reported
separately as `pending_amount`; `CANCELLED` is excluded from every total.

---

# API documentation for the Flutter developer

Base URL (local): `http://localhost:8000/api`
Android emulator: use `http://10.0.2.2:8000/api`.

## The response envelope — read this first

**Every** response, success or failure, has the same top-level shape.

Success:

```json
{ "success": true, "data": { }, "message": "Collection created successfully" }
```

Failure:

```json
{ "success": false, "message": "Flat A5 does not exist", "error": "FLAT_NOT_FOUND", "details": null }
```

* `message` is safe to show in a SnackBar.
* `error` is a stable code — branch on this, never on `message`.
* `details` carries field-level errors for `VALIDATION_ERROR` (422).

Paginated endpoints put the list inside `data`:

```json
{
  "success": true,
  "data": {
    "items": [ ],
    "pagination": { "page": 1, "limit": 20, "total": 37, "pages": 2,
                    "has_next": true, "has_previous": false }
  },
  "message": "Expenses fetched successfully"
}
```

### Error codes

| HTTP | `error` | When |
|---|---|---|
| 400 | `INVALID_WING` | Wing is not in `SOCIETY_WINGS` |
| 400 | `INVALID_DATE_RANGE` | `date_from` is after `date_to` |
| 404 | `FLAT_NOT_FOUND` | Unknown `flat_id` |
| 404 | `COLLECTION_NOT_FOUND` / `EXPENSE_NOT_FOUND` / `CATEGORY_NOT_FOUND` | Unknown id/code |
| 404 | `NOT_FOUND` | Unknown route |
| 409 | `DUPLICATE_FLAT` / `DUPLICATE_CATEGORY` | Unique constraint |
| 409 | `FLAT_HAS_COLLECTIONS` / `CATEGORY_IN_USE` | Delete blocked by references |
| 409 | `INTEGRITY_ERROR` | Database constraint violated |
| 422 | `VALIDATION_ERROR` | Bad body/query (negative amount, future date, bad enum, missing field) |
| 500 | `INTERNAL_ERROR` / `DATABASE_ERROR` | Unexpected failure |

### Optional header

`X-Actor: Sunny` on any write records who made the change in the audit log.
Optional today; it becomes the authenticated user when auth is added.

### Amounts and dates

* Amounts are JSON **numbers** with 2 decimals (`2500.0`). Parse into
  `double`, or better into a Dart `Decimal` for display. Send them as numbers
  or as strings (`"2500.50"`) — both are accepted.
* Dates are `YYYY-MM-DD`. Timestamps are ISO-8601.
* Future dates are rejected unless `ALLOW_FUTURE_DATES=true`.

---

## 1. Meta & health

### `GET /api/meta`
Everything needed to build dropdowns, in one call. Fetch once on app start.

```json
{ "success": true, "data": {
  "app_name": "Ganpati Utsav Management API", "environment": "development",
  "currency": "INR", "currency_symbol": "₹",
  "payment_methods": [{ "value": "CASH", "label": "Cash" },
                      { "value": "UPI", "label": "UPI" },
                      { "value": "BANK_TRANSFER", "label": "Bank Transfer" },
                      { "value": "OTHER", "label": "Other" }],
  "collection_statuses": [{ "value": "PENDING", "label": "Pending" },
                          { "value": "CONFIRMED", "label": "Confirmed" },
                          { "value": "CANCELLED", "label": "Cancelled" }],
  "wings": ["A", "B"],
  "expense_categories": [{ "id": 1, "code": "DECORATION", "name": "Decoration", "is_active": true }],
  "default_page_size": 20, "max_page_size": 100
}, "message": "Metadata fetched successfully" }
```

### `GET /api/health`
Liveness + a real database round trip. `data.status` is `"ok"` or `"degraded"`.

---

## 2. Dashboard

### `GET /api/dashboard`
**One call renders the entire home screen.**

```json
{ "success": true, "data": {
  "currency_symbol": "₹",
  "total_collection": 50000.0,
  "total_expenses": 12500.0,
  "remaining_balance": 37500.0,
  "pending_collection_amount": 0.0,
  "total_flats": 24,
  "active_flats": 24,
  "flats_contributed": 2,
  "flats_not_contributed": 22,
  "collection_percentage": 8.33,
  "expense_percentage": 25.0,
  "collection_count": 2,
  "expense_count": 2,
  "average_contribution": 25000.0,
  "top_expense_categories": [
    { "category_id": 3, "category_code": "SOUND", "category_name": "Sound",
      "total": 9000.0, "count": 1, "percentage": 72.0 }],
  "collection_by_payment_method": [
    { "payment_method": "CASH", "label": "Cash", "total": 20000.0, "count": 1 }],
  "collection_by_wing": [
    { "wing": "A", "total": 50000.0, "count": 2, "flats_total": 12,
      "flats_contributed": 2, "flats_pending": 10 }],
  "recent_collections": [ ],
  "recent_expenses": [ ],
  "flat_config_warning": null
}, "message": "Dashboard data fetched successfully" }
```

Errors: `500 INTERNAL_ERROR`.

---

## 3. Flats

### `GET /api/flats`
Query: `wing`, `is_active`, `search`. Not paginated (24 rows) — fetch once and cache.

```json
{ "success": true, "data": {
  "items": [{ "id": 1, "wing": "A", "flat_number": "A1", "display_name": "A1",
              "owner_name": null, "phone": null, "notes": null,
              "is_active": true, "sort_order": 1,
              "created_at": "2026-08-13T05:31:24Z", "updated_at": "2026-08-13T05:31:24Z" }],
  "total": 24, "wings": ["A", "B"]
}, "message": "Flats fetched successfully" }
```

Example: `GET /api/flats?wing=A` · Errors: `400 INVALID_WING`.

### `GET /api/flats/{id}`
Errors: `404 FLAT_NOT_FOUND`.

### `GET /api/flats/{id}/collections`
All contributions of one flat.

```json
{ "success": true, "data": {
  "flat": { "id": 2, "wing": "A", "flat_number": "A2", "display_name": "A2" },
  "total_amount": 2000.0, "collection_count": 2, "collections": [ ]
}, "message": "Flat collections fetched successfully" }
```

### `GET /api/flats/config`
Reports the configured vs expected flat count and how to fix any mismatch
(see the top of this file). Currently `matches_expectation: true`.

### `POST /api/flats` → `201`

Request:
```json
{ "wing": "A", "flat_number": "A13", "display_name": "A13",
  "owner_name": "Ramesh Patil", "phone": "9876543210", "notes": null }
```
Only `wing` and `flat_number` are required; `display_name` defaults to `flat_number`.

Response: `data` = the created flat (same shape as `GET /api/flats/{id}`).
Errors: `409 DUPLICATE_FLAT`, `400 INVALID_WING`, `422 VALIDATION_ERROR` (bad phone).

### `POST /api/flats/bulk` → `201`
Add several flats at once (e.g. the missing 4).

```json
{ "flats": [{ "wing": "A", "flat_number": "A13" },
            { "wing": "A", "flat_number": "A14" }],
  "skip_existing": true }
```
Response `data`: `{ "created": [...], "skipped": ["A1"], "created_count": 2, "skipped_count": 1 }`.

### `PUT /api/flats/{id}` (also `PATCH`)
Partial update — send only the fields that change.
```json
{ "owner_name": "Sunny Mane", "phone": "9876500000", "is_active": true }
```
Errors: `404 FLAT_NOT_FOUND`, `409 DUPLICATE_FLAT`, `400 INVALID_WING`.

### `DELETE /api/flats/{id}`
Response `data`: `{ "id": 5, "deleted": true }`.
Errors: `404 FLAT_NOT_FOUND`, `409 FLAT_HAS_COLLECTIONS` (deactivate instead).

---

## 4. Collections

### `POST /api/collections` → `201`

Request:
```json
{ "flat_id": 1, "amount": 2500, "payment_method": "UPI",
  "collected_on": "2026-08-12", "status": "CONFIRMED",
  "reference_no": "UPI-8890123", "collected_by": "Sunny",
  "notes": "Ganpati contribution" }
```
Required: `flat_id`, `amount` (> 0), `payment_method`.
Defaults: `collected_on` = today, `status` = `CONFIRMED`.

Response:
```json
{ "success": true, "data": {
  "id": 1, "flat_id": 1, "amount": 2500.0,
  "payment_method": "UPI", "payment_method_label": "UPI",
  "status": "CONFIRMED", "collected_on": "2026-08-12",
  "reference_no": "UPI-8890123", "collected_by": "Sunny",
  "notes": "Ganpati contribution",
  "flat": { "id": 1, "wing": "A", "flat_number": "A1", "display_name": "A1" },
  "created_at": "2026-08-12T10:15:00Z", "updated_at": "2026-08-12T10:15:00Z"
}, "message": "Collection created successfully" }
```

Errors: `404 FLAT_NOT_FOUND`, `422 VALIDATION_ERROR` (amount ≤ 0, future date, bad enum, missing field).

### `GET /api/collections`
Paginated. Query: `page`, `limit`, `flat_id`, `wing`, `payment_method`,
`status`, `date_from`, `date_to`, `min_amount`, `max_amount`, `search`.

Examples:
```
GET /api/collections?wing=A&page=1&limit=20
GET /api/collections?payment_method=UPI&date_from=2026-08-01&date_to=2026-08-31
GET /api/collections?search=A5
```
Errors: `400 INVALID_WING`, `400 INVALID_DATE_RANGE`.

### `GET /api/collections/{id}` — errors `404 COLLECTION_NOT_FOUND`

### `PUT /api/collections/{id}` (also `PATCH`)
Partial update; add `audit_note` to record *why*.
```json
{ "amount": 3000, "payment_method": "CASH", "audit_note": "Corrected receipt amount" }
```
Errors: `404 COLLECTION_NOT_FOUND`, `404 FLAT_NOT_FOUND`, `422 VALIDATION_ERROR`.

### `DELETE /api/collections/{id}?reason=Duplicate%20entry`
Response `data`: `{ "id": 1, "deleted": true }`. A full snapshot is kept in the audit log.

### `GET /api/collections/summary`
Optional `date_from` / `date_to`.

```json
{ "success": true, "data": {
  "total_collection": 6000.0,
  "pending_amount": 1000.0,
  "cancelled_amount": 0.0,
  "collection_count": 3,
  "total_flats": 24,
  "flats_contributed": 2,
  "flats_not_contributed": 22,
  "contribution_percentage": 8.33,
  "average_per_contributing_flat": 3000.0,
  "highest_contribution": 3000.0,
  "total_cash": 2500.0, "total_upi": 500.0,
  "total_bank_transfer": 3000.0, "total_other": 0.0,
  "by_payment_method": [{ "payment_method": "CASH", "label": "Cash", "total": 2500.0, "count": 1 }],
  "by_status": [{ "status": "CONFIRMED", "total": 6000.0, "count": 3 }],
  "by_wing": [{ "wing": "A", "total": 3000.0, "count": 2, "flats_total": 12,
                "flats_contributed": 1, "flats_pending": 11 }],
  "by_flat": [{ "flat_id": 1, "wing": "A", "flat_number": "A1", "display_name": "A1",
                "owner_name": null, "total_amount": 3000.0, "collection_count": 2,
                "has_contributed": true, "last_collected_on": "2026-08-12" }]
}, "message": "Collection summary generated successfully" }
```

### `GET /api/collections/by-flat`
Just the `by_flat` list (every flat, including the ones with `total_amount: 0.0`).

### `GET /api/collections/pending-flats`
Flats that have not contributed yet.
```json
{ "success": true, "data": {
  "items": [{ "id": 6, "wing": "A", "flat_number": "A6", "display_name": "A6" }],
  "total": 22 }, "message": "22 flat(s) have not contributed yet" }
```

### `GET /api/collections/{id}/history`
Audit trail for one contribution (see §7).

---

## 5. Expenses

### `POST /api/expenses` → `201`

Request:
```json
{ "title": "Decoration material", "amount": 3500, "payment_method": "UPI",
  "category_code": "DECORATION", "spent_on": "2026-08-12",
  "vendor": "Sai Decorators", "reference_no": "BILL-104",
  "paid_by": "Sunny", "description": null, "notes": null }
```
Required: `title`, `amount` (> 0), `payment_method`, and **either**
`category_code` **or** `category_id`. `spent_on` defaults to today.

Response:
```json
{ "success": true, "data": {
  "id": 1, "title": "Decoration material", "description": null,
  "amount": 3500.0, "payment_method": "UPI", "payment_method_label": "UPI",
  "category_id": 1, "category_code": "DECORATION", "category_name": "Decoration",
  "spent_on": "2026-08-12", "vendor": "Sai Decorators",
  "reference_no": "BILL-104", "paid_by": "Sunny", "notes": null,
  "category": { "id": 1, "code": "DECORATION", "name": "Decoration",
                "description": "Mandap, lights, flowers, backdrop",
                "is_active": true, "sort_order": 10, "is_system": true },
  "created_at": "2026-08-12T10:20:00Z", "updated_at": "2026-08-12T10:20:00Z"
}, "message": "Expense created successfully" }
```

Errors: `404 CATEGORY_NOT_FOUND`, `422 VALIDATION_ERROR`.

### `GET /api/expenses`
Paginated. Query: `page`, `limit`, `category` (code), `category_id`,
`payment_method`, `date_from`, `date_to`, `min_amount`, `max_amount`, `search`
(matches title, description, vendor, reference, notes, paid_by).

```
GET /api/expenses?page=1&limit=20
GET /api/expenses?category=DECORATION
GET /api/expenses?search=mandap&payment_method=CASH
```

### `GET /api/expenses/{id}` — errors `404 EXPENSE_NOT_FOUND`

### `PUT /api/expenses/{id}` (also `PATCH`)
```json
{ "amount": 3500, "audit_note": "Vendor revised the bill" }
```

### `DELETE /api/expenses/{id}?reason=Entered%20twice`

### `GET /api/expenses/summary`
```json
{ "success": true, "data": {
  "total_expenses": 12000.0, "expense_count": 3,
  "average_expense": 4000.0, "highest_expense": 6500.0,
  "total_cash": 8500.0, "total_upi": 3500.0,
  "total_bank_transfer": 0.0, "total_other": 0.0,
  "by_category": [{ "category_id": 1, "category_code": "DECORATION",
                    "category_name": "Decoration", "total": 10000.0,
                    "count": 2, "percentage": 83.33 }],
  "by_payment_method": [{ "payment_method": "CASH", "label": "Cash",
                          "total": 8500.0, "count": 2 }]
}, "message": "Expense summary generated successfully" }
```

### `GET /api/expenses/{id}/history` — audit trail (see §7)

---

## 6. Expense categories

Seeded: `DECORATION`, `FOOD`, `SOUND`, `ELECTRICITY`, `POOJA`, `PRASAD`,
`CLEANING`, `TRANSPORTATION`, `ADVERTISEMENT`, `MISCELLANEOUS`.

| Method | URL | Notes |
|---|---|---|
| `GET` | `/api/expense-categories` | Query: `is_active`, `search` |
| `GET` | `/api/expense-categories/{id}` | |
| `POST` | `/api/expense-categories` | `{ "name": "Generator Rent", "sort_order": 110 }` → `code` auto-derived (`GENERATOR_RENT`) |
| `PUT` | `/api/expense-categories/{id}` | `code` is immutable by design |
| `DELETE` | `/api/expense-categories/{id}` | `409 CATEGORY_IN_USE` when expenses reference it |

---

## 7. Finance & audit

### `GET /api/finance/summary`
Optional `date_from` / `date_to`.

```json
{ "success": true, "data": {
  "total_collection": 50000.0,
  "total_expenses": 12500.0,
  "remaining_balance": 37500.0,
  "currency": "INR", "currency_symbol": "₹",
  "collection_count": 2, "expense_count": 2,
  "pending_collection_amount": 0.0,
  "utilisation_percentage": 25.0,
  "collection_by_payment_method": [ ],
  "collection_by_wing": [ ],
  "expenses_by_category": [ ],
  "expenses_by_payment_method": [ ],
  "recent_collections": [ ],
  "recent_expenses": [ ]
}, "message": "Financial summary generated successfully" }
```

### `GET /api/finance/balance`
Lightweight: only `total_collection`, `total_expenses`, `remaining_balance`.

### `GET /api/audit-logs`
Paginated. Query: `entity_type` (`FLAT|COLLECTION|EXPENSE|EXPENSE_CATEGORY`),
`entity_id`, `action` (`CREATE|UPDATE|DELETE`).

```json
{ "success": true, "data": { "items": [{
  "id": 12, "entity_type": "EXPENSE", "entity_id": 1, "action": "UPDATE",
  "changes": { "amount": { "old": "3000.00", "new": "3500.00" } },
  "snapshot": { "id": 1, "title": "Decoration material", "amount": "3500.00" },
  "actor": "Sunny", "note": "Vendor revised the bill",
  "created_at": "2026-08-12T11:05:00Z" }],
  "pagination": { } }, "message": "Audit logs fetched successfully" }
```

An UPDATE that changes nothing is not logged. A DELETE keeps the full snapshot
so a removed record can still be inspected.

---

## How Flutter talks to this backend

1. **Base URL** — `http://localhost:8000/api` for desktop/web,
   `http://10.0.2.2:8000/api` for the Android emulator, your machine's LAN IP
   for a physical device. Put it in one constant.
2. **CORS** — only matters for Flutter **Web**. Add your dev origin to
   `CORS_ORIGINS` in `.env`. Android/iOS builds are unaffected.
3. **Android cleartext** — plain `http://` needs
   `android:usesCleartextTraffic="true"` in the debug manifest (or use HTTPS).
4. **One envelope, one model** — every response is
   `{success, data, message}`, so a single generic wrapper covers the whole API:

```dart
class ApiResponse<T> {
  final bool success;
  final T? data;
  final String message;
  ApiResponse({required this.success, this.data, required this.message});

  factory ApiResponse.fromJson(Map<String, dynamic> json,
      T Function(dynamic)? parse) {
    return ApiResponse(
      success: json['success'] as bool,
      data: json['data'] == null || parse == null ? null : parse(json['data']),
      message: json['message'] as String? ?? '',
    );
  }
}

class ApiException implements Exception {
  final String code;     // e.g. FLAT_NOT_FOUND — branch on this
  final String message;  // safe to show to the user
  final int statusCode;
  ApiException(this.code, this.message, this.statusCode);
  @override
  String toString() => message;
}

class GanpatiApi {
  static const base = 'http://10.0.2.2:8000/api'; // Android emulator
  final http.Client _client;
  GanpatiApi(this._client);

  Future<T> _send<T>(Future<http.Response> future, T Function(dynamic) parse) async {
    final res = await future;
    final body = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    if (body['success'] != true) {
      throw ApiException(
        body['error'] as String? ?? 'UNKNOWN',
        body['message'] as String? ?? 'Something went wrong',
        res.statusCode,
      );
    }
    return parse(body['data']);
  }

  Future<Dashboard> dashboard() =>
      _send(_client.get(Uri.parse('$base/dashboard')), (d) => Dashboard.fromJson(d));

  Future<List<Flat>> flats({String? wing}) => _send(
        _client.get(Uri.parse('$base/flats').replace(
            queryParameters: wing == null ? null : {'wing': wing})),
        (d) => (d['items'] as List).map((e) => Flat.fromJson(e)).toList(),
      );

  Future<Collection> addCollection({
    required int flatId,
    required num amount,
    required String paymentMethod,
    String? notes,
  }) =>
      _send(
        _client.post(
          Uri.parse('$base/collections'),
          headers: const {'Content-Type': 'application/json'},
          body: jsonEncode({
            'flat_id': flatId,
            'amount': amount,
            'payment_method': paymentMethod,
            if (notes != null) 'notes': notes,
          }),
        ),
        (d) => Collection.fromJson(d),
      );
}
```

5. **Suggested screen → endpoint mapping**

| Screen | Call |
|---|---|
| Home / dashboard | `GET /api/dashboard` |
| App startup (dropdown values) | `GET /api/meta` |
| Flat list | `GET /api/flats` (cache it) |
| Flat detail | `GET /api/flats/{id}/collections` |
| Add contribution | `POST /api/collections` |
| Collection list + filters | `GET /api/collections?...` |
| "Who hasn't paid" | `GET /api/collections/pending-flats` |
| Collection report | `GET /api/collections/summary` |
| Expense list + search | `GET /api/expenses?...` |
| Add expense | `POST /api/expenses` |
| Expense report | `GET /api/expenses/summary` |
| Accounts screen | `GET /api/finance/summary` |
| Edit history | `GET /api/expenses/{id}/history` |

6. **Amounts** — parse `2500.0` into `double` for maths you don't persist, but
   display with 2 decimals. The server is the only place totals are computed;
   never sum on the client and send a total back.
7. **Model generation** — `openapi.json` is complete, so
   `openapi-generator-cli generate -i http://localhost:8000/openapi.json -g dart-dio`
   produces typed Dart models if you prefer that to hand-written ones.

---

## Adding authentication later (not implemented, by request)

The seams already exist: routers use dependency injection, services never
touch `Request`, and every write accepts an `actor`. Adding auth means
(1) a `users` table + `/api/auth/login` returning a JWT, (2) a
`get_current_user` dependency, (3) `dependencies=[Depends(get_current_user)]`
on the routers, (4) pass the user into services as `actor`. No service or
model changes are needed.

## Common commands

```bash
uvicorn app.main:app --reload            # run the API
pytest                                   # run the tests (SQLite, no server needed)
alembic revision --autogenerate -m "..." # create a migration after model changes
alembic upgrade head                     # apply migrations
alembic downgrade -1                     # roll back one migration
alembic check                            # verify models and migrations agree
python -m scripts.seed                   # flats + categories (idempotent)
python -m scripts.seed --with-samples    # + sample transactions
python -m scripts.seed --reset           # wipe transactions, keep flats
```
