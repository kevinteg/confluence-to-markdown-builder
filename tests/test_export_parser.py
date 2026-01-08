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

    def test_depth_root_page(self) -> None:
        """Root pages have depth 0."""
        page = PageNode(id="1", title="Root", body_content="")
        assert page.depth == 0

    def test_depth_child_page(self) -> None:
        """Child pages have correct depth."""
        root = PageNode(id="1", title="Root", body_content="")
        child = PageNode(id="2", title="Child", body_content="", parent=root)
        grandchild = PageNode(id="3", title="Grandchild", body_content="", parent=child)

        assert root.depth == 0
        assert child.depth == 1
        assert grandchild.depth == 2

    def test_path_single_page(self) -> None:
        """Single page path is just the title."""
        page = PageNode(id="1", title="My Page", body_content="")
        assert page.path == "My Page"

    def test_path_nested_pages(self) -> None:
        """Nested pages have full path."""
        root = PageNode(id="1", title="Root", body_content="")
        child = PageNode(id="2", title="Child", body_content="", parent=root)
        grandchild = PageNode(id="3", title="Grandchild", body_content="", parent=child)

        assert grandchild.path == "Root/Child/Grandchild"

    def test_content_hash(self) -> None:
        """Content hash is consistent."""
        page1 = PageNode(id="1", title="Page", body_content="Hello World")
        page2 = PageNode(id="2", title="Different", body_content="Hello World")
        page3 = PageNode(id="3", title="Page", body_content="Different content")

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

    def test_parse_directory_without_entities(self) -> None:
        """Raises error for directory without entities.xml."""
        parser = ExportParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValueError, match="entities.xml not found"):
                parser.parse(tmpdir)

    def test_parse_minimal_export(self) -> None:
        """Parses a minimal valid export."""
        parser = ExportParser()
        with tempfile.TemporaryDirectory() as tmpdir:
            entities_xml = Path(tmpdir) / "entities.xml"
            entities_xml.write_text(
                """<?xml version="1.0" encoding="UTF-8"?>
                <hibernate-generic>
                    <object class="Space" package="com.atlassian.confluence.spaces">
                        <id name="id">1</id>
                        <property name="key"><![CDATA[TEST]]></property>
                        <property name="name"><![CDATA[Test Space]]></property>
                    </object>
                    <object class="Page" package="com.atlassian.confluence.pages">
                        <id name="id">100</id>
                        <property name="title"><![CDATA[Test Page]]></property>
                        <property name="contentStatus">current</property>
                        <property name="position">0</property>
                    </object>
                </hibernate-generic>
                """
            )

            export = parser.parse(tmpdir)

            assert export.space.key == "TEST"
            assert export.space.name == "Test Space"
            assert len(export.root_pages) == 1
            assert export.root_pages[0].title == "Test Page"


class TestConfluenceExport:
    """Tests for ConfluenceExport class."""

    def test_walk_pages_order(self) -> None:
        """walk_pages returns pages in tree order."""
        root1 = PageNode(id="1", title="Root 1", body_content="", position=0)
        root2 = PageNode(id="2", title="Root 2", body_content="", position=1)
        child1 = PageNode(
            id="3", title="Child 1", body_content="", parent=root1, position=0
        )
        root1.children = [child1]

        export = ConfluenceExport(
            path=Path("."),
            space=Space(id="1", key="TEST", name="Test"),
            root_pages=[root1, root2],
            pages_by_id={"1": root1, "2": root2, "3": child1},
        )

        pages = list(export.walk_pages())
        assert [p.title for p in pages] == ["Root 1", "Child 1", "Root 2"]

    def test_get_page_by_path(self) -> None:
        """get_page_by_path finds correct page."""
        root = PageNode(id="1", title="Root", body_content="", position=0)
        child = PageNode(id="2", title="Child", body_content="", parent=root, position=0)
        root.children = [child]

        export = ConfluenceExport(
            path=Path("."),
            space=Space(id="1", key="TEST", name="Test"),
            root_pages=[root],
            pages_by_id={"1": root, "2": child},
        )

        assert export.get_page_by_path("Root") == root
        assert export.get_page_by_path("Root/Child") == child
        assert export.get_page_by_path("Nonexistent") is None

    def test_all_pages(self) -> None:
        """all_pages returns flat list."""
        root = PageNode(id="1", title="Root", body_content="", position=0)
        child = PageNode(id="2", title="Child", body_content="", parent=root, position=0)
        root.children = [child]

        export = ConfluenceExport(
            path=Path("."),
            space=Space(id="1", key="TEST", name="Test"),
            root_pages=[root],
            pages_by_id={"1": root, "2": child},
        )

        assert len(export.all_pages) == 2
