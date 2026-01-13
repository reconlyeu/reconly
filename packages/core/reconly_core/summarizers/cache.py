"""Model cache for provider model discovery.

Provides TTL-based caching for provider model lists to avoid
excessive API calls during model discovery.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from reconly_core.summarizers.capabilities import ModelInfo


class ModelCache:
    """Cache for provider model lists with TTL-based expiration."""

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize the model cache.

        Args:
            ttl_seconds: Time-to-live in seconds (default: 1 hour)
        """
        self._cache: Dict[str, Tuple[List[ModelInfo], datetime]] = {}
        self._ttl = timedelta(seconds=ttl_seconds)

    def get(self, provider: str) -> Optional[List[ModelInfo]]:
        """
        Get cached models if not expired.

        Args:
            provider: Provider name

        Returns:
            List of ModelInfo if cache hit and not expired, None otherwise
        """
        if provider in self._cache:
            models, timestamp = self._cache[provider]
            if datetime.now() - timestamp < self._ttl:
                return models
            # Expired - remove from cache
            del self._cache[provider]
        return None

    def set(self, provider: str, models: List[ModelInfo]) -> None:
        """
        Cache models for provider.

        Args:
            provider: Provider name
            models: List of ModelInfo to cache
        """
        self._cache[provider] = (models, datetime.now())

    def invalidate(self, provider: Optional[str] = None) -> None:
        """
        Invalidate cache for provider or all providers.

        Args:
            provider: Provider name to invalidate, or None for all
        """
        if provider:
            self._cache.pop(provider, None)
        else:
            self._cache.clear()

    def is_expired(self, provider: str) -> bool:
        """
        Check if cache for provider is expired or missing.

        Args:
            provider: Provider name

        Returns:
            True if cache is expired or missing
        """
        if provider not in self._cache:
            return True
        _, timestamp = self._cache[provider]
        return datetime.now() - timestamp >= self._ttl


# Global cache instance (singleton)
_model_cache: Optional[ModelCache] = None


def get_model_cache() -> ModelCache:
    """Get the global model cache instance."""
    global _model_cache
    if _model_cache is None:
        _model_cache = ModelCache()
    return _model_cache
