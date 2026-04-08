"""SEC EDGAR API client — simplified for prototype with sample executives."""

import httpx

from swarm.config import settings

EDGAR_FILINGS = "https://data.sec.gov/submissions"

# Sample executives for prototype — CIK numbers from SEC EDGAR
SAMPLE_EXECUTIVES = [
    {
        "name": "Jensen Huang",
        "title": "CEO",
        "company": "NVIDIA",
        "cik": "1045810",
        "sector": "Semiconductors",
    },
    {
        "name": "Tim Cook",
        "title": "CEO",
        "company": "Apple",
        "cik": "320193",
        "sector": "Consumer Electronics",
    },
    {
        "name": "Satya Nadella",
        "title": "CEO",
        "company": "Microsoft",
        "cik": "789019",
        "sector": "Software",
    },
]


async def get_company_filings(cik: str, form_type: str = "10-K", count: int = 3) -> list[dict]:
    """Get recent filings for a company by CIK number. Returns a short list for prototype."""
    cik_padded = cik.zfill(10)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{EDGAR_FILINGS}/CIK{cik_padded}.json",
            headers={"User-Agent": settings.edgar_user_agent},
        )
        resp.raise_for_status()
        data = resp.json()

    recent = data.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    dates = recent.get("filingDate", [])
    descriptions = recent.get("primaryDocDescription", [])

    filings = []
    for i, form in enumerate(forms):
        if form == form_type and len(filings) < count:
            filings.append({
                "form": form,
                "accession": accessions[i],
                "date": dates[i],
                "description": descriptions[i] if i < len(descriptions) else "",
            })
    return filings


async def get_filing_text(accession_number: str, cik: str) -> str:
    """Download the full text of a specific filing."""
    cik_padded = cik.zfill(10)
    accession_clean = accession_number.replace("-", "")
    async with httpx.AsyncClient() as client:
        # Try the primary document (usually the 10-K htm)
        index_url = f"https://www.sec.gov/Archives/edgar/data/{cik_padded}/{accession_clean}/"
        resp = await client.get(
            f"{index_url}{accession_number}-index.htm",
            headers={"User-Agent": settings.edgar_user_agent},
            follow_redirects=True,
        )
        resp.raise_for_status()
        return resp.text[:100000]  # Cap at 100K chars for prototype
