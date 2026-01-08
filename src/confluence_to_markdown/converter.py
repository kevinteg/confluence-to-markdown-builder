"""Convert HTML to Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from bs4 import BeautifulSoup, NavigableString, Tag

from confluence_to_markdown.config import Settings
from confluence_to_markdown.export_parser import ConfluenceExport, PageNode


@dataclass
class ConversionResult:
    """Result of converting a single page."""

    markdown: str
    frontmatter: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)


class MarkdownConverter:
    """Converts HTML to Markdown."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def convert(self, page: PageNode, export: ConfluenceExport) -> ConversionResult:
        """Convert a single page to Markdown.

        Args:
            page: The page to convert.
            export: The full export (for context).

        Returns:
            ConversionResult with the Markdown content and metadata.
        """
        warnings: list[str] = []

        if not page.body_content.strip():
            markdown = ""
        else:
            try:
                soup = BeautifulSoup(page.body_content, "lxml")
                markdown = self._convert_element(soup, warnings)
                markdown = self._clean_markdown(markdown)
            except Exception as e:
                warnings.append(f"Parse error: {e}")
                markdown = f"<!-- Parse error: {e} -->\n\n{page.body_content}"

        # Build frontmatter if enabled
        frontmatter = None
        if self.settings.content.include_frontmatter:
            frontmatter = self._build_frontmatter(page)

        # Combine frontmatter and markdown
        if frontmatter:
            frontmatter_yaml = self._format_frontmatter(frontmatter)
            markdown = f"{frontmatter_yaml}\n{markdown}"

        return ConversionResult(
            markdown=markdown.strip() + "\n",
            frontmatter=frontmatter,
            warnings=warnings,
        )

    def _build_frontmatter(self, page: PageNode) -> dict[str, Any]:
        """Build frontmatter dictionary for a page."""
        frontmatter: dict[str, Any] = {}
        fields = self.settings.content.frontmatter_fields

        if "title" in fields:
            frontmatter["title"] = page.title

        return frontmatter

    def _format_frontmatter(self, frontmatter: dict[str, Any]) -> str:
        """Format frontmatter as YAML."""
        lines = ["---"]
        for key, value in frontmatter.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            elif isinstance(value, str) and ("\\n" in value or ":" in value):
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        return "\n".join(lines)

    def _convert_element(self, element: Tag | NavigableString, warnings: list[str]) -> str:
        """Convert an HTML element to Markdown."""
        if isinstance(element, NavigableString):
            text = str(element)
            # Preserve whitespace but normalize excessive newlines
            return text

        if not isinstance(element, Tag):
            return ""

        tag_name = element.name.lower() if element.name else ""

        # Skip script and style tags
        if tag_name in ("script", "style", "head", "meta", "link"):
            return ""

        # Handle specific elements
        if tag_name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return self._convert_heading(element, warnings)
        elif tag_name == "p":
            return self._convert_paragraph(element, warnings)
        elif tag_name in ("ul", "ol"):
            return self._convert_list(element, warnings)
        elif tag_name == "li":
            return self._convert_list_item(element, warnings)
        elif tag_name == "table":
            return self._convert_table(element, warnings)
        elif tag_name == "a":
            return self._convert_link(element, warnings)
        elif tag_name == "img":
            return self._convert_image(element)
        elif tag_name in ("pre", "code"):
            return self._convert_code(element, warnings)
        elif tag_name in ("strong", "b"):
            return self._convert_bold(element, warnings)
        elif tag_name in ("em", "i"):
            return self._convert_italic(element, warnings)
        elif tag_name == "u":
            return self._convert_underline(element, warnings)
        elif tag_name == "s":
            return self._convert_strikethrough(element, warnings)
        elif tag_name == "sub":
            return self._convert_subscript(element, warnings)
        elif tag_name == "sup":
            return self._convert_superscript(element, warnings)
        elif tag_name == "blockquote":
            return self._convert_blockquote(element, warnings)
        elif tag_name == "hr":
            return "\n---\n"
        elif tag_name == "br":
            return "  \n"
        elif tag_name in ("div", "span", "section", "article", "main", "body", "html"):
            # Container elements - process children
            return self._convert_children(element, warnings)
        else:
            # Unknown element - just get text content
            return self._convert_children(element, warnings)

    def _convert_children(self, element: Tag, warnings: list[str]) -> str:
        """Convert all children of an element."""
        parts = []
        for child in element.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                parts.append(self._convert_element(child, warnings))
        return "".join(parts)

    def _convert_heading(self, element: Tag, warnings: list[str]) -> str:
        """Convert heading element to Markdown."""
        level = int(element.name[1])  # h1 -> 1, h2 -> 2, etc.
        level = min(level, self.settings.output.max_heading_level)
        text = self._get_text_content(element, warnings).strip()
        return f"\n\n{'#' * level} {text}\n\n"

    def _convert_paragraph(self, element: Tag, warnings: list[str]) -> str:
        """Convert paragraph element to Markdown."""
        content = self._convert_children(element, warnings).strip()
        if content:
            return f"\n\n{content}\n\n"
        return ""

    def _convert_list(self, element: Tag, warnings: list[str]) -> str:
        """Convert list element to Markdown."""
        is_ordered = element.name.lower() == "ol"
        items = []
        counter = 1

        for child in element.children:
            if isinstance(child, Tag) and child.name.lower() == "li":
                item_content = self._get_text_content(child, warnings).strip()
                if is_ordered:
                    items.append(f"{counter}. {item_content}")
                    counter += 1
                else:
                    items.append(f"- {item_content}")

        return "\n\n" + "\n".join(items) + "\n\n"

    def _convert_list_item(self, element: Tag, warnings: list[str]) -> str:
        """Convert a standalone list item (shouldn't happen normally)."""
        content = self._get_text_content(element, warnings).strip()
        return f"- {content}\n"

    def _convert_table(self, element: Tag, warnings: list[str]) -> str:
        """Convert table element to GFM Markdown."""
        rows = []

        # Find all rows (in thead, tbody, or directly in table)
        for row in element.find_all("tr"):
            cells = []
            for cell in row.find_all(["th", "td"]):
                cell_text = self._get_text_content(cell, warnings).strip()
                # Escape pipe characters in cell content
                cell_text = cell_text.replace("|", "\\|")
                cells.append(cell_text)
            if cells:
                rows.append(cells)

        if not rows:
            return ""

        # Build markdown table
        lines = []
        if rows:
            # Header row
            lines.append("| " + " | ".join(rows[0]) + " |")
            # Separator
            lines.append("| " + " | ".join(["---"] * len(rows[0])) + " |")
            # Data rows
            for row in rows[1:]:
                # Pad row to match header length
                while len(row) < len(rows[0]):
                    row.append("")
                lines.append("| " + " | ".join(row) + " |")

        return "\n\n" + "\n".join(lines) + "\n\n"

    def _convert_link(self, element: Tag, warnings: list[str]) -> str:
        """Convert link element to Markdown."""
        href = element.get("href", "")
        text = self._get_text_content(element, warnings).strip()

        if not text:
            text = str(href)

        if href:
            return f"[{text}]({href})"
        return text

    def _convert_image(self, element: Tag) -> str:
        """Convert image element to Markdown."""
        src = element.get("src", "")
        alt = element.get("alt", "")
        return f"![{alt}]({src})"

    def _convert_code(self, element: Tag, warnings: list[str]) -> str:
        """Convert code/pre element to Markdown."""
        # Check if this is a code block (pre) or inline code
        if element.name.lower() == "pre":
            # Try to find language class
            language = ""
            code_elem = element.find("code")
            if code_elem and isinstance(code_elem, Tag):
                classes = code_elem.get("class", [])
                if isinstance(classes, list):
                    for cls in classes:
                        if cls.startswith("language-"):
                            language = cls[9:]
                            break

            code_text = element.get_text()
            return f"\n\n```{language}\n{code_text}\n```\n\n"
        else:
            # Inline code
            code_text = element.get_text()
            return f"`{code_text}`"

    def _convert_bold(self, element: Tag, warnings: list[str]) -> str:
        """Convert bold element to Markdown."""
        content = self._convert_children(element, warnings)
        return f"**{content.strip()}**"

    def _convert_italic(self, element: Tag, warnings: list[str]) -> str:
        """Convert italic element to Markdown."""
        content = self._convert_children(element, warnings)
        return f"*{content.strip()}*"

    def _convert_underline(self, element: Tag, warnings: list[str]) -> str:
        """Convert underline element to HTML (no Markdown equivalent)."""
        content = self._convert_children(element, warnings)
        return f"<u>{content}</u>"

    def _convert_strikethrough(self, element: Tag, warnings: list[str]) -> str:
        """Convert strikethrough element to Markdown."""
        content = self._convert_children(element, warnings)
        return f"~~{content.strip()}~~"

    def _convert_subscript(self, element: Tag, warnings: list[str]) -> str:
        """Convert subscript element to HTML."""
        content = self._convert_children(element, warnings)
        return f"<sub>{content}</sub>"

    def _convert_superscript(self, element: Tag, warnings: list[str]) -> str:
        """Convert superscript element to HTML."""
        content = self._convert_children(element, warnings)
        return f"<sup>{content}</sup>"

    def _convert_blockquote(self, element: Tag, warnings: list[str]) -> str:
        """Convert blockquote element to Markdown."""
        content = self._convert_children(element, warnings).strip()
        lines = content.split("\n")
        quoted = "\n".join(f"> {line}" for line in lines)
        return f"\n\n{quoted}\n\n"

    def _get_text_content(self, element: Tag, warnings: list[str]) -> str:
        """Get text content with inline formatting preserved."""
        return self._convert_children(element, warnings)

    def _clean_markdown(self, markdown: str) -> str:
        """Clean up the generated Markdown."""
        # Remove excessive newlines (more than 2)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)

        # Remove leading/trailing whitespace from lines
        lines = markdown.split("\n")
        lines = [line.rstrip() for line in lines]
        markdown = "\n".join(lines)

        # Ensure single newline at end
        markdown = markdown.strip() + "\n"

        return markdown
