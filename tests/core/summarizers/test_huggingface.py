"""Tests for HuggingFace summarizer."""
import pytest
from unittest.mock import Mock, patch
import requests
from reconly_core.summarizers.huggingface import HuggingFaceSummarizer
from tests.core.summarizers.base_test_suite import BaseSummarizerTestSuite


class TestHuggingFaceSummarizer(BaseSummarizerTestSuite):
    """Test suite for HuggingFaceSummarizer (inherits contract tests from BaseSummarizerTestSuite)."""

    @pytest.fixture
    def summarizer(self):
        """Return configured HuggingFace summarizer instance."""
        return HuggingFaceSummarizer(api_key='test-huggingface-key')

    @pytest.fixture
    def content_data(self):
        """Sample content data for testing."""
        return {
            'url': 'https://example.com/article',
            'title': 'Test Article',
            'content': 'This is test content for summarization. ' * 20,
            'source_type': 'website'
        }

    # Provider-specific tests

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-hf-key'})
    def test_initialization_with_env_var(self):
        """WHEN API key is in environment variable
        THEN summarizer initializes successfully."""
        summarizer = HuggingFaceSummarizer()

        assert summarizer.api_key == 'test-hf-key'
        # Check that default model is set (don't assert specific model ID)
        assert summarizer.model_key in HuggingFaceSummarizer.AVAILABLE_MODELS
        assert summarizer.model  # Has a full model path

    def test_initialization_with_explicit_key(self):
        """WHEN API key is passed as parameter
        THEN it takes precedence over environment variable."""
        summarizer = HuggingFaceSummarizer(api_key='explicit-key')

        assert summarizer.api_key == 'explicit-key'

    @patch.dict('os.environ', {}, clear=True)
    def test_initialization_missing_key(self):
        """WHEN no API key is provided
        THEN ValueError is raised."""
        with pytest.raises(ValueError) as exc_info:
            HuggingFaceSummarizer()

        assert "HuggingFace API key required" in str(exc_info.value)

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    def test_initialization_custom_model(self):
        """WHEN custom model is specified
        THEN correct model is selected."""
        # Pick any model from AVAILABLE_MODELS for the test
        test_model = list(HuggingFaceSummarizer.AVAILABLE_MODELS.keys())[1]  # Second model
        summarizer = HuggingFaceSummarizer(model=test_model)

        assert summarizer.model_key == test_model
        assert summarizer.model == HuggingFaceSummarizer.AVAILABLE_MODELS[test_model]

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    def test_get_provider_name(self):
        """WHEN get_provider_name is called
        THEN provider name is 'huggingface' (model tracked separately)."""
        summarizer = HuggingFaceSummarizer()
        provider_name = summarizer.get_provider_name()
        assert provider_name == 'huggingface'
        # Model is tracked in get_model_info(), not in provider name
        model_info = summarizer.get_model_info()
        assert model_info['provider'] == 'huggingface'
        assert model_info['model_key'] == summarizer.model_key

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    def test_estimate_cost(self):
        """WHEN cost is estimated
        THEN zero cost is returned (free tier)."""
        summarizer = HuggingFaceSummarizer()
        cost = summarizer.estimate_cost(1000)
        assert cost == 0.0

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.huggingface.requests.post')
    def test_summarize_success(self, mock_post, content_data):
        """WHEN summarization succeeds
        THEN summary is added to content data."""
        # Mock successful API response (OpenAI-compatible chat completions format)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'This is a test summary.'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50}
        }
        mock_post.return_value = mock_response

        summarizer = HuggingFaceSummarizer()
        result = summarizer.summarize(content_data, language='en')

        assert result['summary'] == 'This is a test summary.'
        assert result['summary_language'] == 'en'
        assert 'model_info' in result
        assert result['estimated_cost'] == 0.0

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.huggingface.requests.post')
    def test_summarize_response_format(self, mock_post, content_data):
        """WHEN API returns response
        THEN generated text is extracted correctly."""
        # Create a normal mock response (OpenAI-compatible format)
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'This is the actual summary.'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50}
        }
        mock_post.return_value = mock_response

        summarizer = HuggingFaceSummarizer()
        result = summarizer.summarize(content_data, language='en')

        # Summary should be extracted
        assert 'summary' in result
        assert len(result['summary']) > 0

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.huggingface.requests.post')
    @patch('reconly_core.summarizers.huggingface.time.sleep')
    def test_summarize_model_loading_retry(self, mock_sleep, mock_post, content_data):
        """WHEN model is loading (503 status)
        THEN request is retried with backoff."""
        # First call returns 503 (loading), second call succeeds
        mock_response_loading = Mock()
        mock_response_loading.status_code = 503
        mock_response_loading.text = 'Model is loading'

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            'choices': [{'message': {'content': 'Summary'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50}
        }

        mock_post.side_effect = [mock_response_loading, mock_response_success]

        summarizer = HuggingFaceSummarizer()
        result = summarizer.summarize(content_data)

        assert result['summary'] == 'Summary'
        assert mock_post.call_count == 2
        mock_sleep.assert_called_once()

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.huggingface.requests.post')
    def test_summarize_api_error(self, mock_post, content_data):
        """WHEN API returns an error
        THEN exception is raised."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.text = 'Invalid API key'
        mock_post.return_value = mock_response

        summarizer = HuggingFaceSummarizer()

        with pytest.raises(Exception) as exc_info:
            summarizer.summarize(content_data)

        assert "Failed to generate summary" in str(exc_info.value)

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.huggingface.requests.post')
    def test_summarize_timeout(self, mock_post, content_data):
        """WHEN request times out
        THEN exception is raised after retries."""
        mock_post.side_effect = requests.Timeout("Request timeout")

        summarizer = HuggingFaceSummarizer(timeout=5)

        with pytest.raises(Exception) as exc_info:
            summarizer.summarize(content_data)

        assert "Failed to generate summary" in str(exc_info.value)

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    def test_summarize_empty_content(self):
        """WHEN content is empty
        THEN ValueError is raised."""
        summarizer = HuggingFaceSummarizer()

        empty_data = {
            'title': 'Empty Article',
            'content': '',
            'source_type': 'website'
        }

        with pytest.raises(ValueError) as exc_info:
            summarizer.summarize(empty_data)

        assert "No content to summarize" in str(exc_info.value)

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.huggingface.requests.post')
    def test_summarize_with_token_usage(self, mock_post, content_data):
        """WHEN API returns response with token usage
        THEN token counts are extracted correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Summary with tokens'}}],
            'usage': {'prompt_tokens': 150, 'completion_tokens': 75}
        }
        mock_post.return_value = mock_response

        summarizer = HuggingFaceSummarizer()
        result = summarizer.summarize(content_data)

        assert result['summary'] == 'Summary with tokens'
        assert result['model_info']['input_tokens'] == 150
        assert result['model_info']['output_tokens'] == 75

    @patch.dict('os.environ', {'HUGGINGFACE_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.huggingface.requests.post')
    def test_summarize_truncates_long_content(self, mock_post):
        """WHEN content exceeds maximum length
        THEN content is truncated before sending to API."""
        long_content = 'x' * 5000  # Exceeds 3000 char limit
        long_data = {
            'title': 'Long Article',
            'content': long_content,
            'source_type': 'website'
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Summary'}}],
            'usage': {'prompt_tokens': 100, 'completion_tokens': 50}
        }
        mock_post.return_value = mock_response

        summarizer = HuggingFaceSummarizer()
        summarizer.summarize(long_data)

        # Check that the sent payload uses chat completions format
        call_args = mock_post.call_args
        sent_payload = call_args[1]['json']

        # Should have messages array (OpenAI-compatible format)
        assert 'messages' in sent_payload
        # User message should contain truncated content with '...'
        user_message = sent_payload['messages'][1]['content']  # [0] is system, [1] is user
        assert '...' in user_message
