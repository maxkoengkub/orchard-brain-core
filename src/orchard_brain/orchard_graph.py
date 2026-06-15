"""Phase 3 — Orchard Knowledge Graph.

A lightweight directed graph whose nodes represent agronomic variables and
whose edges represent causal / influence relationships.  The graph ships
pre-populated with durian-specific domain knowledge and can be extended at
runtime.

Usage::

    g = OrchardGraph()                               # pre-built graph
    path = g.explain_path("temperature", "yield")
    # → ["temperature", "vpd", "water_stress", "yield"]
    g.find_related_nodes("soil_moisture")
    # → ["root_health", "phytophthora", "flowering"]
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass

# ─────────────────────────────────────────────────── data structures


@dataclass
class GraphNode:
    name: str
    description: str = ""


@dataclass
class GraphEdge:
    source: str
    target: str
    relationship: str = "influences"


# ─────────────────────────────────────────────────── graph


class OrchardGraph:
    """Directed knowledge graph with BFS path explanation.

    Nodes and edges are stored by name (strings) for simplicity —
    a node is implicitly created when referenced in an edge.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adj: dict[str, list[str]] = {}  # source → [targets]
        self._build_durian_knowledge()

    # ───────────────────────────────────────── mutation API

    def add_node(self, name: str, description: str = "") -> None:
        """Register a named node (idempotent — updating description is allowed)."""
        if name in self._nodes:
            if description:
                self._nodes[name].description = description
        else:
            self._nodes[name] = GraphNode(name=name, description=description)
            self._adj.setdefault(name, [])

    def add_edge(
        self,
        source: str,
        target: str,
        relationship: str = "influences",
    ) -> None:
        """Add a directed edge from ``source`` to ``target``.

        Nodes are created automatically if they do not yet exist.
        Duplicate edges are silently ignored.
        """
        self.add_node(source)
        self.add_node(target)

        # Deduplicate
        for e in self._edges:
            if e.source == source and e.target == target:
                return

        self._edges.append(GraphEdge(source=source, target=target, relationship=relationship))
        self._adj[source].append(target)

    # ───────────────────────────────────────── query API

    def find_related_nodes(self, node: str) -> list[str]:
        """Return all nodes directly reachable from ``node`` (one hop)."""
        return list(self._adj.get(node, []))

    def explain_path(self, start: str, end: str) -> list[str]:
        """Return the shortest directed path from ``start`` to ``end``.

        Uses BFS.  Returns an empty list if no path exists or if either
        node is unknown.
        """
        if start not in self._nodes or end not in self._nodes:
            return []
        if start == end:
            return [start]

        visited: set[str] = {start}
        queue: deque[list[str]] = deque([[start]])

        while queue:
            path = queue.popleft()
            current = path[-1]
            for neighbour in self._adj.get(current, []):
                if neighbour == end:
                    return path + [neighbour]
                if neighbour not in visited:
                    visited.add(neighbour)
                    queue.append(path + [neighbour])

        return []  # no path

    def edge_label(self, source: str, target: str) -> str:
        """Return the relationship label for a given edge, or 'influences'."""
        for e in self._edges:
            if e.source == source and e.target == target:
                return e.relationship
        return "influences"

    def format_path(self, path: list[str]) -> str:
        """Return a human-readable arrow-chain string for a node path.

        Example: "temperature → vpd → water_stress → yield"
        """
        if not path:
            return "(no path)"
        return " → ".join(path)

    def all_paths_from(self, start: str, max_hops: int = 5) -> list[list[str]]:
        """Return all simple paths originating from ``start`` (up to max_hops)."""
        if start not in self._nodes:
            return []

        results: list[list[str]] = []
        queue: deque[list[str]] = deque([[start]])

        while queue:
            path = queue.popleft()
            current = path[-1]
            extended = False
            if len(path) <= max_hops:
                for neighbour in self._adj.get(current, []):
                    if neighbour not in path:  # no cycles
                        queue.append(path + [neighbour])
                        extended = True
            if not extended and len(path) > 1:
                results.append(path)

        return results

    def node_description(self, name: str) -> str:
        node = self._nodes.get(name)
        return node.description if node else ""

    # ───────────────────────────────────────── durian knowledge base

    def _build_durian_knowledge(self) -> None:
        """Pre-populate the graph with durian agronomic domain knowledge."""

        # ── Nodes (with agronomic descriptions)
        nodes = {
            "soil_moisture":  "Volumetric water content (VWC) in the root zone — "
                              "proxy measured via humidity sensor until VWC probe deployed.",
            "temperature":    "Ambient air temperature (°C) — optimal 25-32 °C (Haifa Guide).",
            "humidity":       "Relative humidity (%) — also used as soil moisture proxy.",
            "rainfall":       "Precipitation accumulation (mm) — primary soil moisture input.",
            "vpd":            "Vapor Pressure Deficit (kPa) — atmospheric water demand; "
                              "derived from temperature and humidity.",
            "water_stress":   "Plant water stress index — integrates soil moisture and VPD.",
            "root_health":    "Root system vitality — affected by moisture, pH, disease.",
            "phytophthora":   "Phytophthora palmivora disease risk — warm + wet soil.",
            "fertilizer":     "Nutrient inputs via fertigation (N, P, K, Ca, Mg).",
            "flowering":      "Flowering initiation — triggered by 15-day dry spell.",
            "fruit_set":      "Proportion of flowers that develop into fruit.",
            "fruit_drop":     "Premature fruit abscission — driven by stress.",
            "yield":          "Final harvestable durian yield.",
            "ph":             "Soil pH — governs nutrient bioavailability (optimal 5.5-6.5).",
            "ec":             "Electrical conductivity — proxy for nutrient solution strength.",
            "nutrient_status":"Overall plant nutrient health (N, P, K, Ca, Mg, S balance).",
        }
        for name, desc in nodes.items():
            self.add_node(name, desc)

        # ── Edges (directed influence relationships)
        edges = [
            # Water cycle
            ("rainfall",      "soil_moisture",  "recharges"),
            ("soil_moisture",  "root_health",    "sustains"),
            ("soil_moisture",  "phytophthora",   "elevates risk when high"),
            ("soil_moisture",  "flowering",      "dry spell triggers"),
            ("soil_moisture",  "water_stress",   "deficit causes"),

            # Atmospheric demand
            ("temperature",   "vpd",            "raises saturation pressure"),
            ("humidity",      "vpd",            "actual vapour pressure reduces VPD"),
            ("vpd",           "water_stress",   "amplifies demand"),
            ("vpd",           "fruit_drop",     "high VPD accelerates abscission"),

            # Stress cascade
            ("water_stress",  "fruit_drop",     "triggers abscission"),
            ("water_stress",  "yield",          "reduces"),

            # Disease pathway
            ("phytophthora",  "root_health",    "degrades via canker"),
            ("phytophthora",  "yield",          "reduces via tree death"),

            # Root → productivity
            ("root_health",   "nutrient_status","enables uptake"),
            ("root_health",   "yield",          "supports"),

            # Nutrient pathway
            ("fertilizer",    "nutrient_status","supplies"),
            ("nutrient_status","fruit_set",     "supports"),
            ("nutrient_status","yield",         "improves"),
            ("ph",            "nutrient_status","gates bioavailability"),
            ("ec",            "nutrient_status","indicates concentration"),

            # Phenology
            ("flowering",     "fruit_set",      "precedes"),
            ("fruit_set",     "yield",          "determines"),
            ("fruit_drop",    "yield",          "reduces"),

            # Temperature direct effects
            ("temperature",   "root_health",    "extremes damage"),
            ("temperature",   "flowering",      "cool nights interfere"),
        ]
        for src, tgt, rel in edges:
            self.add_edge(src, tgt, rel)
