"""Tests for ModelInfo and ModelCache."""
import pytest
from datetime import datetime, timedelta

from reconly_core.summarizers.capabilities import ModelInfo, ProviderCapabilities
from reconly_core.summarizers.cache import ModelCache, get_model_cache


class TestModelInfo:
    """Tests for ModelInfo dataclass."""

    def test_create_model_info(self):
        """Test creating a ModelInfo instance."""
        model = ModelInfo(
            id='test-model-id',
            name='Test Model Name',
            provider='test-provider'
        )
        assert model.id == 'test-model-id'
        assert model.name == 'Test Model Name'
        assert model.provider == 'test-provider'
        assert model.is_default is False
        assert model.deprecated is False

    def test_create_model_info_with_defaults(self):
        """Test creating ModelInfo with is_default and deprecated."""
        model = ModelInfo(
            id='gpt-4o',
            name='GPT-4o',
            provider='openai',
            is_default=True,
            deprecated=False
        )
        assert model.is_default is True
        assert model.deprecated is False

    def test_to_dict(self):
        """Test ModelInfo.to_dict() method."""
        model = ModelInfo(
            id='test-model',
            name='Test Model',
            provider='test',
            is_default=True,
            deprecated=True
        )
        result = model.to_dict()
        assert result == {
            'id': 'test-model',
            'name': 'Test Model',
            'provider': 'test',
            'is_default': True,
            'deprecated': True,
        }


class TestModelCache:
    """Tests for ModelCache."""

    def test_set_and_get(self):
        """Test caching models."""
        cache = ModelCache(ttl_seconds=3600)
        models = [
            ModelInfo(id='m1', name='Model 1', provider='test'),
            ModelInfo(id='m2', name='Model 2', provider='test'),
        ]
        cache.set('test', models)
        
        result = cache.get('test')
        assert result is not None
        assert len(result) == 2
        assert result[0].id == 'm1'
        assert result[1].id == 'm2'

    def test_get_nonexistent(self):
        """Test getting from empty cache."""
        cache = ModelCache()
        result = cache.get('nonexistent')
        assert result is None

    def test_invalidate_single(self):
        """Test invalidating a single provider."""
        cache = ModelCache()
        cache.set('p1', [ModelInfo(id='m1', name='M1', provider='p1')])
        cache.set('p2', [ModelInfo(id='m2', name='M2', provider='p2')])
        
        cache.invalidate('p1')
        
        assert cache.get('p1') is None
        assert cache.get('p2') is not None

    def test_invalidate_all(self):
        """Test invalidating all providers."""
        cache = ModelCache()
        cache.set('p1', [ModelInfo(id='m1', name='M1', provider='p1')])
        cache.set('p2', [ModelInfo(id='m2', name='M2', provider='p2')])
        
        cache.invalidate()
        
        assert cache.get('p1') is None
        assert cache.get('p2') is None

    def test_is_expired(self):
        """Test expiration checking."""
        cache = ModelCache(ttl_seconds=3600)
        
        # Not in cache = expired
        assert cache.is_expired('missing') is True
        
        # In cache and fresh = not expired
        cache.set('fresh', [ModelInfo(id='m', name='M', provider='t')])
        assert cache.is_expired('fresh') is False


class TestGlobalCache:
    """Tests for global cache instance."""

    def test_get_model_cache_returns_same_instance(self):
        """Test that get_model_cache returns singleton."""
        cache1 = get_model_cache()
        cache2 = get_model_cache()
        assert cache1 is cache2
