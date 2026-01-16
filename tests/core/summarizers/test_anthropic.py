"""Tests for Anthropic Claude summarizer."""
import pytest
from unittest.mock import Mock, patch
from reconly_core.summarizers.anthropic import AnthropicSummarizer
from tests.core.summarizers.base_test_suite import BaseSummarizerTestSuite


class TestAnthropicSummarizer(BaseSummarizerTestSuite):
    """Test suite for AnthropicSummarizer (inherits contract tests from BaseSummarizerTestSuite)."""

    @pytest.fixture
    def summarizer(self):
        """Return configured Anthropic summarizer instance."""
        with patch('reconly_core.summarizers.anthropic.Anthropic'):
            return AnthropicSummarizer(api_key='test-anthropic-key')

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

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-api-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_initialization_with_env_var(self, mock_anthropic_class):
        """WHEN API key is in environment variable
        THEN summarizer initializes successfully."""
        summarizer = AnthropicSummarizer()

        assert summarizer.api_key == 'test-api-key'
        assert summarizer.model.startswith('claude-')  # Valid Anthropic model
        # Verify client was created with api_key and timeout
        mock_anthropic_class.assert_called_once_with(
            api_key='test-api-key',
            timeout=120.0  # Default timeout
        )

    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_initialization_with_explicit_key(self, mock_anthropic_class):
        """WHEN API key is passed as parameter
        THEN it takes precedence over environment variable."""
        summarizer = AnthropicSummarizer(api_key='explicit-key')

        assert summarizer.api_key == 'explicit-key'
        mock_anthropic_class.assert_called_once_with(
            api_key='explicit-key',
            timeout=120.0  # Default timeout
        )

    @patch.dict('os.environ', {}, clear=True)
    def test_initialization_missing_key(self):
        """WHEN no API key is provided
        THEN ValueError is raised."""
        with pytest.raises(ValueError) as exc_info:
            AnthropicSummarizer()

        assert "Anthropic API key required" in str(exc_info.value)

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_get_provider_name(self, mock_anthropic_class):
        """WHEN get_provider_name is called
        THEN 'anthropic' is returned."""
        summarizer = AnthropicSummarizer()
        assert summarizer.get_provider_name() == 'anthropic'

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_get_model_info(self, mock_anthropic_class):
        """WHEN get_model_info is called
        THEN model details are returned with expected structure."""
        summarizer = AnthropicSummarizer()
        model_info = summarizer.get_model_info()

        assert model_info['provider'] == 'anthropic'
        assert model_info['model'].startswith('claude-')  # Valid Anthropic model
        assert 'name' in model_info  # Has a display name

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_estimate_cost(self, mock_anthropic_class):
        """WHEN cost is estimated in OSS edition
        THEN 0.0 is returned (cost tracking is Enterprise only)."""
        summarizer = AnthropicSummarizer()

        # Test with 1000 characters
        cost = summarizer.estimate_cost(1000)

        # OSS edition always returns 0.0 - Enterprise overrides for actual pricing
        assert cost == 0.0

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_summarize_success_german(self, mock_anthropic_class, content_data):
        """WHEN summarization succeeds with German language
        THEN summary is added to content data."""
        # Mock the API response
        mock_content = Mock()
        mock_content.text = "Dies ist eine deutsche Zusammenfassung."

        mock_message = Mock()
        mock_message.content = [mock_content]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client

        summarizer = AnthropicSummarizer()
        result = summarizer.summarize(content_data, language='de')

        # Verify result contains original data plus summary
        assert result['url'] == content_data['url']
        assert result['title'] == content_data['title']
        assert result['content'] == content_data['content']
        assert result['summary'] == "Dies ist eine deutsche Zusammenfassung."
        assert result['summary_language'] == 'de'
        assert 'model_info' in result
        assert 'estimated_cost' in result

        # Verify API was called with German prompt
        call_args = mock_client.messages.create.call_args
        assert call_args[1]['model'].startswith('claude-')  # Valid Anthropic model
        assert call_args[1]['max_tokens'] >= 1000  # Reasonable token limit
        prompt = call_args[1]['messages'][0]['content']
        assert 'Fasse den folgenden Inhalt' in prompt
        assert 'Test Article' in prompt

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_summarize_success_english(self, mock_anthropic_class, content_data):
        """WHEN summarization succeeds with English language
        THEN English prompt is used."""
        # Mock the API response
        mock_content = Mock()
        mock_content.text = "This is an English summary."

        mock_message = Mock()
        mock_message.content = [mock_content]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client

        summarizer = AnthropicSummarizer()
        result = summarizer.summarize(content_data, language='en')

        assert result['summary'] == "This is an English summary."
        assert result['summary_language'] == 'en'

        # Verify English prompt was used
        call_args = mock_client.messages.create.call_args
        prompt = call_args[1]['messages'][0]['content']
        assert 'Summarize the following content' in prompt

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_summarize_empty_content(self, mock_anthropic_class):
        """WHEN content is empty
        THEN ValueError is raised."""
        summarizer = AnthropicSummarizer()

        empty_data = {
            'title': 'Empty Article',
            'content': '',
            'source_type': 'website'
        }

        with pytest.raises(ValueError) as exc_info:
            summarizer.summarize(empty_data)

        assert "No content to summarize" in str(exc_info.value)

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_summarize_api_error(self, mock_anthropic_class, content_data):
        """WHEN API returns an error
        THEN exception is raised with error message."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API rate limit exceeded")
        mock_anthropic_class.return_value = mock_client

        summarizer = AnthropicSummarizer()

        with pytest.raises(Exception) as exc_info:
            summarizer.summarize(content_data)

        assert "Failed to generate summary with Claude" in str(exc_info.value)
        assert "API rate limit exceeded" in str(exc_info.value)

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_summarize_auth_error(self, mock_anthropic_class, content_data):
        """WHEN authentication fails
        THEN exception is raised."""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("Invalid API key")
        mock_anthropic_class.return_value = mock_client

        summarizer = AnthropicSummarizer()

        with pytest.raises(Exception) as exc_info:
            summarizer.summarize(content_data)

        assert "Failed to generate summary with Claude" in str(exc_info.value)

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_summarize_different_source_types(self, mock_anthropic_class):
        """WHEN different source types are used
        THEN appropriate labels are used in prompts."""
        mock_content = Mock()
        mock_content.text = "Summary text"

        mock_message = Mock()
        mock_message.content = [mock_content]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client

        summarizer = AnthropicSummarizer()

        # Test YouTube source type
        youtube_data = {
            'title': 'Video Title',
            'content': 'Video transcript content',
            'source_type': 'youtube'
        }

        result = summarizer.summarize(youtube_data, language='de')
        call_args = mock_client.messages.create.call_args
        prompt = call_args[1]['messages'][0]['content']
        # Fallback prompt uses raw source_type
        assert 'youtube' in prompt

        # Test RSS source type
        mock_client.messages.create.reset_mock()
        rss_data = {
            'title': 'Article Title',
            'content': 'Article content',
            'source_type': 'rss'
        }

        result = summarizer.summarize(rss_data, language='de')
        call_args = mock_client.messages.create.call_args
        prompt = call_args[1]['messages'][0]['content']
        # Fallback prompt uses raw source_type
        assert 'rss' in prompt

    @patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'test-key'})
    @patch('reconly_core.summarizers.anthropic.Anthropic')
    def test_summarize_preserves_original_data(self, mock_anthropic_class, content_data):
        """WHEN summarization completes
        THEN original content data is preserved."""
        mock_content = Mock()
        mock_content.text = "Summary"

        mock_message = Mock()
        mock_message.content = [mock_content]

        mock_client = Mock()
        mock_client.messages.create.return_value = mock_message
        mock_anthropic_class.return_value = mock_client

        summarizer = AnthropicSummarizer()

        # Add custom field to test preservation
        content_data['custom_field'] = 'custom_value'

        result = summarizer.summarize(content_data)

        # Original data should be preserved
        assert result['custom_field'] == 'custom_value'
        assert result['url'] == content_data['url']
        # And new fields should be added
        assert 'summary' in result
        assert 'summary_language' in result
