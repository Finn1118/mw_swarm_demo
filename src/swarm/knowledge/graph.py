"""In-memory knowledge graph with deduplication and merge.

Stores entities as nodes and relationships as edges. Deduplicates by
(name, type) pair — same executive mentioned in 100 articles = 1 node.
"""

from dataclasses import dataclass, field


@dataclass
class Node:
    name: str
    type: str
    attributes: dict = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)  # which articles mentioned this

    @property
    def key(self) -> str:
        return f"{self.type}::{self.name.lower().strip()}"


@dataclass
class Edge:
    type: str
    source: str  # node key
    target: str  # node key
    context: str = ""
    sources: list[str] = field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.source}--{self.type}-->{self.target}"


class KnowledgeGraph:
    def __init__(self):
        self.nodes: dict[str, Node] = {}  # keyed by Node.key
        self.edges: dict[str, Edge] = {}  # keyed by Edge.key

    def add_entity(self, entity: dict, source_label: str = ""):
        """Add or merge an entity into the graph."""
        node = Node(
            name=entity["name"],
            type=entity["type"],
            attributes=entity.get("attributes", {}),
            sources=[source_label] if source_label else [],
        )
        existing = self.nodes.get(node.key)
        if existing:
            # Merge: update attributes, add source
            for k, v in node.attributes.items():
                if v and (k not in existing.attributes or not existing.attributes[k]):
                    existing.attributes[k] = v
            if source_label and source_label not in existing.sources:
                existing.sources.append(source_label)
        else:
            self.nodes[node.key] = node

    def add_relationship(self, rel: dict, source_label: str = ""):
        """Add or merge a relationship into the graph."""
        # Resolve source/target to node keys (try to match by name)
        source_key = self._resolve_node(rel["source"])
        target_key = self._resolve_node(rel["target"])
        if not source_key or not target_key:
            return  # skip if we can't resolve

        edge = Edge(
            type=rel["type"],
            source=source_key,
            target=target_key,
            context=rel.get("context", ""),
            sources=[source_label] if source_label else [],
        )
        existing = self.edges.get(edge.key)
        if existing:
            if source_label and source_label not in existing.sources:
                existing.sources.append(source_label)
            if edge.context and edge.context != existing.context:
                existing.context = edge.context  # update with latest
        else:
            self.edges[edge.key] = edge

    def _resolve_node(self, name: str) -> str | None:
        """Find a node key by name (case-insensitive)."""
        name_lower = name.lower().strip()
        for key, node in self.nodes.items():
            if node.name.lower().strip() == name_lower:
                return key
        return None

    def get_context_for_executive(self, executive_name: str) -> dict:
        """Get all knowledge relevant to an executive for simulation context."""
        exec_key = self._resolve_node(executive_name)
        if not exec_key:
            return {"decisions": [], "companies": [], "events": [], "relationships": []}

        decisions = []
        events = []
        companies = []
        relationships = []

        for edge in self.edges.values():
            if edge.source == exec_key:
                target = self.nodes.get(edge.target)
                if not target:
                    continue
                if edge.type == "DECIDED":
                    decisions.append({"description": target.name, "context": edge.context, **target.attributes})
                elif edge.type == "RESPONDED_TO":
                    events.append({"description": target.name, "context": edge.context, **target.attributes})
                elif edge.type == "LEADS":
                    companies.append({"name": target.name, **target.attributes})
                else:
                    relationships.append({"type": edge.type, "target": target.name, "context": edge.context})
            elif edge.target == exec_key:
                source = self.nodes.get(edge.source)
                if source:
                    relationships.append({"type": edge.type, "source": source.name, "context": edge.context})

        # Also get company-level edges for companies this exec leads
        exec_companies = {e.target for e in self.edges.values() if e.source == exec_key and e.type == "LEADS"}
        for edge in self.edges.values():
            if edge.source in exec_companies and edge.type != "LEADS":
                target = self.nodes.get(edge.target)
                if target:
                    relationships.append({
                        "type": edge.type,
                        "source": self.nodes[edge.source].name,
                        "target": target.name,
                        "context": edge.context,
                    })

        return {
            "decisions": decisions,
            "companies": companies,
            "events": events,
            "relationships": relationships,
        }

    def stats(self) -> dict:
        """Return graph statistics."""
        type_counts = {}
        for node in self.nodes.values():
            type_counts[node.type] = type_counts.get(node.type, 0) + 1
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": type_counts,
            "edge_types": len({e.type for e in self.edges.values()}),
        }

    def to_dict(self) -> dict:
        """Serialize the graph for API responses."""
        return {
            "nodes": [
                {"name": n.name, "type": n.type, "attributes": n.attributes, "sources": n.sources}
                for n in self.nodes.values()
            ],
            "edges": [
                {"type": e.type, "source": self.nodes[e.source].name if e.source in self.nodes else e.source,
                 "target": self.nodes[e.target].name if e.target in self.nodes else e.target,
                 "context": e.context}
                for e in self.edges.values()
            ],
            "stats": self.stats(),
        }
