"""Importing a prior system's history.

Migration is the battle, not the feature list. A practice with twenty years in
another system will not abandon it, and incumbents make export deliberately
awkward. Treating import as a first-class component rather than a services
engagement is the difference between a product and a pilot.

Imported records become ordinary domain events with source=IMPORTED, so they
project into state exactly like native ones while remaining distinguishable
for anything that must not claim credit for them.
"""

from ai_bos.migration.importer import ImportReport, Importer
from ai_bos.migration.mappers import (
    ColumnMapping,
    SourceMapper,
    GENERIC_CSV_MAPPER,
)

__all__ = [
    "Importer",
    "ImportReport",
    "SourceMapper",
    "ColumnMapping",
    "GENERIC_CSV_MAPPER",
]
