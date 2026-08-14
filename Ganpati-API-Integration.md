# Ganpati Utsav API — Flutter Integration Guide

Everything needed to integrate the Flutter app. No backend knowledge required.

* **Live docs (Swagger):** `http://localhost:8000/docs`
* **OpenAPI spec:** `http://localhost:8000/openapi.json` — importable into Postman, or into `openapi-generator-cli ... -g dart-dio` for typed Dart models
* **Version:** 1.0.0 · **API prefix:** `/api`

---

## 1. Connecting

| Client | Base URL |
|---|---|
| Android emulator | `http://10.0.2.2:8000/api` |
| iOS simulator / desktop / Flutter Web | `http://localhost:8000/api` |
| Physical device | `http://<your-machine-LAN-IP>:8000/api` |

* **Flutter Web only:** the origin must be listed in the backend's `CORS_ORIGINS`. Mobile builds send no `Origin` header and are unaffected.
* **Android release/debug over plain HTTP** needs `android:usesCleartextTraffic="true"` in the manifest (or serve over HTTPS).
* **No authentication.** Every endpoint is open. An optional `X-Actor: <name>` header on any write records who made the change in the audit log — send the logged-in committee member's name once you have one.

---

## 2. The response envelope — read this first

**Every** response has the same top-level shape, success or failure. Write one wrapper class and you are done.

**Success**

```json
{
  "success": true,
  "data": { },
  "message": "Collection created successfully"
}
```

**Failure**

```json
{
  "success": false,
  "message": "Flat A5 does not exist",
  "error": "FLAT_NOT_FOUND",
  "details": null
}
```

* `message` — human readable, safe to show in a SnackBar.
* `error` — **stable machine code. Branch on this, never on `message`.**
* `details` — field-level errors for `VALIDATION_ERROR`, otherwise `null`:
  ```json
  [{ "field": "flat_id", "message": "Field required", "type": "missing" }]
  ```

**Paginated lists** put `items` + `pagination` inside `data`:

```json
{
  "success": true,
  "data": {
    "items": [ ],
    "pagination": {
      "page": 1, "limit": 20, "total": 37, "pages": 2,
      "has_next": true, "has_previous": false
    }
  },
  "message": "Expenses fetched successfully"
}
```

---

## 3. Conventions

### Money
Amounts are JSON **numbers with 2 decimals** (`2500.0`, `1000.1`). Send them as a number (`2500`) or a string (`"2500.50"`) — both accepted. More than 2 decimal places is rejected with `422`.

> The server is the only place totals are computed. Never sum on the client and send a total back — there is no endpoint that accepts one.

### Dates
`YYYY-MM-DD` (e.g. `"2026-08-15"`). Timestamps (`created_at`, `updated_at`) are ISO-8601. **Future dates are rejected** with `422`.

### Enums

| `payment_method` | Label shown by the API |
|---|---|
| `CASH` | Cash |
| `UPI` | UPI |
| `BANK_TRANSFER` | Bank Transfer |
| `OTHER` | Other |

| `status` (collections) | Meaning |
|---|---|
| `CONFIRMED` *(default)* | Money received. **Only these count toward totals and balance.** |
| `PENDING` | Promised, not yet received. Reported separately as `pending_amount`. |
| `CANCELLED` | Recorded by mistake / refunded. Excluded from every total. |

Every collection/expense object also carries `payment_method_label` so the UI never has to map codes to text.

### Error codes

| HTTP | `error` | When |
|---|---|---|
| 400 | `INVALID_WING` | Wing is not `A` or `B` |
| 400 | `INVALID_DATE_RANGE` | `date_from` is after `date_to` |
| 404 | `FLAT_NOT_FOUND` | Unknown `flat_id` |
| 404 | `COLLECTION_NOT_FOUND` | Unknown collection id |
| 404 | `EXPENSE_NOT_FOUND` | Unknown expense id |
| 404 | `CATEGORY_NOT_FOUND` | Unknown category id/code |
| 404 | `NOT_FOUND` | Unknown route |
| 409 | `DUPLICATE_FLAT` | Flat number already exists |
| 409 | `DUPLICATE_CATEGORY` | Category already exists |
| 409 | `FLAT_HAS_COLLECTIONS` | Cannot delete a flat that has money recorded |
| 409 | `CATEGORY_IN_USE` | Cannot delete a category used by expenses |
| 409 | `INTEGRITY_ERROR` | Database constraint violated |
| 422 | `VALIDATION_ERROR` | Bad body/query — negative amount, future date, bad enum, missing field |
| 500 | `INTERNAL_ERROR` / `DATABASE_ERROR` | Unexpected failure |

