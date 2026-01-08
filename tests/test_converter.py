"""Tests for the Markdown converter module."""

from pathlib import Path

import pytest

from confluence_to_markdown.config import Settings
from confluence_to_markdown.converter import ConversionResult, MarkdownConverter
from confluence_to_markdown.export_parser import ConfluenceExport, PageNode, Space


@pytest.fixture
def settings() -> Settings:
    """Default settings for testing."""
    return Settings.default()


@pytest.fixture
def simple_export() -> ConfluenceExport:
    """Simple export with a single page."""
    page = PageNode(id="1", title="Test Page", body_content="", filename="test.html")
    return ConfluenceExport(
        path=Path("."),
        space=Space(key="TEST", name="Test"),
        pages=[page],
    )


class TestMarkdownConverter:
    """Tests for MarkdownConverter class."""

    def test_convert_empty_page(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Empty page produces minimal output."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]

        result = converter.convert(page, simple_export)

        assert isinstance(result, ConversionResult)
        # Should have frontmatter at minimum
        assert "---" in result.markdown

    def test_convert_simple_paragraph(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Simple paragraph converts correctly."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]
        page.body_content = "<p>Hello World</p>"

        result = converter.convert(page, simple_export)

        assert "Hello World" in result.markdown

    def test_frontmatter_includes_title(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Frontmatter includes page title."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]

        result = converter.convert(page, simple_export)

        assert result.frontmatter is not None
        assert result.frontmatter.get("title") == "Test Page"

    def test_frontmatter_disabled(
        self, simple_export: ConfluenceExport
    ) -> None:
        """Frontmatter can be disabled."""
        settings = Settings.default()
        settings.content.include_frontmatter = False

        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]

        result = converter.convert(page, simple_export)

        assert result.frontmatter is None
        assert "---" not in result.markdown


class TestLinkConversion:
    """Tests for link conversion."""

    def test_external_link(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """External links convert to Markdown format."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]
        page.body_content = '<a href="https://example.com">Example</a>'

        result = converter.convert(page, simple_export)

        assert "[Example](https://example.com)" in result.markdown


class TestHeadingConversion:
    """Tests for heading conversion."""

    def test_heading_levels(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Heading levels convert correctly."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]
        page.body_content = """
            <h1>Level 1</h1>
            <h2>Level 2</h2>
            <h3>Level 3</h3>
        """

        result = converter.convert(page, simple_export)

        assert "# Level 1" in result.markdown
        assert "## Level 2" in result.markdown
        assert "### Level 3" in result.markdown


class TestListConversion:
    """Tests for list conversion."""

    def test_unordered_list(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Unordered lists convert correctly."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]
        page.body_content = """
            <ul>
                <li>Item 1</li>
                <li>Item 2</li>
            </ul>
        """

        result = converter.convert(page, simple_export)

        assert "- Item 1" in result.markdown
        assert "- Item 2" in result.markdown

    def test_ordered_list(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Ordered lists convert correctly."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]
        page.body_content = """
            <ol>
                <li>First</li>
                <li>Second</li>
            </ol>
        """

        result = converter.convert(page, simple_export)

        assert "1. First" in result.markdown
        assert "2. Second" in result.markdown


class TestCodeConversion:
    """Tests for code block conversion."""

    def test_code_block(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Code blocks convert correctly."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]
        page.body_content = """
            <pre><code class="language-python">print("hello")</code></pre>
        """

        result = converter.convert(page, simple_export)

        assert "```python" in result.markdown
        assert 'print("hello")' in result.markdown

    def test_inline_code(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Inline code converts correctly."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]
        page.body_content = "<p>Use <code>pip install</code> to install</p>"

        result = converter.convert(page, simple_export)

        assert "`pip install`" in result.markdown


class TestTableConversion:
    """Tests for table conversion."""

    def test_simple_table(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Simple tables convert correctly."""
        converter = MarkdownConverter(settings)
        page = simple_export.pages[0]
        page.body_content = """
            <table>
                <tr><th>Header 1</th><th>Header 2</th></tr>
                <tr><td>Cell 1</td><td>Cell 2</td></tr>
            </table>
        """

        result = converter.convert(page, simple_export)

        assert "| Header 1 | Header 2 |" in result.markdown
        assert "| --- | --- |" in result.markdown
        assert "| Cell 1 | Cell 2 |" in result.markdown
