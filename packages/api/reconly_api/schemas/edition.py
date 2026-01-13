"""Edition-aware schema utilities.

This module provides utilities for filtering response fields based on the current
Reconly edition (OSS vs Enterprise). Cost-related fields are only included in
Enterprise edition responses.

Two approaches are provided:

1. **EditionAwareMixin** (recommended for response models):
   Inherit from this mixin and cost fields will automatically be excluded
   from serialization in OSS edition.

2. **Utility functions** (for inline responses):
   Use `exclude_cost_fields()` for individual responses,
   `exclude_cost_fields_from_dict()` for dicts,
   `exclude_cost_fields_from_list()` for lists.

Usage:
    # Approach 1: Mixin (automatic filtering)
    class FeedRunResponse(EditionAwareMixin, BaseModel):
        total_cost: float = 0.0
        # ... other fields

    # Approach 2: Manual filtering
    @router.get("/feed-runs/{id}")
    async def get_feed_run(id: int):
        ...
        return exclude_cost_fields(response)
"""
from typing import Any, Dict, Set, TypeVar
from pydantic import BaseModel

from reconly_core.edition import is_enterprise


# Fields to exclude in OSS edition (cost-related fields)
OSS_EXCLUDED_FIELDS: Set[str] = {
    "total_cost",
    "estimated_cost",
    "cost",
    "cost_per_run",
    "monthly_cost",
}


T = TypeVar("T", bound=BaseModel)


def exclude_cost_fields(response: T) -> Dict[str, Any]:
    """
    Serialize a response model, excluding cost fields in OSS edition.

    In Enterprise edition, all fields are included.
    In OSS edition, cost-related fields are excluded from the response.

    Args:
        response: A Pydantic model instance

    Returns:
        A dictionary representation of the model with cost fields excluded in OSS

    Example:
        >>> response = FeedRunResponse(id=1, total_cost=0.05, ...)
        >>> # In OSS edition:
        >>> exclude_cost_fields(response)
        {'id': 1, ...}  # total_cost is excluded
        >>> # In Enterprise edition:
        >>> exclude_cost_fields(response)
        {'id': 1, 'total_cost': 0.05, ...}  # total_cost is included
    """
    if is_enterprise():
        # Enterprise: include all fields
        return response.model_dump()

    # OSS: exclude cost-related fields
    return response.model_dump(exclude=OSS_EXCLUDED_FIELDS)


def exclude_cost_fields_from_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Filter cost fields from a dictionary in OSS edition.

    Useful for inline response building (e.g., in analytics routes).

    Args:
        data: A dictionary that may contain cost fields

    Returns:
        The dictionary with cost fields excluded in OSS edition
    """
    if is_enterprise():
        return data

    return {k: v for k, v in data.items() if k not in OSS_EXCLUDED_FIELDS}


def exclude_cost_fields_from_list(items: list) -> list:
    """
    Filter cost fields from a list of dictionaries or models.

    Args:
        items: A list of dictionaries or Pydantic models

    Returns:
        The list with cost fields excluded from each item in OSS edition
    """
    if is_enterprise():
        # Enterprise: return as-is (convert models to dicts if needed)
        return [
            item.model_dump() if isinstance(item, BaseModel) else item
            for item in items
        ]

    result = []
    for item in items:
        if isinstance(item, BaseModel):
            result.append(item.model_dump(exclude=OSS_EXCLUDED_FIELDS))
        elif isinstance(item, dict):
            result.append({k: v for k, v in item.items() if k not in OSS_EXCLUDED_FIELDS})
        else:
            result.append(item)

    return result