---

## 4. Meta & health

### `GET /api/meta`
**Purpose:** every dropdown value in one call. Fetch once at app start and cache.

**Request:** none

**Response**
```json
{ "success": true, "data": {
  "app_name": "Ganpati Utsav Management API",
  "app_version": "1.0.0",
  "environment": "development",
  "currency": "INR",
  "currency_symbol": "₹",
  "payment_methods": [
    { "value": "CASH", "label": "Cash" },
    { "value": "UPI", "label": "UPI" },
    { "value": "BANK_TRANSFER", "label": "Bank Transfer" },
    { "value": "OTHER", "label": "Other" }],
  "collection_statuses": [
    { "value": "PENDING", "label": "Pending" },
    { "value": "CONFIRMED", "label": "Confirmed" },
    { "value": "CANCELLED", "label": "Cancelled" }],
  "wings": ["A", "B"],
  "expense_categories": [
    { "id": 1, "code": "DECORATION", "name": "Decoration",
      "description": "Mandap, lights, flowers, backdrop",
      "is_active": true, "sort_order": 10, "is_system": true,
      "created_at": "2026-08-15T09:00:00Z", "updated_at": "2026-08-15T09:00:00Z" }],
  "default_page_size": 20,
  "max_page_size": 100
}, "message": "Metadata fetched successfully" }
```

**Errors:** `500`

### `GET /api/health`
**Purpose:** liveness check including a real database round trip. Good for a "server unreachable" screen.

**Response**
```json
{ "success": true, "data": {
  "status": "ok", "database": "connected",
  "environment": "development", "version": "1.0.0"
}, "message": "Service is healthy" }
```
If the database is down: `status: "degraded"`, `database: "unavailable"` (still HTTP 200).

---

## 5. Dashboard

### `GET /api/dashboard`
**Purpose:** **one call renders the entire home screen.** Totals, balance, participation, charts and recent activity.

**Request:** none

**Response** (real values from a test run)
```json
{ "success": true, "data": {
  "currency": "INR",
  "currency_symbol": "₹",

  "total_collection": 4500.0,
  "total_expenses": 2300.0,
  "remaining_balance": 2200.0,
  "pending_collection_amount": 0.0,

  "total_flats": 24,
  "active_flats": 24,
  "flats_contributed": 2,
  "flats_not_contributed": 22,
  "collection_percentage": 8.33,
  "expense_percentage": 51.11,

  "collection_count": 2,
  "expense_count": 2,
  "average_contribution": 2250.0,

  "top_expense_categories": [
    { "category_id": 1, "category_code": "DECORATION", "category_name": "Decoration",
      "total": 1500.0, "count": 1, "percentage": 65.22 }],
  "collection_by_payment_method": [
    { "payment_method": "CASH", "label": "Cash", "total": 1500.0, "count": 1 },
    { "payment_method": "UPI", "label": "UPI", "total": 3000.0, "count": 1 },
    { "payment_method": "BANK_TRANSFER", "label": "Bank Transfer", "total": 0.0, "count": 0 },
    { "payment_method": "OTHER", "label": "Other", "total": 0.0, "count": 0 }],
  "collection_by_wing": [
    { "wing": "A", "total": 3000.0, "count": 1, "flats_total": 12,
      "flats_contributed": 1, "flats_pending": 11 },
    { "wing": "B", "total": 1500.0, "count": 1, "flats_total": 12,
      "flats_contributed": 1, "flats_pending": 11 }],

  "recent_collections": [ /* CollectionRead objects, newest first */ ],
  "recent_expenses":    [ /* ExpenseRead objects, newest first */ ],

  "flat_config_warning": null
}, "message": "Dashboard data fetched successfully" }
```

**Notes**
* `remaining_balance` = `total_collection − total_expenses`, recomputed on every request. It is never stored, so it can never be stale.
* `collection_percentage` = share of flats that paid. `expense_percentage` = share of collected money already spent.
* `by_payment_method` always returns **all four** methods (zeros included) so chart series stay stable.
* `flat_config_warning` is `null` while configuration is consistent; if it is ever non-null, show it as a warning banner.

**Errors:** `500`

---

## 6. Flats

The society has **24 flats: A1–A12 and B1–B12**, returned in natural order (A1, A2, … A10, A11, A12, B1, …).

### `GET /api/flats`
**Purpose:** the flat register. Small and stable — fetch once and cache.

