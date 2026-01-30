"""API routes for embedding providers.

This module exposes the embedding provider registry to the API,
allowing the UI to display available embedding providers and their metadata.
"""
from fastapi import APIRouter

from reconly_api.schemas.components import EmbeddingProviderMetadataResponse

router = APIRouter(prefix="/embedding-providers", tags=["embedding-providers"])


@router.get(
    "",
    response_model=list[EmbeddingProviderMetadataResponse],
    summary="List embedding providers",
    description="Returns metadata for all available embedding providers.",
)
def list_embedding_providers_metadata() -> list[EmbeddingProviderMetadataResponse]:
    """List all available embedding providers with their metadata."""
    from reconly_core.rag.embeddings import list_embedding_provider_metadata

    return list_embedding_provider_metadata()
