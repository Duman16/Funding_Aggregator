import uuid

import pytest

from app.models.grant import Grant


async def _seed_grant(db_session, **kwargs) -> Grant:
    """Helper to insert a grant directly into test DB."""
    defaults = {
        "id": uuid.uuid4(),
        "external_id": str(uuid.uuid4()),
        "source": "test_source",
        "title": "Test Research Grant",
        "description": "Funding for advanced research in science and technology",
        "agency_name": "National Science Foundation",
        "url": "https://example.com/grant/1",
        "status": "open",
        "is_processed": True,
    }
    defaults.update(kwargs)
    grant = Grant(**defaults)
    db_session.add(grant)
    await db_session.commit()
    await db_session.refresh(grant)
    return grant


@pytest.mark.asyncio
async def test_list_grants_empty(client):
    resp = await client.get("/api/v1/grants")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert data["page"] == 1


@pytest.mark.asyncio
async def test_list_grants_with_data(client, db_session):
    await _seed_grant(db_session, title="Climate Research Grant")
    resp = await client.get("/api/v1/grants")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


@pytest.mark.asyncio
async def test_get_grant_by_id(client, db_session):
    grant = await _seed_grant(db_session, title="Specific Grant")
    resp = await client.get(f"/api/v1/grants/{grant.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Specific Grant"


@pytest.mark.asyncio
async def test_get_grant_not_found(client):
    resp = await client.get(f"/api/v1/grants/{uuid.uuid4()}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filter_by_status(client, db_session):
    await _seed_grant(db_session, status="open")
    await _seed_grant(db_session, status="closed")
    resp = await client.get("/api/v1/grants?status=open")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(g["status"] == "open" for g in items)


@pytest.mark.asyncio
async def test_filter_by_source(client, db_session):
    await _seed_grant(db_session, source="grants_gov")
    resp = await client.get("/api/v1/grants?source=grants_gov")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert all(g["source"] == "grants_gov" for g in items)


@pytest.mark.asyncio
async def test_pagination(client, db_session):
    for i in range(5):
        await _seed_grant(db_session, title=f"Paginated Grant {i}")
    resp = await client.get("/api/v1/grants?per_page=2&page=1")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) <= 2
    assert data["per_page"] == 2


@pytest.mark.asyncio
async def test_trigger_collection_requires_auth(client):
    resp = await client.post("/api/v1/grants/collect/grants_gov")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_trigger_collection_invalid_source(auth_client):
    resp = await auth_client.post("/api/v1/grants/collect/unknown_source")
    assert resp.status_code == 400
