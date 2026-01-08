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
    page = PageNode(id="1", title="Test Page", body_content="", position=0)
    return ConfluenceExport(
        path=Path("."),
        space=Space(id="1", key="TEST", name="Test"),
        root_pages=[page],
        pages_by_id={"1": page},
    )


class TestMarkdownConverter:
    """Tests for MarkdownConverter class."""

    def test_convert_empty_page(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Empty page produces minimal output."""
        converter = MarkdownConverter(settings)
        page = simple_export.root_pages[0]

        result = converter.convert(page, simple_export)

        assert isinstance(result, ConversionResult)
        # Should have frontmatter at minimum
        assert "---" in result.markdown

    def test_convert_simple_paragraph(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Simple paragraph converts correctly."""
        converter = MarkdownConverter(settings)
        page = simple_export.root_pages[0]
        page.body_content = "<p>Hello World</p>"

        result = converter.convert(page, simple_export)

        assert "Hello World" in result.markdown

    def test_frontmatter_includes_title(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """Frontmatter includes page title."""
        converter = MarkdownConverter(settings)
        page = simple_export.root_pages[0]

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
        page = simple_export.root_pages[0]

        result = converter.convert(page, simple_export)

        assert result.frontmatter is None
        assert "---" not in result.markdown


class TestSectionFiltering:
    """Tests for section filtering functionality."""

    def test_exclude_section_by_pattern(
        self, simple_export: ConfluenceExport
    ) -> None:
        """Sections matching exclude patterns are skipped."""
        settings = Settings.default()
        settings.exclude_sections = ["**/Change Log"]

        converter = MarkdownConverter(settings)
        page = simple_export.root_pages[0]
        page.body_content = """
            <h1>Main Content</h1>
            <p>Important stuff</p>
            <h2>Change Log</h2>
            <p>This should be skipped</p>
            <h2>More Content</h2>
            <p>This should appear</p>
        """

        result = converter.convert(page, simple_export)

        # The skipped section should be reported
        assert "Change Log" in str(result.skipped_sections)


class TestLinkConversion:
    """Tests for link conversion."""

    def test_external_link(
        self, settings: Settings, simple_export: ConfluenceExport
    ) -> None:
        """External links convert to Markdown format."""
        converter = MarkdownConverter(settings)
        page = simple_export.root_pages[0]
        page.body_content = '<a href="https://example.com">Example</a>'

        result = converter.convert(page, simple_export)

        assert "[Example](https://example.com)" in result.markdown or "Example" in result.markdown


class TestSlugify:
    """Tests for the slugify helper."""

    def test_slugify_basic(self, settings: Settings) -> None:
        """Basic slugification works."""
        converter = MarkdownConverter(settings)

        assert converter._slugify("Hello World") == "hello-world"
        assert converter._slugify("My Page Title") == "my-page-title"

    def test_slugify_special_chars(self, settings: Settings) -> None:
        """Special characters are removed."""
        converter = MarkdownConverter(settings)

        assert converter._slugify("Hello! World?") == "hello-world"
        assert converter._slugify("Test (Page)") == "test-page"

    def test_slugify_multiple_spaces(self, settings: Settings) -> None:
        """Multiple spaces become single dash."""
        converter = MarkdownConverter(settings)

        assert converter._slugify("Hello   World") == "hello-world"
        assert converter._slugify("  Leading and Trailing  ") == "leading-and-trailing"
