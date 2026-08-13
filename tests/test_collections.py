"""Collection endpoint tests."""

from __future__ import annotations

from datetime import date, timedelta

from tests.conftest import data_of, error_of


async def _create(client, **overrides) -> dict:
    payload = {"flat_id": 1, "amount": 2500, "payment_method": "UPI"}
    payload.update(overrides)
    response = await client.post("/api/collections", json=payload)
    assert response.status_code == 201, response.json()
    return data_of(response)


async def test_create_collection(client, seeded):
    data = await _create(client, notes="Ganpati contribution")
    assert data["amount"] == 2500.0
    assert data["payment_method"] == "UPI"
    assert data["payment_method_label"] == "UPI"
    assert data["status"] == "CONFIRMED"
    assert data["flat"]["flat_number"] == "A1"
    assert data["collected_on"] == date.today().isoformat()  # defaults to today


async def test_create_collection_for_missing_flat(client, seeded):
    response = await client.post(
        "/api/collections", json={"flat_id": 9999, "amount": 100, "payment_method": "CASH"}
    )
    assert response.status_code == 404
    body = error_of(response)
    assert body["error"] == "FLAT_NOT_FOUND"
    assert "9999" in body["message"]


async def test_negative_and_zero_amounts_are_rejected(client, seeded):
    for amount in (-100, 0):
        response = await client.post(
            "/api/collections", json={"flat_id": 1, "amount": amount, "payment_method": "CASH"}
        )
        assert response.status_code == 422
        assert error_of(response)["error"] == "VALIDATION_ERROR"


async def test_future_date_is_rejected(client, seeded):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    response = await client.post(
        "/api/collections",
        json={"flat_id": 1, "amount": 100, "payment_method": "CASH", "collected_on": tomorrow},
    )
    assert response.status_code == 422


async def test_invalid_payment_method_is_rejected(client, seeded):
    response = await client.post(
        "/api/collections", json={"flat_id": 1, "amount": 100, "payment_method": "BITCOIN"}
    )
    assert response.status_code == 422


async def test_missing_required_field_is_rejected(client, seeded):
    response = await client.post("/api/collections", json={"amount": 100})
    assert response.status_code == 422
    details = error_of(response)["details"]
    assert any(item["field"] == "flat_id" for item in details)


async def test_update_collection(client, seeded):
    created = await _create(client, amount=2000)
    response = await client.put(
        f"/api/collections/{created['id']}",
        json={"amount": 3000, "payment_method": "CASH", "audit_note": "Corrected receipt"},
    )
    data = data_of(response)
    assert data["amount"] == 3000.0
    assert data["payment_method"] == "CASH"
    assert data["flat_id"] == 1  # unchanged


async def test_update_missing_collection_returns_404(client, seeded):
    response = await client.put("/api/collections/999", json={"amount": 10})
    assert response.status_code == 404
    assert error_of(response)["error"] == "COLLECTION_NOT_FOUND"


async def test_delete_collection(client, seeded):
    created = await _create(client)
    assert (await client.delete(f"/api/collections/{created['id']}")).status_code == 200
    assert (await client.get(f"/api/collections/{created['id']}")).status_code == 404

    summary = data_of(await client.get("/api/collections/summary"))
    assert summary["total_collection"] == 0.0


async def test_list_filters_and_pagination(client, seeded):
    await _create(client, flat_id=1, amount=1000, payment_method="CASH")
    await _create(client, flat_id=2, amount=2000, payment_method="UPI")
    await _create(client, flat_id=13, amount=3000, payment_method="UPI")  # B1

    all_rows = data_of(await client.get("/api/collections"))
    assert all_rows["pagination"]["total"] == 3

    by_wing = data_of(await client.get("/api/collections", params={"wing": "B"}))
    assert by_wing["pagination"]["total"] == 1
    assert by_wing["items"][0]["flat"]["wing"] == "B"

    by_method = data_of(await client.get("/api/collections", params={"payment_method": "UPI"}))
    assert by_method["pagination"]["total"] == 2

    by_flat = data_of(await client.get("/api/collections", params={"flat_id": 1}))
    assert by_flat["pagination"]["total"] == 1

    page = data_of(await client.get("/api/collections", params={"page": 1, "limit": 2}))
    assert len(page["items"]) == 2
    assert page["pagination"]["pages"] == 2
    assert page["pagination"]["has_next"] is True


