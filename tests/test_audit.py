"""Audit trail tests — requirement #9 (₹3000 changed to ₹3500 must be traceable)."""

from __future__ import annotations

from tests.conftest import data_of


async def test_expense_edit_is_recorded(client, seeded):
    created = data_of(
        await client.post(
            "/api/expenses",
            json={
                "title": "Decoration material",
                "amount": 3000,
                "payment_method": "UPI",
                "category_code": "DECORATION",
            },
        )
    )
    await client.put(
        f"/api/expenses/{created['id']}",
        json={"amount": 3500, "audit_note": "Vendor revised the bill"},
        headers={"X-Actor": "Sunny"},
    )

    history = data_of(await client.get(f"/api/expenses/{created['id']}/history"))
    assert history["total"] == 2  # CREATE + UPDATE

    update = next(row for row in history["items"] if row["action"] == "UPDATE")
    assert update["changes"]["amount"] == {"old": "3000.00", "new": "3500.00"}
    assert update["note"] == "Vendor revised the bill"
    assert update["actor"] == "Sunny"


async def test_no_op_update_is_not_logged(client, seeded):
    created = data_of(
        await client.post(
            "/api/collections", json={"flat_id": 1, "amount": 2500, "payment_method": "UPI"}
        )
    )
    await client.put(f"/api/collections/{created['id']}", json={"amount": 2500})
    history = data_of(await client.get(f"/api/collections/{created['id']}/history"))
    assert history["total"] == 1  # only the CREATE


async def test_delete_keeps_a_snapshot(client, seeded):
    created = data_of(
        await client.post(
            "/api/collections", json={"flat_id": 1, "amount": 2500, "payment_method": "CASH"}
        )
    )
    await client.delete(f"/api/collections/{created['id']}", params={"reason": "Duplicate entry"})

    logs = data_of(
        await client.get(
            "/api/audit-logs", params={"entity_type": "COLLECTION", "entity_id": created["id"]}
        )
    )
    delete_row = next(row for row in logs["items"] if row["action"] == "DELETE")
    assert delete_row["snapshot"]["amount"] == "2500.00"
    assert delete_row["note"] == "Duplicate entry"


async def test_audit_log_listing_is_filterable(client, seeded):
    await client.post(
        "/api/collections", json={"flat_id": 1, "amount": 100, "payment_method": "CASH"}
    )
    await client.post(
        "/api/expenses",
        json={"title": "Tea", "amount": 50, "payment_method": "CASH", "category_code": "FOOD"},
    )

    all_logs = data_of(await client.get("/api/audit-logs"))
    assert all_logs["pagination"]["total"] == 2

    only_expenses = data_of(await client.get("/api/audit-logs", params={"entity_type": "EXPENSE"}))
    assert only_expenses["pagination"]["total"] == 1
    assert only_expenses["items"][0]["action"] == "CREATE"