**Query:** `wing` (`A`/`B`), `is_active` (bool), `search` (matches number, name, owner, phone). Not paginated.

**Response**
```json
{ "success": true, "data": {
  "items": [
    { "id": 1, "wing": "A", "flat_number": "A1", "display_name": "A1",
      "owner_name": null, "phone": null, "notes": null,
      "is_active": true, "sort_order": 1,
      "created_at": "2026-08-15T09:00:00Z", "updated_at": "2026-08-15T09:00:00Z" }],
  "total": 24,
  "wings": ["A", "B"]
}, "message": "Flats fetched successfully" }
```

**Errors:** `400 INVALID_WING`

### `GET /api/flats/{id}`
**Purpose:** one flat. **Response:** `data` = a single flat object as above.
**Errors:** `404 FLAT_NOT_FOUND`

### `GET /api/flats/{id}/collections`
**Purpose:** flat detail screen — every contribution from one flat plus its total.

**Response**
```json
{ "success": true, "data": {
  "flat": { "id": 1, "wing": "A", "flat_number": "A1", "display_name": "A1" },
  "total_amount": 3000.0,
  "collection_count": 2,
  "collections": [ /* CollectionRead objects, newest first */ ]
}, "message": "Flat collections fetched successfully" }
```
`total_amount` counts `CONFIRMED` rows only.

**Errors:** `404 FLAT_NOT_FOUND`

### `GET /api/flats/config`
**Purpose:** sanity check of the flat configuration. Useful on an admin/settings screen.

**Response**
```json
{ "success": true, "data": {
  "wings": [{ "code": "A", "configured_flat_count": 12, "existing_flat_count": 12 },
            { "code": "B", "configured_flat_count": 12, "existing_flat_count": 12 }],
  "configured_flat_count": 24,
  "existing_flat_count": 24,
  "expected_total_flats": 24,
  "matches_expectation": true,
  "discrepancy": 0,
  "message": "Flat configuration matches the expected total of 24 flats.",
  "how_to_fix": []
}, "message": "Flat configuration matches the expected total of 24 flats." }
```

### `POST /api/flats` → `201`
**Purpose:** add a flat.

**Request** (only `wing` and `flat_number` required)
```json
{ "wing": "A", "flat_number": "A13", "display_name": "A13",
  "owner_name": "Ramesh Patil", "phone": "9876543210", "notes": null }
```
`display_name` defaults to `flat_number`. `phone` must be a valid 10-digit Indian mobile (optionally `+91`).

**Response:** `data` = the created flat.
**Errors:** `409 DUPLICATE_FLAT`, `400 INVALID_WING`, `422 VALIDATION_ERROR`

### `POST /api/flats/bulk` → `201`
**Purpose:** add several flats at once.

**Request**
```json
{ "flats": [{ "wing": "A", "flat_number": "A13" },
            { "wing": "A", "flat_number": "A14" }],
  "skip_existing": true }
```

**Response**
```json
{ "success": true, "data": {
  "created": [ /* flat objects */ ],
  "skipped": ["A1"],
  "created_count": 2,
  "skipped_count": 1
}, "message": "2 flat(s) created, 1 skipped" }
```

### `PUT /api/flats/{id}`  (`PATCH` is an identical alias)
**Purpose:** update a flat. **Partial** — send only the fields that change.

**Request**
```json
{ "owner_name": "Sunny Mane", "phone": "9876500000", "is_active": true }
```
**Response:** `data` = the updated flat.
**Errors:** `404 FLAT_NOT_FOUND`, `409 DUPLICATE_FLAT`, `400 INVALID_WING`, `422 VALIDATION_ERROR`

### `DELETE /api/flats/{id}`
**Purpose:** remove a flat.

**Response:** `{ "success": true, "data": { "id": 5, "deleted": true }, "message": "Flat deleted successfully" }`

**Errors:** `404 FLAT_NOT_FOUND`, `409 FLAT_HAS_COLLECTIONS` —
```json
{ "success": false,
  "message": "Flat A1 has 1 collection(s) recorded and cannot be deleted. Deactivate it instead (PATCH /api/flats/{id} with is_active=false).",
  "error": "FLAT_HAS_COLLECTIONS", "details": { "collection_count": 1 } }
```

---

## 7. Collections (contributions)

Every contribution is one row. Totals are always derived from these rows, so history stays editable.

### `POST /api/collections` → `201`
**Purpose:** record a payment from a flat.

