"""Tests for website content fetching."""
import pytest
import responses
import requests
from reconly_core.fetchers.website import WebsiteFetcher


class TestWebsiteFetcher:
    """Test suite for WebsiteFetcher class."""

    @pytest.fixture
    def website_fetcher(self):
        """Create WebsiteFetcher instance for testing."""
        return WebsiteFetcher(timeout=5)

    @responses.activate
    def test_fetch_success_with_main_tag(self, website_fetcher):
        """WHEN valid HTML with <main> tag is fetched
        THEN content is extracted from main element."""
        html = """
        <html>
            <head><title>Test Article</title></head>
            <body>
                <nav>Navigation menu</nav>
                <main>
                    <h1>Main Content</h1>
                    <p>This is the main article content.</p>
                </main>
                <footer>Footer content</footer>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/article',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/article')
        # fetch() now returns a list with a single item
        item = result[0]

        assert item['url'] == 'https://example.com/article'
        assert item['title'] == 'Test Article'
        assert 'Main Content' in item['content']
        assert 'This is the main article content.' in item['content']
        assert 'Navigation menu' not in item['content']
        assert 'Footer content' not in item['content']
        assert item['source_type'] == 'website'

    @responses.activate
    def test_fetch_success_with_article_tag(self, website_fetcher):
        """WHEN HTML uses <article> tag and no <main>
        THEN content is extracted from article element."""
        html = """
        <html>
            <head><title>Blog Post</title></head>
            <body>
                <article>
                    <h1>Article Title</h1>
                    <p>Article body text.</p>
                </article>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/blog',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/blog')
        item = result[0]

        assert item['title'] == 'Blog Post'
        assert 'Article Title' in item['content']
        assert 'Article body text.' in item['content']

    @responses.activate
    def test_fetch_removes_scripts_and_styles(self, website_fetcher):
        """WHEN HTML contains <script> and <style> tags
        THEN they are removed from content."""
        html = """
        <html>
            <head>
                <title>Page with Scripts</title>
                <style>body { color: red; }</style>
            </head>
            <body>
                <main>
                    <p>Visible content</p>
                    <script>console.log('hidden');</script>
                </main>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/page',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/page')
        item = result[0]

        assert 'Visible content' in item['content']
        assert 'console.log' not in item['content']
        assert 'color: red' not in item['content']

    @responses.activate
    def test_fetch_404_error(self, website_fetcher):
        """WHEN URL returns 404 status
        THEN exception is raised."""
        responses.add(
            responses.GET,
            'https://example.com/notfound',
            status=404
        )

        with pytest.raises(Exception) as exc_info:
            website_fetcher.fetch('https://example.com/notfound')

        assert "Failed to fetch website" in str(exc_info.value)

    @responses.activate
    def test_fetch_timeout(self, website_fetcher):
        """WHEN request times out
        THEN exception is raised."""
        responses.add(
            responses.GET,
            'https://example.com/slow',
            body=requests.exceptions.Timeout("Timeout")
        )

        with pytest.raises(Exception) as exc_info:
            website_fetcher.fetch('https://example.com/slow')

        assert "Failed to fetch website" in str(exc_info.value)

    @responses.activate
    def test_fetch_connection_error(self, website_fetcher):
        """WHEN connection cannot be established
        THEN exception is raised."""
        responses.add(
            responses.GET,
            'https://example.com/unreachable',
            body=requests.exceptions.ConnectionError("Connection failed")
        )

        with pytest.raises(Exception) as exc_info:
            website_fetcher.fetch('https://example.com/unreachable')

        assert "Failed to fetch website" in str(exc_info.value)

    @responses.activate
    def test_fetch_missing_title(self, website_fetcher):
        """WHEN HTML has no <title> tag
        THEN default title is used."""
        html = """
        <html>
            <body>
                <main>
                    <p>Content without title</p>
                </main>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/notitle',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/notitle')
        item = result[0]

        assert item['title'] == 'No title'
        assert 'Content without title' in item['content']

    @responses.activate
    def test_fetch_with_content_div(self, website_fetcher):
        """WHEN HTML uses <div class="content"> and no main/article
        THEN content is extracted from div (if it meets minimum length threshold)."""
        # Content must exceed 100 char threshold used by the best-element selection logic
        long_paragraph = "This is the main content in a div element. " * 5
        html = f"""
        <html>
            <head><title>Div Content</title></head>
            <body>
                <div class="sidebar">Sidebar</div>
                <div class="content">
                    <p>{long_paragraph}</p>
                </div>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/div',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/div')
        item = result[0]

        assert 'main content in a div element' in item['content']
        assert 'Sidebar' not in item['content']

    @responses.activate
    def test_fetch_fallback_to_body(self, website_fetcher):
        """WHEN no semantic content tags are found
        THEN entire body content is extracted."""
        html = """
        <html>
            <head><title>Simple Page</title></head>
            <body>
                <p>Just some text in body</p>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/simple',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/simple')
        item = result[0]

        assert 'Just some text in body' in item['content']

    @responses.activate
    def test_fetch_cleans_excessive_whitespace(self, website_fetcher):
        """WHEN HTML has excessive whitespace and newlines
        THEN content is cleaned up."""
        html = """
        <html>
            <head><title>Whitespace Test</title></head>
            <body>
                <main>
                    <p>Line 1</p>


                    <p>Line 2</p>
                </main>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/whitespace',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/whitespace')
        item = result[0]

        # Should have cleaned up excessive newlines
        assert 'Line 1' in item['content']
        assert 'Line 2' in item['content']
        # No more than 2 consecutive newlines
        assert '\n\n\n' not in item['content']

    @responses.activate
    def test_fetch_malformed_html(self, website_fetcher):
        """WHEN HTML is malformed but parseable
        THEN content is still extracted (BeautifulSoup is lenient)."""
        html = """
        <html>
            <head><title>Malformed</title>
            <body>
                <main>
                    <p>Content here
                </main>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/malformed',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/malformed')
        item = result[0]

        assert item['title'] == 'Malformed'
        assert 'Content here' in item['content']

    @responses.activate
    def test_fetch_empty_body(self, website_fetcher):
        """WHEN HTML body is empty
        THEN result contains empty content."""
        html = """
        <html>
            <head><title>Empty</title></head>
            <body></body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/empty',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/empty')
        item = result[0]

        assert item['title'] == 'Empty'
        assert item['content'] == ''

    @responses.activate
    def test_fetch_sets_user_agent(self, website_fetcher):
        """WHEN request is made
        THEN User-Agent header is set."""
        html = '<html><body><p>Test</p></body></html>'

        def check_headers(request):
            assert 'User-Agent' in request.headers
            assert 'Mozilla' in request.headers['User-Agent']
            return (200, {}, html)

        responses.add_callback(
            responses.GET,
            'https://example.com/ua',
            callback=check_headers
        )

        website_fetcher.fetch('https://example.com/ua')

    @responses.activate
    def test_fetch_with_id_content(self, website_fetcher):
        """WHEN HTML uses <div id="content">
        THEN content is extracted from that div (if it meets minimum length threshold)."""
        # Content must exceed 100 char threshold used by the best-element selection logic
        long_paragraph = "Main content with ID selector providing detailed information. " * 4
        html = f"""
        <html>
            <head><title>ID Content</title></head>
            <body>
                <div id="header">Header</div>
                <div id="content">
                    <p>{long_paragraph}</p>
                </div>
            </body>
        </html>
        """

        responses.add(
            responses.GET,
            'https://example.com/idcontent',
            body=html,
            status=200
        )

        result = website_fetcher.fetch('https://example.com/idcontent')
        item = result[0]

        assert 'Main content with ID selector' in item['content']
        assert 'Header' not in item['content']
