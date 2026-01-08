"""Integration tests with example Confluence HTML export."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from confluence_to_markdown.builder import ConversionBuilder
from confluence_to_markdown.config import Settings
from confluence_to_markdown.converter import MarkdownConverter
from confluence_to_markdown.export_parser import ExportParser


# Path to the example export fixture
FIXTURES_DIR = Path(__file__).parent / "fixtures"
EXAMPLE_EXPORT = FIXTURES_DIR / "example-export"


class TestExampleExportParsing:
    """Tests for parsing the example Confluence HTML export."""

    def test_parse_example_export(self) -> None:
        """Parse the example export and verify structure."""
        parser = ExportParser()
        export = parser.parse(EXAMPLE_EXPORT)

        # Verify space
        assert export.space.key == "example-export"
        assert export.space.name == "example-export"

        # Verify we have the right number of pages
        assert len(export.pages) == 4

    def test_page_titles(self) -> None:
        """Verify page titles are correctly extracted."""
        parser = ExportParser()
        export = parser.parse(EXAMPLE_EXPORT)

        titles = {page.title for page in export.pages}
        assert "Home" in titles
        assert "Getting Started" in titles
        assert "Architecture Overview" in titles
        assert "Installation Guide" in titles

    def test_page_content_present(self) -> None:
        """Verify body content is loaded."""
        parser = ExportParser()
        export = parser.parse(EXAMPLE_EXPORT)

        # Find Home page
        home = next((p for p in export.pages if p.title == "Home"), None)
        assert home is not None
        assert home.body_content
        assert "Welcome to the Documentation" in home.body_content

        # Find Getting Started page
        getting_started = next((p for p in export.pages if p.title == "Getting Started"), None)
        assert getting_started is not None
        assert "Prerequisites" in getting_started.body_content

    def test_walk_pages(self) -> None:
        """Verify walk_pages returns all pages."""
        parser = ExportParser()
        export = parser.parse(EXAMPLE_EXPORT)

        pages = list(export.walk_pages())
        assert len(pages) == 4


class TestExampleExportConversion:
    """Tests for converting the example export to Markdown."""

    @pytest.fixture
    def settings(self) -> Settings:
        """Default settings for testing."""
        return Settings.default()

    @pytest.fixture
    def export(self) -> "ConfluenceExport":
        """Parsed example export."""
        from confluence_to_markdown.export_parser import ConfluenceExport
        parser = ExportParser()
        return parser.parse(EXAMPLE_EXPORT)

    def test_convert_home_page(self, settings: Settings, export) -> None:
        """Convert the Home page to Markdown."""
        converter = MarkdownConverter(settings)
        home = next((p for p in export.pages if p.title == "Home"), None)
        assert home is not None

        result = converter.convert(home, export)

        # Check frontmatter
        assert "---" in result.markdown
        assert "title: Home" in result.markdown

        # Check heading conversion
        assert "# Welcome to the Documentation" in result.markdown

        # Check paragraph conversion
        assert "main documentation hub" in result.markdown

        # Check list conversion
        assert "- " in result.markdown

    def test_convert_page_with_code_block(self, settings: Settings, export) -> None:
        """Convert a page with code blocks."""
        converter = MarkdownConverter(settings)
        getting_started = next((p for p in export.pages if p.title == "Getting Started"), None)
        assert getting_started is not None

        result = converter.convert(getting_started, export)

        # Check code block
        assert "```" in result.markdown
        assert "pip install our-package" in result.markdown

    def test_convert_page_with_tables(self, settings: Settings, export) -> None:
        """Convert a page with tables."""
        converter = MarkdownConverter(settings)
        getting_started = next((p for p in export.pages if p.title == "Getting Started"), None)
        assert getting_started is not None

        result = converter.convert(getting_started, export)

        # Table should be converted (basic check for table markers)
        assert "|" in result.markdown
        assert "Version" in result.markdown

    def test_frontmatter_disabled(self, export) -> None:
        """Test conversion with frontmatter disabled."""
        settings = Settings.default()
        settings.content.include_frontmatter = False

        converter = MarkdownConverter(settings)
        home = next((p for p in export.pages if p.title == "Home"), None)
        assert home is not None

        result = converter.convert(home, export)

        # Should not have frontmatter
        assert not result.markdown.startswith("---")
        assert result.frontmatter is None


class TestFullConversionPipeline:
    """Tests for the full conversion pipeline including file output."""

    def test_full_conversion(self) -> None:
        """Test full conversion pipeline with file output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_dir = Path(tmpdir) / "exports"
            exports_dir.mkdir()

            settings = Settings.default()
            settings.exports_dir = exports_dir

            builder = ConversionBuilder(settings)
            result = builder.convert_export(EXAMPLE_EXPORT)

            # Check statistics
            assert result.pages_converted == 4
            assert result.pages_failed == 0
            assert result.pages_skipped == 0

            # Check files were created (flat structure)
            output_files = list(exports_dir.rglob("*.md"))
            assert len(output_files) == 4

    def test_incremental_conversion(self) -> None:
        """Test that incremental conversion skips unchanged pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_dir = Path(tmpdir) / "exports"
            exports_dir.mkdir()

            settings = Settings.default()
            settings.exports_dir = exports_dir

            builder = ConversionBuilder(settings)

            # First conversion
            result1 = builder.convert_export(EXAMPLE_EXPORT)
            assert result1.pages_converted == 4

            # Second conversion (should skip all pages)
            result2 = builder.convert_export(EXAMPLE_EXPORT)
            assert result2.pages_skipped == 4
            assert result2.pages_converted == 0

    def test_force_conversion(self) -> None:
        """Test that force flag reconverts all pages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_dir = Path(tmpdir) / "exports"
            exports_dir.mkdir()

            settings = Settings.default()
            settings.exports_dir = exports_dir

            builder = ConversionBuilder(settings)

            # First conversion
            result1 = builder.convert_export(EXAMPLE_EXPORT)
            assert result1.pages_converted == 4

            # Force conversion
            result2 = builder.convert_export(EXAMPLE_EXPORT, force=True)
            assert result2.pages_converted == 4
            assert result2.pages_skipped == 0

    def test_clean_removes_files(self) -> None:
        """Test that clean removes generated files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            exports_dir = Path(tmpdir) / "exports"
            exports_dir.mkdir()

            settings = Settings.default()
            settings.exports_dir = exports_dir

            builder = ConversionBuilder(settings)

            # Convert
            builder.convert_export(EXAMPLE_EXPORT)

            # Verify files exist
            output_files = list(exports_dir.rglob("*.md"))
            assert len(output_files) == 4

            # Clean
            removed = builder.clean()
            assert removed >= 4

            # Verify files are gone
            output_files = list(exports_dir.rglob("*.md"))
            assert len(output_files) == 0


class TestMarkdownOutputQuality:
    """Tests for the quality of generated Markdown."""

    @pytest.fixture
    def converted_home(self) -> str:
        """Get converted Home page Markdown."""
        settings = Settings.default()
        parser = ExportParser()
        export = parser.parse(EXAMPLE_EXPORT)
        converter = MarkdownConverter(settings)
        home = next((p for p in export.pages if p.title == "Home"), None)
        assert home is not None
        result = converter.convert(home, export)
        return result.markdown

    @pytest.fixture
    def converted_architecture(self) -> str:
        """Get converted Architecture Overview page Markdown."""
        settings = Settings.default()
        parser = ExportParser()
        export = parser.parse(EXAMPLE_EXPORT)
        converter = MarkdownConverter(settings)
        page = next((p for p in export.pages if p.title == "Architecture Overview"), None)
        assert page is not None
        result = converter.convert(page, export)
        return result.markdown

    def test_no_raw_html_tags_in_output(self, converted_home: str) -> None:
        """Ensure common HTML tags are converted."""
        # These raw tags should be converted
        assert "<p>" not in converted_home
        assert "<ul>" not in converted_home
        assert "<li>" not in converted_home

    def test_frontmatter_valid_yaml(self, converted_home: str) -> None:
        """Ensure frontmatter is valid YAML."""
        import yaml

        # Extract frontmatter
        lines = converted_home.split("\n")
        assert lines[0] == "---"

        end_idx = -1
        for i, line in enumerate(lines[1:], 1):
            if line == "---":
                end_idx = i
                break

        assert end_idx > 0, "Frontmatter not properly closed"

        frontmatter_yaml = "\n".join(lines[1:end_idx])
        # Should not raise
        data = yaml.safe_load(frontmatter_yaml)
        assert "title" in data

    def test_headings_properly_formatted(self, converted_home: str) -> None:
        """Check that headings are properly formatted."""
        lines = converted_home.split("\n")
        heading_lines = [l for l in lines if l.startswith("#")]

        # Should have some headings
        assert len(heading_lines) > 0

        # All headings should have space after #
        for heading in heading_lines:
            import re
            assert re.match(r"^#+\s+\S", heading), f"Invalid heading: {heading}"

    def test_lists_properly_formatted(self, converted_home: str) -> None:
        """Check that lists are properly formatted."""
        # Should have list items
        assert "- " in converted_home or "1. " in converted_home
