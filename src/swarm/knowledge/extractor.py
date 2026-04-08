"""LLM-based entity and relationship extraction from news text."""

import json

from openai import AsyncOpenAI

from swarm.config import settings
from swarm.knowledge.ontology import ONTOLOGY_PROMPT

EXTRACTION_PROMPT = """\
You are a financial knowledge graph extraction engine. Extract structured entities
and relationships from the news text below using ONLY these types:

{ontology}

Rules:
- Only extract entities and relationships explicitly stated or strongly implied in the text.
- Use the exact entity type names above.
- For each entity, include all available attributes.
- For each relationship, specify source and target entity names and the relationship type.
- Deduplicate: if the same person/company appears multiple times, use one consistent name.
- Return valid JSON only, no markdown.

News text:
{text}

Return this exact JSON structure:
{{
  "entities": [
    {{"type": "Executive", "name": "...", "attributes": {{"title": "...", "company": "..."}} }},
    ...
  ],
  "relationships": [
    {{"type": "DECIDED", "source": "...", "target": "...", "context": "one-line description"}},
    ...
  ]
}}
"""


async def extract_from_text(text: str) -> dict:
    """Extract entities and relationships from a news article or blurb."""
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.2,
        max_tokens=2048,
        messages=[
            {
                "role": "user",
                "content": EXTRACTION_PROMPT.format(ontology=ONTOLOGY_PROMPT, text=text[:10000]),
            }
        ],
    )
    raw = response.choices[0].message.content
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(raw)
