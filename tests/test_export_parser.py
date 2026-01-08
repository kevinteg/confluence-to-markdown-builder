"""Tests for the export parser module."""

import tempfile
from pathlib import Path

import pytest

from confluence_to_markdown.export_parser import (
    ConfluenceExport,
    ExportParser,
    PageNode,
    Space,
)


class TestPageNode:
    """Tests for PageNode class."""

    def test_content_hash(self) -> None:
        """Content hash is consistent."""
        page1 = PageNode(id="1", title="Page", body_content="Hello World", filename="test.html")
        page2 = PageNode(id="2", title="Different", body_content="Hello World", filename="test2.html")
        page3 = PageNode(id="3", title="Page", body_content="Different content", filename="test3.html")

        assert page1.content_hash == page2.content_hash
        assert page1.content_hash != page3.content_hash


class TestExportParser:
    """Tests for ExportParser class."""

    def test_parse_nonexistent_path(self) -> None:
        """Raises error for nonexistent path."""
        parser = ExportParser()
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/path")

    def test_parse_invalid_file(self) -> None:
        """Raises error for invalid file type."""
        parser = ExportParser()
        with tempfile.NamedTemporaryFile(suffix=".txt") as f:
            with pytest.raises(ValueError):
                parser.parse(f.name)

    def test_parse_directory_without_html(self) -> None:
        """Raises error for directory without HTML files."""
        parser = ExportParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="No HTML files found"):
                parser.parse(tmpdir)

    def test_parse_minimal_export(self) -> None:
        """Parses a minimal valid export."""
        parser = ExportParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            html_file = Path(tmpdir) / "test-page.html"
            html_file.write_text(
                """<!DOCTYPE html>
                <html>
                <head><title>Test Page</title></head>
                <body>
                <div id="main-content">
                    <h1>Test Page</h1>
                    <p>Some content here.</p>
                </div>
                </body>
                </html>
                """
            )

            export = parser.parse(tmpdir)

            assert len(export.pages) == 1
            assert export.pages[0].title == "Test Page"

    def test_parse_multiple_html_files(self) -> None:
        """Parses multiple HTML files from directory."""
        parser = ExportParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first HTML file
            html1 = Path(tmpdir) / "page1.html"
            html1.write_text(
                """<!DOCTYPE html>
                <html>
                <head><title>Page 1</title></head>
                <body><p>Content 1</p></body>
                </html>
                """
            )

            # Create second HTML file
            html2 = Path(tmpdir) / "page2.html"
            html2.write_text(
                """<!DOCTYPE html>
                <html>
                <head><title>Page 2</title></head>
                <body><p>Content 2</p></body>
                </html>
                """
            )

            export = parser.parse(tmpdir)

            assert len(export.pages) == 2
            titles = {p.title for p in export.pages}
            assert "Page 1" in titles
            assert "Page 2" in titles


class TestConfluenceExport:
    """Tests for ConfluenceExport class."""

    def test_walk_pages(self) -> None:
        """walk_pages returns all pages."""
        page1 = PageNode(id="1", title="Page 1", body_content="content", filename="p1.html")
        page2 = PageNode(id="2", title="Page 2", body_content="content", filename="p2.html")

        export = ConfluenceExport(
            path=Path("."),
            space=Space(key="TEST", name="Test"),
            pages=[page1, page2],
        )

        pages = list(export.walk_pages())
        assert len(pages) == 2

    def test_all_pages(self) -> None:
        """all_pages returns flat list."""
        page1 = PageNode(id="1", title="Page 1", body_content="content", filename="p1.html")
        page2 = PageNode(id="2", title="Page 2", body_content="content", filename="p2.html")

        export = ConfluenceExport(
            path=Path("."),
            space=Space(key="TEST", name="Test"),
            pages=[page1, page2],
        )

        assert len(export.all_pages) == 2

    def test_pages_by_id(self) -> None:
        """pages_by_id is built correctly."""
        page1 = PageNode(id="abc", title="Page 1", body_content="content", filename="p1.html")
        page2 = PageNode(id="def", title="Page 2", body_content="content", filename="p2.html")

        export = ConfluenceExport(
            path=Path("."),
            space=Space(key="TEST", name="Test"),
            pages=[page1, page2],
        )

        assert export.pages_by_id["abc"] == page1
        assert export.pages_by_id["def"] == page2