**Request** — required: `flat_id`, `amount` (> 0), `payment_method`
```json
{ "flat_id": 1,
  "amount": 2500,
  "payment_method": "UPI",
  "collected_on": "2026-08-15",
  "status": "CONFIRMED",
  "reference_no": "UPI-8890123",
  "collected_by": "Sunny",
  "notes": "Ganpati contribution" }
```
Defaults: `collected_on` = today, `status` = `CONFIRMED`.

**Response**
```json
{ "success": true, "data": {
  "id": 1,
  "flat_id": 1,
  "amount": 2500.0,
  "payment_method": "UPI",
  "payment_method_label": "UPI",
  "status": "CONFIRMED",
  "collected_on": "2026-08-15",
  "reference_no": "UPI-8890123",
  "collected_by": "Sunny",
  "notes": "Ganpati contribution",
  "flat": { "id": 1, "wing": "A", "flat_number": "A1", "display_name": "A1" },
  "created_at": "2026-08-15T09:12:00Z",
  "updated_at": "2026-08-15T09:12:00Z"
}, "message": "Collection created successfully" }
```

**Errors**
* `404 FLAT_NOT_FOUND` — `"Flat with id 9999 does not exist"`
* `422 VALIDATION_ERROR` — amount ≤ 0 (`"amount: Input should be greater than 0"`), future date, bad enum (`"payment_method: Input should be 'CASH', 'UPI', 'BANK_TRANSFER' or 'OTHER'"`), missing field

### `GET /api/collections`
**Purpose:** paginated, filterable list.

**Query:** `page` (default 1), `limit` (default 20, max 100), `flat_id`, `wing`, `payment_method`, `status`, `date_from`, `date_to`, `min_amount`, `max_amount`, `search` (notes, reference, collected_by, flat number, owner)

Examples
```
GET /api/collections?page=1&limit=20
GET /api/collections?wing=A
GET /api/collections?payment_method=UPI&date_from=2026-08-01&date_to=2026-08-31
GET /api/collections?flat_id=1
```

**Response:** paginated envelope of the object above, newest first.
**Errors:** `400 INVALID_WING`, `400 INVALID_DATE_RANGE`, `422 VALIDATION_ERROR`

### `GET /api/collections/{id}`
**Response:** `data` = one collection object. **Errors:** `404 COLLECTION_NOT_FOUND`

### `PUT /api/collections/{id}`  (`PATCH` alias)
**Purpose:** correct an entry. **Partial** — only what you send changes.

**Request**
```json
{ "amount": 3000, "payment_method": "CASH", "audit_note": "Corrected receipt amount" }
```
`audit_note` is optional and is stored in the change history. Every field of `POST` may be updated, including `flat_id` and `status`.

**Response:** `data` = the updated collection. Totals and balance reflect the change immediately.
**Errors:** `404 COLLECTION_NOT_FOUND`, `404 FLAT_NOT_FOUND`, `422 VALIDATION_ERROR`

### `DELETE /api/collections/{id}`
**Query:** `reason` (optional, stored in the audit log)

**Response:** `{ "success": true, "data": { "id": 1, "deleted": true }, "message": "Collection deleted successfully" }`
The deleted row is preserved as a snapshot in the audit log.
**Errors:** `404 COLLECTION_NOT_FOUND`

### `GET /api/collections/summary`
**Purpose:** the collection report screen. **Query:** `date_from`, `date_to` (both optional)

**Response**
```json
{ "success": true, "data": {
  "total_collection": 4500.0,
  "pending_amount": 0.0,
  "cancelled_amount": 0.0,
  "collection_count": 2,
  "total_flats": 24,
  "flats_contributed": 2,
  "flats_not_contributed": 22,
  "contribution_percentage": 8.33,
  "average_per_contributing_flat": 2250.0,
  "highest_contribution": 3000.0,
  "total_cash": 1500.0,
  "total_upi": 3000.0,
  "total_bank_transfer": 0.0,
  "total_other": 0.0,
  "by_payment_method": [{ "payment_method": "CASH", "label": "Cash", "total": 1500.0, "count": 1 }],
  "by_status":         [{ "status": "CONFIRMED", "total": 4500.0, "count": 2 }],
  "by_wing":           [{ "wing": "A", "total": 3000.0, "count": 1, "flats_total": 12,
                          "flats_contributed": 1, "flats_pending": 11 }],
  "by_flat":           [{ "flat_id": 1, "wing": "A", "flat_number": "A1", "display_name": "A1",
                          "owner_name": null, "total_amount": 3000.0, "collection_count": 1,
                          "has_contributed": true, "last_collected_on": "2026-08-15" }]
}, "message": "Collection summary generated successfully" }
```
`by_flat` contains **all 24 flats**, including those with `total_amount: 0.0` / `has_contributed: false`.

