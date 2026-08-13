"""Flat endpoint tests."""

from __future__ import annotations

from tests.conftest import data_of, error_of


async def test_list_flats_returns_all_seeded_flats(client, seeded):
    response = await client.get("/api/flats")
    assert response.status_code == 200
    data = data_of(response)
    assert data["total"] == 24
    assert data["wings"] == ["A", "B"]
    # Natural ordering: A1, A2, ... A10 (not A1, A10, A11).
    assert [flat["flat_number"] for flat in data["items"][:3]] == ["A1", "A2", "A3"]


async def test_filter_flats_by_wing(client, seeded):
    response = await client.get("/api/flats", params={"wing": "B"})
    data = data_of(response)
    assert data["total"] == 12
    assert {flat["wing"] for flat in data["items"]} == {"B"}


async def test_filter_flats_by_unknown_wing_is_rejected(client, seeded):
    response = await client.get("/api/flats", params={"wing": "Z"})
    assert response.status_code == 400
    assert error_of(response)["error"] == "INVALID_WING"


async def test_create_flat(client, seeded):
    payload = {
        "wing": "A",
        "flat_number": "A13",
        "owner_name": "Ramesh Patil",
        "phone": "9876543210",
    }
    response = await client.post("/api/flats", json=payload)
    assert response.status_code == 201
    data = data_of(response)
    assert data["flat_number"] == "A13"
    assert data["display_name"] == "A13"
    assert data["is_active"] is True


async def test_duplicate_flat_is_rejected(client, seeded):
    response = await client.post("/api/flats", json={"wing": "A", "flat_number": "A1"})
    assert response.status_code == 409
    body = error_of(response)
    assert body["error"] == "DUPLICATE_FLAT"
    assert "A1" in body["message"]


async def test_invalid_phone_is_rejected(client, seeded):
    response = await client.post(
        "/api/flats", json={"wing": "A", "flat_number": "A14", "phone": "12345"}
    )
    assert response.status_code == 422
    assert error_of(response)["error"] == "VALIDATION_ERROR"


async def test_get_missing_flat_returns_404(client, seeded):
    response = await client.get("/api/flats/9999")
    assert response.status_code == 404
    assert error_of(response)["error"] == "FLAT_NOT_FOUND"


async def test_update_flat(client, seeded):
    response = await client.put("/api/flats/1", json={"owner_name": "Sunny Mane"})
    data = data_of(response)
    assert data["owner_name"] == "Sunny Mane"
    assert data["flat_number"] == "A1"  # untouched fields stay as they were


async def test_delete_flat_without_collections(client, seeded):
    created = data_of(await client.post("/api/flats", json={"wing": "B", "flat_number": "B13"}))
    response = await client.delete(f"/api/flats/{created['id']}")
    assert response.status_code == 200
    assert data_of(response)["deleted"] is True
    assert (await client.get(f"/api/flats/{created['id']}")).status_code == 404


async def test_delete_flat_with_collections_is_blocked(client, seeded):
    await client.post(
        "/api/collections", json={"flat_id": 1, "amount": 500, "payment_method": "CASH"}
    )
    response = await client.delete("/api/flats/1")
    assert response.status_code == 409
    assert error_of(response)["error"] == "FLAT_HAS_COLLECTIONS"


async def test_flat_config_reports_the_24_vs_28_discrepancy(client, seeded):
    data = data_of(await client.get("/api/flats/config"))
    assert data["configured_flat_count"] == 24
    assert data["expected_total_flats"] == 28
    assert data["matches_expectation"] is False
    assert data["discrepancy"] == 4
    assert data["how_to_fix"]  # actionable instructions are present


async def test_bulk_create_skips_existing(client, seeded):
    payload = {
        "flats": [
            {"wing": "A", "flat_number": "A1"},  # already exists
            {"wing": "A", "flat_number": "A13"},  # new
            {"wing": "A", "flat_number": "A14"},  # new
        ],
        "skip_existing": True,
    }
    data = data_of(await client.post("/api/flats/bulk", json=payload))
    assert data["created_count"] == 2
    assert data["skipped"] == ["A1"]
