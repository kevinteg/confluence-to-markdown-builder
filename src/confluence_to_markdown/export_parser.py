"""Parse Confluence HTML exports and extract pages."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator
import hashlib
import re
import zipfile
import tempfile
import shutil

from bs4 import BeautifulSoup


@dataclass
class Space:
    """Represents a Confluence space."""

    key: str
    name: str


@dataclass
class PageNode:
    """A page extracted from the HTML export."""

    id: str
    title: str
    body_content: str  # Raw HTML content
    filename: str  # Original filename

    @property
    def content_hash(self) -> str:
        """SHA256 hash of the body content for change detection."""
        return hashlib.sha256(self.body_content.encode()).hexdigest()


@dataclass
class ConfluenceExport:
    """Represents a parsed Confluence HTML export."""

    path: Path
    space: Space
    pages: list[PageNode]
    pages_by_id: dict[str, PageNode] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Build pages_by_id index."""
        self.pages_by_id = {page.id: page for page in self.pages}

    def walk_pages(self) -> Iterator[PageNode]:
        """Iterate all pages."""
        yield from self.pages

    @property
    def all_pages(self) -> list[PageNode]:
        """Return all pages as a flat list."""
        return self.pages


class ExportParser:
    """Parses Confluence HTML exports."""

    def parse(self, path: str | Path) -> ConfluenceExport:
        """Parse an export ZIP or extracted directory.

        Args:
            path: Path to the export ZIP file or extracted directory.

        Returns:
            ConfluenceExport containing the parsed pages.

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
        # Find all HTML files
        html_files = list(dir_path.rglob("*.html"))
        if not html_files:
            raise ValueError(f"No HTML files found in export: {dir_path}")

        pages = []
        space_name = None

        for html_file in html_files:
            page = self._parse_html_file(html_file)
            if page:
                pages.append(page)
                # Try to extract space name from directory structure
                if space_name is None:
                    space_name = self._extract_space_name(html_file, dir_path)

        if not pages:
            raise ValueError(f"No valid pages found in export: {dir_path}")

        # Create space from directory name or extracted name
        space = Space(
            key=space_name or dir_path.name,
            name=space_name or dir_path.name,
        )

        return ConfluenceExport(
            path=dir_path,
            space=space,
            pages=pages,
        )

    def _parse_html_file(self, html_path: Path) -> PageNode | None:
        """Parse a single HTML file into a PageNode."""
        try:
            content = html_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            try:
                content = html_path.read_text(encoding="latin-1")
            except Exception:
                return None

        soup = BeautifulSoup(content, "lxml")

        # Extract title
        title = self._extract_title(soup, html_path)

        # Extract body content
        body = self._extract_body(soup)

        if not body.strip():
            return None

        # Generate ID from filename
        page_id = self._generate_id(html_path)

        return PageNode(
            id=page_id,
            title=title,
            body_content=body,
            filename=html_path.name,
        )

    def _extract_title(self, soup: BeautifulSoup, html_path: Path) -> str:
        """Extract page title from HTML."""
        # Try <title> tag first
        title_tag = soup.find("title")
        if title_tag and title_tag.string:
            title = title_tag.string.strip()
            # Clean up common suffixes like " - Space Name"
            if " - " in title:
                title = title.split(" - ")[0].strip()
            if title:
                return title

        # Try first <h1>
        h1_tag = soup.find("h1")
        if h1_tag:
            title = h1_tag.get_text(strip=True)
            if title:
                return title

        # Fallback to filename without extension
        return html_path.stem

    def _extract_body(self, soup: BeautifulSoup) -> str:
        """Extract body content from HTML."""
        # Look for main content areas common in Confluence exports
        content_selectors = [
            "div#main-content",
            "div.wiki-content",
            "div#content",
            "article",
            "main",
            "body",
        ]

        for selector in content_selectors:
            content = soup.select_one(selector)
            if content:
                return str(content)

        # Fallback to entire body
        body = soup.find("body")
        if body:
            return str(body)

        return str(soup)

    def _extract_space_name(self, html_path: Path, base_path: Path) -> str | None:
        """Try to extract space name from the export structure."""
        relative = html_path.relative_to(base_path)
        parts = relative.parts

        # Common patterns: space_name/page.html or just page.html
        if len(parts) > 1:
            return parts[0]

        return None

    def _generate_id(self, html_path: Path) -> str:
        """Generate a unique ID for a page based on its path."""
        # Use hash of the path for consistent IDs
        path_str = str(html_path.resolve())
        return hashlib.md5(path_str.encode()).hexdigest()[:12]

    def _slugify(self, text: str) -> str:
        """Convert text to kebab-case slug."""
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")
