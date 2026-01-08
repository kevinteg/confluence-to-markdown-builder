"""Parse Confluence XML exports and build page tree."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator
import hashlib
import zipfile
import tempfile
import shutil

from lxml import etree


@dataclass
class Space:
    """Represents a Confluence space."""

    id: str
    key: str
    name: str
    home_page_id: str | None = None


@dataclass
class PageNode:
    """A page in the hierarchy tree."""

    id: str
    title: str
    body_content: str  # Raw storage format XML
    parent: "PageNode | None" = None
    children: list["PageNode"] = field(default_factory=list)
    position: int = 0
    created_date: datetime | None = None
    modified_date: datetime | None = None
    labels: list[str] = field(default_factory=list)

    @property
    def depth(self) -> int:
        """Depth in tree (0 = root)."""
        depth = 0
        node = self.parent
        while node is not None:
            depth += 1
            node = node.parent
        return depth

    @property
    def path(self) -> str:
        """Full path like 'Parent/Child/This Page'."""
        parts = []
        node: PageNode | None = self
        while node is not None:
            parts.append(node.title)
            node = node.parent
        return "/".join(reversed(parts))

    @property
    def content_hash(self) -> str:
        """SHA256 hash of the body content for change detection."""
        return hashlib.sha256(self.body_content.encode()).hexdigest()


@dataclass
class ConfluenceExport:
    """Represents a parsed Confluence export."""

    path: Path
    space: Space
    root_pages: list[PageNode]
    pages_by_id: dict[str, PageNode]

    def walk_pages(self) -> Iterator[PageNode]:
        """Iterate all pages in tree order (depth-first)."""

        def walk_node(node: PageNode) -> Iterator[PageNode]:
            yield node
            for child in sorted(node.children, key=lambda p: p.position):
                yield from walk_node(child)

        for root in sorted(self.root_pages, key=lambda p: p.position):
            yield from walk_node(root)

    def get_page_by_path(self, path: str) -> PageNode | None:
        """Get page by hierarchy path like 'Parent/Child/Grandchild'."""
        parts = path.split("/")
        for root in self.root_pages:
            if root.title == parts[0]:
                node = root
                for part in parts[1:]:
                    found = None
                    for child in node.children:
                        if child.title == part:
                            found = child
                            break
                    if found is None:
                        return None
                    node = found
                return node
        return None

    @property
    def all_pages(self) -> list[PageNode]:
        """Return all pages as a flat list."""
        return list(self.walk_pages())


class ExportParser:
    """Parses Confluence XML exports."""

    def parse(self, path: str | Path) -> ConfluenceExport:
        """Parse an export ZIP or extracted directory.

        Args:
            path: Path to the export ZIP file or extracted directory.

        Returns:
            ConfluenceExport containing the parsed space and page tree.

        Raises:
            FileNotFoundError: If the path doesn't exist.
            ValueError: If the export format is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Export not found: {path}")

        if path.is_file() and path.suffix == ".zip":
            return self._parse_zip(path)
        elif path.is_dir():
            return self._parse_directory(path)
        else:
            raise ValueError(f"Invalid export path: {path} (expected ZIP file or directory)")

    def _parse_zip(self, zip_path: Path) -> ConfluenceExport:
        """Parse a ZIP export file."""
        temp_dir = tempfile.mkdtemp(prefix="confluence-export-")
        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(temp_dir)
            export = self._parse_directory(Path(temp_dir))
            export.path = zip_path
            return export
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _parse_directory(self, dir_path: Path) -> ConfluenceExport:
        """Parse an extracted export directory."""
        entities_path = dir_path / "entities.xml"
        if not entities_path.exists():
            raise ValueError(f"entities.xml not found in export: {dir_path}")

        space, pages, body_contents = self._parse_entities_xml(entities_path)
        root_pages, pages_by_id = self._build_page_tree(pages, body_contents, space)

        return ConfluenceExport(
            path=dir_path,
            space=space,
            root_pages=root_pages,
            pages_by_id=pages_by_id,
        )

    def _parse_entities_xml(
        self, xml_path: Path
    ) -> tuple[Space, list[dict], dict[str, str]]:
        """Parse the entities.xml file.

        Returns:
            Tuple of (Space, list of page dicts, dict of body contents by id).
        """
        tree = etree.parse(str(xml_path))
        root = tree.getroot()

        # Find the space
        space = self._parse_space(root)

        # Find all pages
        pages = self._parse_pages(root)

        # Find all body contents
        body_contents = self._parse_body_contents(root)

        return space, pages, body_contents

    def _parse_space(self, root: etree._Element) -> Space:
        """Parse Space object from XML."""
        space_elem = root.find(".//object[@class='Space']")
        if space_elem is None:
            raise ValueError("No Space found in entities.xml")

        space_id = self._get_id(space_elem)
        key = self._get_property_text(space_elem, "key") or ""
        name = self._get_property_text(space_elem, "name") or key

        home_page_elem = space_elem.find(".//property[@name='homePage']")
        home_page_id = None
        if home_page_elem is not None:
            id_elem = home_page_elem.find("id")
            if id_elem is not None and id_elem.text:
                home_page_id = id_elem.text

        return Space(id=space_id, key=key, name=name, home_page_id=home_page_id)

    def _parse_pages(self, root: etree._Element) -> list[dict]:
        """Parse all Page objects from XML."""
        pages = []
        for page_elem in root.findall(".//object[@class='Page']"):
            content_status = self._get_property_text(page_elem, "contentStatus")
            if content_status != "current":
                continue

            page_id = self._get_id(page_elem)
            title = self._get_property_text(page_elem, "title") or f"Untitled-{page_id}"
            position = int(self._get_property_text(page_elem, "position") or "0")

            parent_elem = page_elem.find(".//property[@name='parent']")
            parent_id = None
            if parent_elem is not None:
                parent_id_elem = parent_elem.find("id")
                if parent_id_elem is not None and parent_id_elem.text:
                    parent_id = parent_id_elem.text

            created_date = self._parse_date(
                self._get_property_text(page_elem, "creationDate")
            )
            modified_date = self._parse_date(
                self._get_property_text(page_elem, "lastModificationDate")
            )

            # Get body content IDs from collection
            body_content_ids = []
            body_contents_elem = page_elem.find(".//collection[@name='bodyContents']")
            if body_contents_elem is not None:
                for elem in body_contents_elem.findall(".//element"):
                    id_elem = elem.find("id")
                    if id_elem is not None and id_elem.text:
                        body_content_ids.append(id_elem.text)

            pages.append(
                {
                    "id": page_id,
                    "title": title,
                    "parent_id": parent_id,
                    "position": position,
                    "created_date": created_date,
                    "modified_date": modified_date,
                    "body_content_ids": body_content_ids,
                }
            )

        return pages

    def _parse_body_contents(self, root: etree._Element) -> dict[str, str]:
        """Parse all BodyContent objects from XML."""
        body_contents = {}
        for bc_elem in root.findall(".//object[@class='BodyContent']"):
            bc_id = self._get_id(bc_elem)
            body_type = self._get_property_text(bc_elem, "bodyType")
            if body_type != "2":  # Only storage format
                continue
            body = self._get_property_text(bc_elem, "body") or ""
            body_contents[bc_id] = body
        return body_contents

    def _build_page_tree(
        self, pages: list[dict], body_contents: dict[str, str], space: Space
    ) -> tuple[list[PageNode], dict[str, PageNode]]:
        """Build hierarchical page tree from flat page list."""
        # Create PageNode objects
        pages_by_id: dict[str, PageNode] = {}
        parent_map: dict[str, str | None] = {}

        for page_data in pages:
            # Get body content
            body = ""
            for bc_id in page_data.get("body_content_ids", []):
                if bc_id in body_contents:
                    body = body_contents[bc_id]
                    break

            node = PageNode(
                id=page_data["id"],
                title=page_data["title"],
                body_content=body,
                position=page_data["position"],
                created_date=page_data["created_date"],
                modified_date=page_data["modified_date"],
            )
            pages_by_id[node.id] = node
            parent_map[node.id] = page_data.get("parent_id")

        # Build parent-child relationships
        root_pages = []
        for page_id, node in pages_by_id.items():
            parent_id = parent_map.get(page_id)
            if parent_id and parent_id in pages_by_id:
                parent_node = pages_by_id[parent_id]
                node.parent = parent_node
                parent_node.children.append(node)
            else:
                root_pages.append(node)

        return root_pages, pages_by_id

    def _get_id(self, elem: etree._Element) -> str:
        """Get the id value from an object element."""
        id_elem = elem.find("id")
        if id_elem is not None and id_elem.text:
            return id_elem.text
        raise ValueError("Element has no id")

    def _get_property_text(self, elem: etree._Element, name: str) -> str | None:
        """Get text value of a property by name."""
        prop = elem.find(f".//property[@name='{name}']")
        if prop is not None and prop.text:
            return prop.text.strip()
        return None

    def _parse_date(self, date_str: str | None) -> datetime | None:
        """Parse a date string from Confluence format."""
        if not date_str:
            return None
        try:
            return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
