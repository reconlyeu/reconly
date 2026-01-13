"""Feed marketplace module for bundle export/import.

This module provides functionality for:
- Exporting feeds as portable JSON bundles
- Importing feed bundles from the marketplace
- Validating bundle schemas
"""
from reconly_core.marketplace.bundle import (
    FeedBundle,
    BundleAuthor,
    BundleSource,
    BundlePromptTemplate,
    BundleReportTemplate,
    BundleSchedule,
    BundleCompatibility,
    BundleMetadata,
    slugify,
)
from reconly_core.marketplace.exporter import FeedBundleExporter
from reconly_core.marketplace.importer import FeedBundleImporter, ImportResult
from reconly_core.marketplace.validator import BundleValidator, ValidationResult
from reconly_core.marketplace.schema import BUNDLE_SCHEMA_V1

__all__ = [
    # Bundle dataclasses
    'FeedBundle',
    'BundleAuthor',
    'BundleSource',
    'BundlePromptTemplate',
    'BundleReportTemplate',
    'BundleSchedule',
    'BundleCompatibility',
    'BundleMetadata',
    'slugify',
    # Exporter
    'FeedBundleExporter',
    # Importer
    'FeedBundleImporter',
    'ImportResult',
    # Validator
    'BundleValidator',
    'ValidationResult',
    # Schema
    'BUNDLE_SCHEMA_V1',
]
