from __future__ import annotations
from collections import defaultdict
from typing import Any

class KnowledgeEngine:
    """Relaciones declarativas entre conceptos, recursos y actividades."""

    def __init__(self, course: dict[str, Any]):
        self.course = course
        self.edges: dict[str, set[str]] = defaultdict(set)

    def link(self, left: str, right: str, relation: str = "RELATED") -> None:
        self.edges[left].add(f"{relation}:{right}")

    def concept(self, concept_id: str) -> dict[str, Any] | None:
        return next((x for x in self.course.get("concepts", []) if x.get("id") == concept_id), None)

    def related(self, node: str) -> list[str]:
        return sorted(self.edges.get(node, set()))