**Errors:** `400 INVALID_DATE_RANGE`

### `GET /api/collections/by-flat`
**Purpose:** "how much has each flat paid" — just the `by_flat` list.
**Query:** `date_from`, `date_to`
**Response:** `{ "items": [ /* FlatContribution */ ], "total": 24 }`

### `GET /api/collections/pending-flats`
**Purpose:** "who hasn't paid yet" screen.

**Response**
```json
{ "success": true, "data": {
  "items": [{ "id": 2, "wing": "A", "flat_number": "A2", "display_name": "A2" }],
  "total": 22
}, "message": "22 flat(s) have not contributed yet" }
```

### `GET /api/collections/{id}/history`
**Purpose:** change history of one contribution — see §10.

---

## 8. Expenses

### `POST /api/expenses` → `201`
**Purpose:** record a spend.

**Request** — required: `title`, `amount` (> 0), `payment_method`, and **either** `category_code` **or** `category_id`
```json
{ "title": "Decoration material",
  "description": "Mandap flowers and lights",
  "amount": 1200,
  "payment_method": "UPI",
  "category_code": "DECORATION",
  "spent_on": "2026-08-15",
  "vendor": "Sai Decorators",
  "reference_no": "BILL-104",
  "paid_by": "Sunny",
  "notes": null }
```
`spent_on` defaults to today.

**Response**
```json
{ "success": true, "data": {
  "id": 1,
  "title": "Decoration material",
  "description": "Mandap flowers and lights",
  "amount": 1200.0,
  "payment_method": "UPI",
  "payment_method_label": "UPI",
  "category_id": 1,
  "category_code": "DECORATION",
  "category_name": "Decoration",
  "spent_on": "2026-08-15",
  "vendor": "Sai Decorators",
  "reference_no": "BILL-104",
  "paid_by": "Sunny",
  "notes": null,
  "category": { "id": 1, "code": "DECORATION", "name": "Decoration",
                "description": "Mandap, lights, flowers, backdrop",
                "is_active": true, "sort_order": 10, "is_system": true,
                "created_at": "…", "updated_at": "…" },
  "created_at": "2026-08-15T09:20:00Z",
  "updated_at": "2026-08-15T09:20:00Z"
}, "message": "Expense created successfully" }
```
`category_code` / `category_name` are flattened shortcuts — use them in list UIs and ignore the nested `category` object unless you need it.

**Errors**
* `422 VALIDATION_ERROR` — neither category sent: `"either category_id or category_code is required"`; amount ≤ 0; future date; `title` shorter than 2 characters
* `404 CATEGORY_NOT_FOUND` — `"Expense category 'NOPE' does not exist"`

### `GET /api/expenses`
**Purpose:** the expense log / history screen. Paginated.

**Query:** `page`, `limit`, `category` (**code**, e.g. `DECORATION`), `category_id`, `payment_method`, `date_from`, `date_to`, `min_amount`, `max_amount`, `search` (title, description, vendor, reference, notes, paid_by)

Examples
```
GET /api/expenses?page=1&limit=20
GET /api/expenses?category=DECORATION
GET /api/expenses?search=mandap
GET /api/expenses?payment_method=CASH&date_from=2026-08-01
```

**Response:** paginated envelope, newest first.
**Errors:** `400 INVALID_DATE_RANGE`, `422 VALIDATION_ERROR`

### `GET /api/expenses/{id}`
**Response:** `data` = one expense object. **Errors:** `404 EXPENSE_NOT_FOUND`

### `PUT /api/expenses/{id}`  (`PATCH` alias)
**Purpose:** correct an expense. **Partial**.

**Request**
```json
{ "amount": 1500, "audit_note": "Vendor revised the bill" }
```
Fields you omit are untouched. `category_code` or `category_id` may be sent to re-categorise.

**Response:** `data` = the updated expense. Balance updates immediately.
**Errors:** `404 EXPENSE_NOT_FOUND`, `404 CATEGORY_NOT_FOUND`, `422 VALIDATION_ERROR`

### `DELETE /api/expenses/{id}`
**Query:** `reason` (optional, stored in the audit log)
**Response:** `{ "success": true, "data": { "id": 1, "deleted": true }, "message": "Expense deleted successfully" }`
**Errors:** `404 EXPENSE_NOT_FOUND`

