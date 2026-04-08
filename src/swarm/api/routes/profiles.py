"""API routes for executive Thorsten 4 profiles."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from swarm import store
from swarm.data.executives import SAMPLE_EXECUTIVES, get_executive_info, load_api_profiles, load_sample_profiles
from swarm.profiles.extractor import extract_profile

router = APIRouter()


class ExtractRequest(BaseModel):
    executive_name: str
    transcript_text: str


@router.get("/")
async def list_profiles():
    """List all stored profiles."""
    return {
        name: _profile_summary(name, p)
        for name, p in store.profiles.items()
    }


@router.get("/samples/available")
async def list_sample_executives():
    """List executives available with pre-built Thorsten 4 profiles."""
    return SAMPLE_EXECUTIVES


@router.post("/load-samples")
async def load_samples():
    """Load all pre-built Thorsten 4 profiles into the store (samples + API profiles)."""
    # Load original 4 sample profiles
    all_profiles = load_sample_profiles()
    # Also load API-analyzed profiles (Sam Altman, Dario Amodei, etc.)
    all_profiles.update(load_api_profiles())

    loaded = []
    for name, profile in all_profiles.items():
        info = get_executive_info(name)
        store.profiles[name] = {
            **profile,
            "title": info["title"] if info else "Executive",
            "company": info["company"] if info else "Unknown",
            "sector": info["sector"] if info else "Unknown",
        }
        store.knowledge[name] = {
            "decisions": [],
            "companies": [{"name": info["company"], "sector": info["sector"]}] if info else [],
            "positions": [{"title": info["title"], "company": info["company"]}] if info else [],
        }
        loaded.append(name)
    return {"loaded": loaded, "count": len(loaded)}


@router.post("/fix-metadata")
async def fix_metadata():
    """Re-apply executive metadata from KNOWN_EXECUTIVES to all stored profiles."""
    fixed = []
    for name in list(store.profiles.keys()):
        info = get_executive_info(name)
        if info and store.profiles[name].get("company", "Unknown") == "Unknown":
            store.profiles[name]["title"] = info["title"]
            store.profiles[name]["company"] = info["company"]
            store.profiles[name]["sector"] = info["sector"]
            fixed.append(name)
    return {"fixed": fixed}


class StoreRawRequest(BaseModel):
    executive_name: str
    profile: dict


@router.post("/store-raw")
async def store_raw_profile(req: StoreRawRequest):
    """Store a raw Thorsten 4 API response directly, with metadata lookup."""
    info = get_executive_info(req.executive_name)
    store.profiles[req.executive_name] = {
        **req.profile,
        "title": info["title"] if info else "Executive",
        "company": info["company"] if info else "Unknown",
        "sector": info["sector"] if info else "Unknown",
    }
    return {"stored": req.executive_name, "company": store.profiles[req.executive_name].get("company")}


@router.get("/{executive_name}")
async def get_profile(executive_name: str):
    """Get a specific executive's Thorsten 4 profile."""
    profile = store.profiles.get(executive_name)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile for '{executive_name}'")
    return profile


@router.post("/analyze")
async def analyze_transcript(req: ExtractRequest):
    """Analyze a transcript via the live Thorsten 4 API and store the profile."""
    profile = await extract_profile(req.executive_name, req.transcript_text)
    info = get_executive_info(req.executive_name)
    store.profiles[req.executive_name] = {
        **profile,
        "title": info["title"] if info else "Executive",
        "company": info["company"] if info else "Unknown",
        "sector": info["sector"] if info else "Unknown",
    }
    store.knowledge[req.executive_name] = {
        "decisions": [],
        "companies": [{"name": info["company"], "sector": info["sector"]}] if info else [],
        "positions": [{"title": info["title"], "company": info["company"]}] if info else [],
    }
    return {"executive_name": req.executive_name, "profile": store.profiles[req.executive_name]}


def _profile_summary(name: str, profile: dict) -> dict:
    # API v2 format: top-level motives/affect
    if profile.get("object") == "analysis":
        motives = profile.get("motives", {})
        affect = profile.get("affect", {})
        return {
            "title": profile.get("title", ""),
            "company": profile.get("company", ""),
            "sector": profile.get("sector", ""),
            "motives": {
                "power": motives.get("power"),
                "achievement": motives.get("achievement"),
                "contact": motives.get("contact"),
            },
            "emotions": {
                "approach": affect.get("approach"),
                "avoidance": affect.get("avoidance"),
            },
        }
    # Old sample format: result.motives, result.emotions
    result = profile.get("result", {})
    motives = result.get("motives", {})
    emotions = result.get("emotions", {})
    return {
        "title": profile.get("title", ""),
        "company": profile.get("company", ""),
        "sector": profile.get("sector", ""),
        "motives": {
            "power": motives.get("power"),
            "achievement": motives.get("achievement"),
            "contact": motives.get("contact"),
        },
        "emotions": emotions,
    }