async def test_date_filtering(client, seeded):
    today = date.today()
    old = (today - timedelta(days=10)).isoformat()
    await _create(client, amount=1000, collected_on=old)
    await _create(client, amount=2000, collected_on=today.isoformat())

    recent = data_of(
        await client.get(
            "/api/collections", params={"date_from": (today - timedelta(days=1)).isoformat()}
        )
    )
    assert recent["pagination"]["total"] == 1
    assert recent["items"][0]["amount"] == 2000.0


async def test_reversed_date_range_is_rejected(client, seeded):
    response = await client.get(
        "/api/collections", params={"date_from": "2026-08-10", "date_to": "2026-08-01"}
    )
    assert response.status_code == 400
    assert error_of(response)["error"] == "INVALID_DATE_RANGE"


async def test_summary_totals_and_participation(client, seeded):
    await _create(client, flat_id=1, amount=2500, payment_method="CASH")
    await _create(client, flat_id=1, amount=500, payment_method="UPI")  # same flat twice
    await _create(client, flat_id=13, amount=3000, payment_method="BANK_TRANSFER")
    await _create(client, flat_id=14, amount=1000, payment_method="OTHER", status="PENDING")

    summary = data_of(await client.get("/api/collections/summary"))
    assert summary["total_collection"] == 6000.0  # PENDING excluded
    assert summary["pending_amount"] == 1000.0
    assert summary["collection_count"] == 3
    assert summary["total_flats"] == 24
    assert summary["flats_contributed"] == 2  # A1 and B1
    assert summary["flats_not_contributed"] == 22
    assert summary["total_cash"] == 2500.0
    assert summary["total_upi"] == 500.0
    assert summary["total_bank_transfer"] == 3000.0
    assert summary["total_other"] == 0.0  # the OTHER row is PENDING
    assert summary["highest_contribution"] == 3000.0

    wings = {row["wing"]: row for row in summary["by_wing"]}
    assert wings["A"]["total"] == 3000.0
    assert wings["A"]["flats_contributed"] == 1
    assert wings["A"]["flats_pending"] == 11
    assert wings["B"]["total"] == 3000.0

    a1 = next(row for row in summary["by_flat"] if row["flat_number"] == "A1")
    assert a1["total_amount"] == 3000.0
    assert a1["collection_count"] == 2
    assert a1["has_contributed"] is True

    a2 = next(row for row in summary["by_flat"] if row["flat_number"] == "A2")
    assert a2["total_amount"] == 0.0
    assert a2["has_contributed"] is False


async def test_pending_flats(client, seeded):
    await _create(client, flat_id=1)
    data = data_of(await client.get("/api/collections/pending-flats"))
    assert data["total"] == 23
    assert "A1" not in [flat["flat_number"] for flat in data["items"]]


async def test_collections_for_one_flat(client, seeded):
    await _create(client, flat_id=2, amount=1500)
    await _create(client, flat_id=2, amount=500)
    data = data_of(await client.get("/api/flats/2/collections"))
    assert data["collection_count"] == 2
    assert data["total_amount"] == 2000.0
    assert data["flat"]["flat_number"] == "A2"


async def test_by_flat_endpoint_lists_every_flat(client, seeded):
    await _create(client, flat_id=1, amount=2500)
    data = data_of(await client.get("/api/collections/by-flat"))
    assert data["total"] == 24
    assert sum(1 for row in data["items"] if row["has_contributed"]) == 1