### `GET /api/expenses/summary`
**Purpose:** expense report screen. **Query:** `date_from`, `date_to`

**Response**
```json
{ "success": true, "data": {
  "total_expenses": 2300.0,
  "expense_count": 2,
  "average_expense": 1150.0,
  "highest_expense": 1500.0,
  "total_cash": 800.0,
  "total_upi": 1500.0,
  "total_bank_transfer": 0.0,
  "total_other": 0.0,
  "by_category": [
    { "category_id": 1, "category_code": "DECORATION", "category_name": "Decoration",
      "total": 1500.0, "count": 1, "percentage": 65.22 },
    { "category_id": 3, "category_code": "SOUND", "category_name": "Sound",
      "total": 800.0, "count": 1, "percentage": 34.78 }],
  "by_payment_method": [
    { "payment_method": "CASH", "label": "Cash", "total": 800.0, "count": 1 }]
}, "message": "Expense summary generated successfully" }
```
`by_category` is sorted by amount descending and omits categories with no expenses.

### `GET /api/expenses/{id}/history`
**Purpose:** change history of one expense — see §10.

---

## 9. Expense categories

Seeded and ready to use: `DECORATION`, `FOOD`, `SOUND`, `ELECTRICITY`, `POOJA`, `PRASAD`, `CLEANING`, `TRANSPORTATION`, `ADVERTISEMENT`, `MISCELLANEOUS`.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/api/expense-categories` | List. Query: `is_active`, `search`. Returns `{ items: [...], total }` |
| `GET` | `/api/expense-categories/{id}` | One category |
| `POST` | `/api/expense-categories` | Create → `201` |
| `PUT` | `/api/expense-categories/{id}` | Update (partial) |
| `DELETE` | `/api/expense-categories/{id}` | Delete |

**Create request** — `code` is derived from `name` when omitted (`"Generator Rent"` → `GENERATOR_RENT`)
```json
{ "name": "Generator Rent", "description": null, "is_active": true, "sort_order": 110 }
```

**Category object**
```json
{ "id": 11, "code": "GENERATOR_RENT", "name": "Generator Rent",
  "description": null, "is_active": true, "sort_order": 110, "is_system": false,
  "created_at": "…", "updated_at": "…" }
