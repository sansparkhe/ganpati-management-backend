"""Expense and expense-category endpoint tests."""

from __future__ import annotations

from tests.conftest import data_of, error_of


async def _create(client, **overrides) -> dict:
    payload = {
        "title": "Decoration material",
        "amount": 3500,
        "payment_method": "UPI",
        "category_code": "DECORATION",
    }
    payload.update(overrides)
    response = await client.post("/api/expenses", json=payload)
    assert response.status_code == 201, response.json()
    return data_of(response)


async def test_create_expense(client, seeded):
    data = await _create(client, vendor="Sai Decorators")
    assert data["amount"] == 3500.0
    assert data["category_code"] == "DECORATION"
    assert data["category_name"] == "Decoration"
    assert data["payment_method_label"] == "UPI"


async def test_create_expense_with_category_id(client, seeded):
    categories = data_of(await client.get("/api/expense-categories"))
    food = next(row for row in categories["items"] if row["code"] == "FOOD")
    data = await _create(
        client, category_id=food["id"], category_code=None, title="Volunteer meals"
    )
    assert data["category_id"] == food["id"]


async def test_unknown_category_is_rejected(client, seeded):
    response = await client.post(
        "/api/expenses",
        json={"title": "Random", "amount": 10, "payment_method": "CASH", "category_code": "NOPE"},
    )
    assert response.status_code == 404
    assert error_of(response)["error"] == "CATEGORY_NOT_FOUND"


async def test_missing_category_is_rejected(client, seeded):
    response = await client.post(
        "/api/expenses", json={"title": "Random", "amount": 10, "payment_method": "CASH"}
    )
    assert response.status_code == 404


async def test_negative_amount_is_rejected(client, seeded):
    response = await client.post(
        "/api/expenses",
        json={"title": "Bad", "amount": -50, "payment_method": "CASH", "category_code": "FOOD"},
    )
    assert response.status_code == 422
    assert error_of(response)["error"] == "VALIDATION_ERROR"


async def test_update_expense(client, seeded):
    created = await _create(client, amount=3000)
    response = await client.put(
        f"/api/expenses/{created['id']}",
        json={"amount": 3500, "audit_note": "Vendor revised the bill"},
    )
    data = data_of(response)
    assert data["amount"] == 3500.0
    assert data["title"] == "Decoration material"  # untouched


async def test_update_expense_category(client, seeded):
    created = await _create(client)
    data = data_of(
        await client.put(f"/api/expenses/{created['id']}", json={"category_code": "SOUND"})
    )
    assert data["category_code"] == "SOUND"


async def test_delete_expense(client, seeded):
    created = await _create(client)
    assert (await client.delete(f"/api/expenses/{created['id']}")).status_code == 200
    assert (await client.get(f"/api/expenses/{created['id']}")).status_code == 404


async def test_missing_expense_returns_404(client, seeded):
    response = await client.get("/api/expenses/999")
    assert response.status_code == 404
    assert error_of(response)["error"] == "EXPENSE_NOT_FOUND"


async def test_filter_search_and_pagination(client, seeded):
    await _create(client, title="Mandap rent", amount=6000, category_code="DECORATION")
    await _create(
        client, title="Sound system", amount=4500, payment_method="CASH", category_code="SOUND"
    )
    await _create(
        client, title="Modak prasad", amount=1800, payment_method="CASH", category_code="PRASAD"
    )

    by_category = data_of(await client.get("/api/expenses", params={"category": "SOUND"}))
    assert by_category["pagination"]["total"] == 1

    by_method = data_of(await client.get("/api/expenses", params={"payment_method": "CASH"}))
    assert by_method["pagination"]["total"] == 2

    search = data_of(await client.get("/api/expenses", params={"search": "mandap"}))
    assert search["pagination"]["total"] == 1
    assert search["items"][0]["title"] == "Mandap rent"

    page = data_of(await client.get("/api/expenses", params={"page": 2, "limit": 2}))
    assert page["pagination"]["page"] == 2
    assert page["pagination"]["has_previous"] is True


async def test_expense_summary(client, seeded):
    await _create(client, amount=3500, category_code="DECORATION", payment_method="UPI")
    await _create(
        client, amount=6500, category_code="DECORATION", payment_method="CASH", title="Mandap"
    )
    await _create(client, amount=2000, category_code="SOUND", payment_method="CASH", title="DJ")

    summary = data_of(await client.get("/api/expenses/summary"))
    assert summary["total_expenses"] == 12000.0
    assert summary["expense_count"] == 3
    assert summary["average_expense"] == 4000.0
    assert summary["highest_expense"] == 6500.0
    assert summary["total_cash"] == 8500.0
    assert summary["total_upi"] == 3500.0

    decoration = next(row for row in summary["by_category"] if row["category_code"] == "DECORATION")
    assert decoration["total"] == 10000.0
    assert decoration["count"] == 2
    assert decoration["percentage"] == 83.33


# ------------------------------------------------------------- categories ---
async def test_default_categories_exist(client, seeded):
    data = data_of(await client.get("/api/expense-categories"))
    codes = {row["code"] for row in data["items"]}
    assert {"DECORATION", "FOOD", "SOUND", "POOJA", "MISCELLANEOUS"} <= codes
    assert data["total"] == 10


async def test_create_custom_category(client, seeded):
    response = await client.post("/api/expense-categories", json={"name": "Generator Rent"})
    assert response.status_code == 201
    data = data_of(response)
    assert data["code"] == "GENERATOR_RENT"  # derived from the name
    assert data["is_system"] is False


async def test_duplicate_category_is_rejected(client, seeded):
    response = await client.post("/api/expense-categories", json={"name": "Decoration"})
    assert response.status_code == 409
    assert error_of(response)["error"] == "DUPLICATE_CATEGORY"


async def test_category_in_use_cannot_be_deleted(client, seeded):
    created = await _create(client)
    response = await client.delete(f"/api/expense-categories/{created['category_id']}")
    assert response.status_code == 409
    assert error_of(response)["error"] == "CATEGORY_IN_USE"


async def test_unused_category_can_be_deleted(client, seeded):
    created = data_of(await client.post("/api/expense-categories", json={"name": "Temporary"}))
    assert (await client.delete(f"/api/expense-categories/{created['id']}")).status_code == 200
