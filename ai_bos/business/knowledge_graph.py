"""Business entity and relationship model."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BusinessEntity:
    entity_id: uuid.UUID = field(default_factory=uuid.uuid4)
    entity_type: str = ""       # customer, staff, vendor, regulator, product, service
    name: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class BusinessRelationship:
    from_entity: uuid.UUID = field(default_factory=uuid.uuid4)
    to_entity: uuid.UUID = field(default_factory=uuid.uuid4)
    relationship_type: str = ""  # serves, employs, reports_to, regulates, etc.
    attributes: dict[str, Any] = field(default_factory=dict)


class BusinessKnowledgeGraph:
    """In-memory graph of business entities and relationships.
    Persisted as structured facts in the MemoryStore."""

    def __init__(self) -> None:
        self._entities: dict[uuid.UUID, BusinessEntity] = {}
        self._relationships: list[BusinessRelationship] = []

    def add_entity(self, entity: BusinessEntity) -> None:
        self._entities[entity.entity_id] = entity

    def add_relationship(self, rel: BusinessRelationship) -> None:
        self._relationships.append(rel)

    def get_entity(self, entity_id: uuid.UUID) -> BusinessEntity | None:
        return self._entities.get(entity_id)

    def relationships_for(self, entity_id: uuid.UUID) -> list[BusinessRelationship]:
        return [
            r for r in self._relationships
            if r.from_entity == entity_id or r.to_entity == entity_id
        ]