```

**Notes:** `code` is immutable — it is the stable key you filter expenses by. `is_system: true` marks the 10 seeded categories.

**Errors:** `409 DUPLICATE_CATEGORY`, `409 CATEGORY_IN_USE` (delete blocked while expenses reference it), `404 CATEGORY_NOT_FOUND`, `422 VALIDATION_ERROR`

---

## 10. Finance & change history

### `GET /api/finance/summary`
**Purpose:** the accounts screen. **Query:** `date_from`, `date_to`

**Response**
```json
{ "success": true, "data": {
  "total_collection": 4500.0,
  "total_expenses": 2300.0,
  "remaining_balance": 2200.0,
  "currency": "INR",
  "currency_symbol": "₹",
  "collection_count": 2,
  "expense_count": 2,
  "pending_collection_amount": 0.0,
  "utilisation_percentage": 51.11,
  "collection_by_payment_method": [ /* all 4 methods */ ],
  "collection_by_wing":           [ /* per wing */ ],
  "expenses_by_category":         [ /* CategoryTotal */ ],
  "expenses_by_payment_method":   [ /* all 4 methods */ ],
  "recent_collections":           [ /* newest 5 */ ],
  "recent_expenses":              [ /* newest 5 */ ]
}, "message": "Financial summary generated successfully" }
```

### `GET /api/finance/balance`
**Purpose:** lightweight widget — just the three headline numbers. Cheapest way to refresh a balance card.

**Response**
```json
{ "success": true, "data": {
  "total_collection": 4500.0,
  "total_expenses": 2300.0,
  "remaining_balance": 2200.0
}, "message": "Balance calculated successfully" }
```

> `remaining_balance` is computed from the transaction rows on every request. `/api/dashboard`, `/api/finance/summary` and `/api/finance/balance` can never disagree.

### `GET /api/collections/{id}/history` · `GET /api/expenses/{id}/history`
**Purpose:** "who changed what" on a single record.

**Response**
```json
{ "success": true, "data": {
  "entity_type": "EXPENSE",
  "entity_id": 1,
  "items": [
    { "id": 4, "entity_type": "EXPENSE", "entity_id": 1, "action": "UPDATE",
      "changes": { "amount": { "old": "1200.00", "new": "1500.00" } },
      "snapshot": { "id": 1, "title": "Decoration material", "amount": "1500.00" },
      "actor": "Sunny", "note": "Vendor revised the bill",
      "created_at": "2026-08-15T09:25:00Z" },
    { "id": 3, "action": "CREATE", "changes": null, "snapshot": { }, "actor": "Sunny",
      "note": null, "created_at": "2026-08-15T09:20:00Z" }],
  "total": 2
}, "message": "Expense history fetched successfully" }
```
Newest first. `changes` is `null` for `CREATE`/`DELETE`. An update that changes nothing is not logged. Amounts inside `changes`/`snapshot` are **strings** to preserve exact precision.

**Errors:** `404 EXPENSE_NOT_FOUND` / `404 COLLECTION_NOT_FOUND`

### `GET /api/audit-logs`
**Purpose:** global activity feed. Paginated.
**Query:** `entity_type` (`FLAT`|`COLLECTION`|`EXPENSE`|`EXPENSE_CATEGORY`), `entity_id`, `action` (`CREATE`|`UPDATE`|`DELETE`), `page`, `limit`
**Response:** paginated envelope of the audit objects above.

---

## 11. Screen → endpoint map

| Screen | Call |
|---|---|
| App startup (cache dropdowns) | `GET /api/meta` |
| Home / dashboard | `GET /api/dashboard` |
| Flat list | `GET /api/flats` (cache) |
| Flat detail | `GET /api/flats/{id}/collections` |
| Add contribution | `POST /api/collections` |
| Edit contribution | `PUT /api/collections/{id}` |
| Collection list + filters | `GET /api/collections?...` |
| Who hasn't paid | `GET /api/collections/pending-flats` |
| Collection report | `GET /api/collections/summary` |
| Add expense | `POST /api/expenses` |
| Expense log + search | `GET /api/expenses?...` |
| Edit expense | `PUT /api/expenses/{id}` |
| Expense report | `GET /api/expenses/summary` |
| Accounts / balance | `GET /api/finance/summary` or `/api/finance/balance` |
| Record change history | `GET /api/expenses/{id}/history` |
| Activity feed | `GET /api/audit-logs` |

---

## 12. Dart client skeleton

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

/// Thrown for every non-success response. Branch on [code], show [message].
class ApiException implements Exception {
  final String code;      // e.g. FLAT_NOT_FOUND
  final String message;   // safe to show to the user
  final int statusCode;
  final dynamic details;  // field errors for VALIDATION_ERROR
  ApiException(this.code, this.message, this.statusCode, this.details);
  @override
  String toString() => message;
}

class GanpatiApi {
  GanpatiApi({http.Client? client, this.base = 'http://10.0.2.2:8000/api'})
      : _client = client ?? http.Client();

  final http.Client _client;
  final String base;
  static const _json = {'Content-Type': 'application/json'};

  /// Unwraps {success, data, message} and throws ApiException on failure.
  Future<T> _send<T>(Future<http.Response> req, T Function(dynamic) parse) async {
    final res = await req;
    final body = jsonDecode(utf8.decode(res.bodyBytes)) as Map<String, dynamic>;
    if (body['success'] != true) {
      throw ApiException(
        body['error'] as String? ?? 'UNKNOWN',
        body['message'] as String? ?? 'Something went wrong',
        res.statusCode,
        body['details'],
      );
    }
    return parse(body['data']);
  }

  Uri _uri(String path, [Map<String, dynamic>? query]) =>
      Uri.parse('$base$path').replace(
        queryParameters: query?.map((k, v) => MapEntry(k, '$v')),
      );

  // ---- reads ----
  Future<Map<String, dynamic>> dashboard() =>
      _send(_client.get(_uri('/dashboard')), (d) => d as Map<String, dynamic>);

  Future<Map<String, dynamic>> balance() =>
      _send(_client.get(_uri('/finance/balance')), (d) => d as Map<String, dynamic>);

  Future<List<dynamic>> flats({String? wing}) => _send(
        _client.get(_uri('/flats', {if (wing != null) 'wing': wing})),
        (d) => d['items'] as List<dynamic>,
      );

  Future<Map<String, dynamic>> expenses({int page = 1, int limit = 20, String? category, String? search}) =>
      _send(
        _client.get(_uri('/expenses', {
          'page': page, 'limit': limit,
          if (category != null) 'category': category,
          if (search != null) 'search': search,
        })),
        (d) => d as Map<String, dynamic>, // { items: [...], pagination: {...} }
      );

  // ---- writes (pass actor to record who did it) ----
  Future<Map<String, dynamic>> addCollection({
    required int flatId,
    required num amount,
    required String paymentMethod,
    String? referenceNo,
    String? notes,
    String? actor,
  }) =>
      _send(
        _client.post(_uri('/collections'),
            headers: {..._json, if (actor != null) 'X-Actor': actor},
            body: jsonEncode({
              'flat_id': flatId,
              'amount': amount,
              'payment_method': paymentMethod,
              if (referenceNo != null) 'reference_no': referenceNo,
              if (notes != null) 'notes': notes,
            })),
        (d) => d as Map<String, dynamic>,
      );

  Future<Map<String, dynamic>> addExpense({
    required String title,
    required num amount,
    required String paymentMethod,
    required String categoryCode,
    String? vendor,
    String? description,
    String? actor,
  }) =>
      _send(
        _client.post(_uri('/expenses'),
            headers: {..._json, if (actor != null) 'X-Actor': actor},
            body: jsonEncode({
              'title': title,
              'amount': amount,
              'payment_method': paymentMethod,
              'category_code': categoryCode,
              if (vendor != null) 'vendor': vendor,
              if (description != null) 'description': description,
            })),
        (d) => d as Map<String, dynamic>,
      );

  /// Partial update — send only what changed.
  Future<Map<String, dynamic>> updateExpense(int id, Map<String, dynamic> changes, {String? auditNote}) =>
      _send(
        _client.put(_uri('/expenses/$id'),
            headers: _json,
            body: jsonEncode({...changes, if (auditNote != null) 'audit_note': auditNote})),
        (d) => d as Map<String, dynamic>,
      );

  Future<void> deleteExpense(int id, {String? reason}) => _send(
        _client.delete(_uri('/expenses/$id', {if (reason != null) 'reason': reason})),
        (_) => null,
      );
}
```

