"""In-memory store for prototype."""

from swarm.knowledge.graph import KnowledgeGraph

# Keyed by executive name
profiles: dict[str, dict] = {}

# Keyed by executive name — populated from knowledge graph
knowledge: dict[str, dict] = {}

# Keyed by simulation_id
simulations: dict[str, dict] = {}

# Single knowledge graph instance
graph = KnowledgeGraph()
