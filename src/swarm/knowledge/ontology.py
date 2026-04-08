"""Fixed ontology for the financial/executive domain.

Following MiroFish's pattern: constrained entity types + relationship types
to prevent graph explosion. Hand-tailored instead of auto-generated since
our domain is narrow and well-defined.
"""

ENTITY_TYPES = [
    {
        "name": "Executive",
        "description": "A named corporate leader (CEO, CFO, CTO, etc.)",
        "attributes": ["full_name", "title", "company"],
    },
    {
        "name": "Company",
        "description": "A corporation, startup, or business entity",
        "attributes": ["name", "sector", "ticker"],
    },
    {
        "name": "Decision",
        "description": "A specific strategic choice made by an executive or company",
        "attributes": ["description", "date", "outcome"],
    },
    {
        "name": "Event",
        "description": "A market event, crisis, announcement, or milestone",
        "attributes": ["description", "date", "impact"],
    },
    {
        "name": "Deal",
        "description": "An acquisition, merger, partnership, or investment",
        "attributes": ["description", "value", "date", "status"],
    },
    {
        "name": "Product",
        "description": "A product, service, or technology platform",
        "attributes": ["name", "company", "category"],
    },
    {
        "name": "Regulator",
        "description": "A government body, regulatory agency, or legal entity",
        "attributes": ["name", "jurisdiction"],
    },
    {
        "name": "FinancialContext",
        "description": "Revenue, earnings, stock movement, or financial metric",
        "attributes": ["metric", "value", "period", "company"],
    },
    # Fallbacks (same pattern as MiroFish)
    {
        "name": "Person",
        "description": "Any individual not matching Executive",
        "attributes": ["full_name", "role"],
    },
    {
        "name": "Organization",
        "description": "Any organization not matching Company or Regulator",
        "attributes": ["name", "type"],
    },
]

RELATIONSHIP_TYPES = [
    {"name": "LEADS", "source": "Executive", "target": "Company"},
    {"name": "DECIDED", "source": "Executive", "target": "Decision"},
    {"name": "ANNOUNCED", "source": "Company", "target": "Event"},
    {"name": "ACQUIRED", "source": "Company", "target": "Company"},
    {"name": "PARTNERED_WITH", "source": "Company", "target": "Company"},
    {"name": "COMPETES_WITH", "source": "Company", "target": "Company"},
    {"name": "LAUNCHED", "source": "Company", "target": "Product"},
    {"name": "INVESTED_IN", "source": "Company", "target": "Deal"},
    {"name": "REGULATED_BY", "source": "Company", "target": "Regulator"},
    {"name": "RESPONDED_TO", "source": "Executive", "target": "Event"},
]

# Compact ontology string for LLM extraction prompts
ONTOLOGY_PROMPT = """Entity types: Executive (name, title, company), Company (name, sector, ticker), Decision (description, date, outcome), Event (description, date, impact), Deal (description, value, date, status), Product (name, company, category), Regulator (name, jurisdiction), FinancialContext (metric, value, period, company), Person (name, role), Organization (name, type).

Relationship types: LEADS (Executive→Company), DECIDED (Executive→Decision), ANNOUNCED (Company→Event), ACQUIRED (Company→Company), PARTNERED_WITH (Company→Company), COMPETES_WITH (Company→Company), LAUNCHED (Company→Product), INVESTED_IN (Company→Deal), REGULATED_BY (Company→Regulator), RESPONDED_TO (Executive→Event)."""
