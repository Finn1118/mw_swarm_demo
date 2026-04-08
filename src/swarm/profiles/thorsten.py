"""Thorsten 4 API client — behavioral analysis via millionways API v2."""

import asyncio

import httpx

from swarm.config import settings

BASE_URL = "https://api.millionways.ai/v2"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.thorsten_api_key}",
        "Content-Type": "application/json",
    }


async def analyze_text(text: str, person_id: str | None = None, sync: bool = True) -> dict:
    """Submit text to Thorsten 4 for behavioral analysis.

    In sync mode (default), blocks until the result is ready (up to 60s).
    In async mode, returns a job object that must be polled.
    """
    payload = {
        "content": text,
        "language": "en",
        "mode": "sync" if sync else "async",
        "include_insights": True,
        "input_type": "transcript",
    }
    if person_id:
        payload["person_id"] = person_id

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(f"{BASE_URL}/analyze", json=payload, headers=_headers())
        resp.raise_for_status()
        result = resp.json()

    if not sync and result.get("status") in ("queued", "processing"):
        result = await poll_job(result["id"])

    return result


async def poll_job(job_id: str, max_wait: int = 120, interval: int = 3) -> dict:
    """Poll an async analysis job until completion."""
    elapsed = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        while elapsed < max_wait:
            resp = await client.get(f"{BASE_URL}/jobs/{job_id}", headers=_headers())
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") not in ("queued", "processing"):
                return data
            await asyncio.sleep(interval)
            elapsed += interval
    raise TimeoutError(f"Job {job_id} did not complete within {max_wait}s")


async def create_person(name: str, role: str, organization: str, tags: list[str] | None = None) -> dict:
    """Create a person record in the People Studio."""
    payload = {
        "name": name,
        "role": role,
        "organization_name": organization,
        "tags": tags or [],
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{BASE_URL}/people", json=payload, headers=_headers())
        resp.raise_for_status()
        return resp.json()


async def list_people(search: str | None = None) -> list[dict]:
    """List people from the People Studio."""
    params = {}
    if search:
        params["search"] = search
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(f"{BASE_URL}/people", params=params, headers=_headers())
        resp.raise_for_status()
        return resp.json().get("data", [])
