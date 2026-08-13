"""Finance summary, dashboard and money-arithmetic tests."""

from __future__ import annotations

from decimal import Decimal

from tests.conftest import data_of


async def _seed_transactions(client) -> None:
    await client.post(
        "/api/collections", json={"flat_id": 1, "amount": 30000, "payment_method": "UPI"}
    )
    await client.post(
        "/api/collections", json={"flat_id": 2, "amount": 20000, "payment_method": "CASH"}
    )
    await client.post(
        "/api/expenses",
        json={
            "title": "Decoration material",
            "amount": 3500,
            "payment_method": "UPI",
            "category_code": "DECORATION",
        },
    )
    await client.post(
        "/api/expenses",
        json={
            "title": "Sound system",
            "amount": 9000,
            "payment_method": "CASH",
            "category_code": "SOUND",
        },
    )


async def test_finance_summary_balance_is_calculated(client, seeded):
    await _seed_transactions(client)
    data = data_of(await client.get("/api/finance/summary"))

    assert data["total_collection"] == 50000.0
    assert data["total_expenses"] == 12500.0
    assert data["remaining_balance"] == 37500.0
    assert data["collection_count"] == 2
    assert data["expense_count"] == 2
    assert data["utilisation_percentage"] == 25.0
    assert len(data["recent_collections"]) == 2
    assert len(data["recent_expenses"]) == 2


async def test_balance_reacts_to_edits_and_deletes(client, seeded):
    await _seed_transactions(client)
    expenses = data_of(await client.get("/api/expenses"))
    first = expenses["items"][0]

    await client.put(f"/api/expenses/{first['id']}", json={"amount": 1})
    after_edit = data_of(await client.get("/api/finance/balance"))
    assert after_edit["total_expenses"] == 12500.0 - first["amount"] + 1
    assert (
        after_edit["remaining_balance"]
        == after_edit["total_collection"] - after_edit["total_expenses"]
    )

    await client.delete(f"/api/expenses/{first['id']}")
    after_delete = data_of(await client.get("/api/finance/balance"))
    assert after_delete["total_expenses"] == 12500.0 - first["amount"]


async def test_empty_database_returns_zeroes(client, seeded):
    data = data_of(await client.get("/api/finance/summary"))
    assert data["total_collection"] == 0.0
    assert data["total_expenses"] == 0.0
    assert data["remaining_balance"] == 0.0
    assert data["utilisation_percentage"] == 0.0  # no division by zero


async def test_balance_can_go_negative(client, seeded):
    await client.post(
        "/api/collections", json={"flat_id": 1, "amount": 1000, "payment_method": "CASH"}
    )
    await client.post(
        "/api/expenses",
        json={
            "title": "Big spend",
            "amount": 2500,
            "payment_method": "CASH",
            "category_code": "FOOD",
        },
    )
    data = data_of(await client.get("/api/finance/balance"))
    assert data["remaining_balance"] == -1500.0


async def test_decimal_precision_is_preserved(client, seeded):
    """Paise must survive the round trip — 0.1 + 0.2 style float errors must not appear."""
    for amount in ("1000.10", "2000.20", "3000.05"):
        await client.post(
            "/api/collections",
            json={"flat_id": 1, "amount": amount, "payment_method": "CASH"},
        )
    data = data_of(await client.get("/api/finance/balance"))
    assert Decimal(str(data["total_collection"])) == Decimal("6000.35")


async def test_too_many_decimal_places_is_rejected(client, seeded):
    response = await client.post(
        "/api/collections", json={"flat_id": 1, "amount": "100.123", "payment_method": "CASH"}
    )
    assert response.status_code == 422


async def test_dashboard(client, seeded):
    await _seed_transactions(client)
    data = data_of(await client.get("/api/dashboard"))

    assert data["total_collection"] == 50000.0
    assert data["total_expenses"] == 12500.0
    assert data["remaining_balance"] == 37500.0
    assert data["total_flats"] == 24
    assert data["active_flats"] == 24
    assert data["flats_contributed"] == 2
    assert data["flats_not_contributed"] == 22
    assert data["collection_percentage"] == 8.33
    assert data["expense_percentage"] == 25.0
    assert data["average_contribution"] == 25000.0
    assert data["currency_symbol"] == "₹"
    assert len(data["recent_collections"]) == 2
    assert len(data["top_expense_categories"]) == 2
    # The 24-vs-28 discrepancy is surfaced to the app, not hidden.
    assert data["flat_config_warning"] is not None


async def test_dashboard_and_finance_agree(client, seeded):
    await _seed_transactions(client)
    dashboard = data_of(await client.get("/api/dashboard"))
    finance = data_of(await client.get("/api/finance/summary"))
    for key in ("total_collection", "total_expenses", "remaining_balance"):
        assert dashboard[key] == finance[key]


async def test_cancelled_collections_are_excluded(client, seeded):
    created = data_of(
        await client.post(
            "/api/collections", json={"flat_id": 1, "amount": 5000, "payment_method": "CASH"}
        )
    )
    await client.put(f"/api/collections/{created['id']}", json={"status": "CANCELLED"})
    data = data_of(await client.get("/api/finance/balance"))
    assert data["total_collection"] == 0.0


async def test_meta_endpoint(client, seeded):
    data = data_of(await client.get("/api/meta"))
    assert [option["value"] for option in data["payment_methods"]] == [
        "CASH",
        "UPI",
        "BANK_TRANSFER",
        "OTHER",
    ]
    assert data["wings"] == ["A", "B"]
    assert len(data["expense_categories"]) == 10


async def test_health_endpoint(client, seeded):
    data = data_of(await client.get("/api/health"))
    assert data["status"] == "ok"
    assert data["database"] == "connected"


async def test_unknown_route_returns_envelope(client, seeded):
    response = await client.get("/api/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"] == "NOT_FOUND"