**Error handling pattern**

```dart
try {
  await api.addCollection(flatId: 1, amount: 2500, paymentMethod: 'UPI');
} on ApiException catch (e) {
  switch (e.code) {
    case 'FLAT_NOT_FOUND':   showError('That flat no longer exists.');  break;
    case 'VALIDATION_ERROR': showError(e.message);                      break;
    default:                 showError('Could not save. Please retry.');
  }
}
```

---

## 13. Quick reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/meta` | All dropdown values |
| GET | `/api/health` | Liveness + DB check |
| GET | `/api/dashboard` | Whole home screen in one call |
| GET | `/api/flats` | Flat register (24 flats) |
| GET | `/api/flats/{id}` | One flat |
| GET | `/api/flats/{id}/collections` | Flat's contributions + total |
| GET | `/api/flats/config` | Flat-count sanity check |
| POST | `/api/flats` | Create flat |
| POST | `/api/flats/bulk` | Create many flats |
| PUT/PATCH | `/api/flats/{id}` | Update flat (partial) |
| DELETE | `/api/flats/{id}` | Delete flat |
| POST | `/api/collections` | Record a contribution |
| GET | `/api/collections` | List (paginated + filters) |
| GET | `/api/collections/{id}` | One contribution |
| PUT/PATCH | `/api/collections/{id}` | Update (partial) |
| DELETE | `/api/collections/{id}` | Delete |
| GET | `/api/collections/summary` | Totals by wing/flat/method |
| GET | `/api/collections/by-flat` | Amount per flat |
| GET | `/api/collections/pending-flats` | Flats that haven't paid |
| GET | `/api/collections/{id}/history` | Change history |
| POST | `/api/expenses` | Record a spend |
| GET | `/api/expenses` | Expense log (paginated + search) |
| GET | `/api/expenses/{id}` | One expense |
| PUT/PATCH | `/api/expenses/{id}` | Update (partial) |
| DELETE | `/api/expenses/{id}` | Delete |
| GET | `/api/expenses/summary` | Totals by category/method |
| GET | `/api/expenses/{id}/history` | Change history |
| GET | `/api/expense-categories` | List categories |
| GET | `/api/expense-categories/{id}` | One category |
| POST | `/api/expense-categories` | Create category |
| PUT | `/api/expense-categories/{id}` | Update category |
| DELETE | `/api/expense-categories/{id}` | Delete category |
| GET | `/api/finance/summary` | Full financial report |
| GET | `/api/finance/balance` | Collection / expenses / balance |
| GET | `/api/audit-logs` | Global change feed |
