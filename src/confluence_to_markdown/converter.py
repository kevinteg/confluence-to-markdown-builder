"""Convert Confluence storage format to Markdown."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from fnmatch import fnmatch
from typing import Any

from confluence_content_parser import ConfluenceParser
from confluence_content_parser.nodes import (
    Fragment,
    HeadingElement,
    TextBreakElement,
    TextEffectElement,
    ListElement,
    ListItem,
    Table,
    TableRow,
    TableCell,
    LinkElement,
    Image,
    CodeMacro,
    PanelMacro,
    ExpandMacro,
    Text,
    HeadingType,
    TextEffectType,
    ListType,
)

from confluence_to_markdown.config import Settings
from confluence_to_markdown.export_parser import ConfluenceExport, PageNode


@dataclass
class ConversionResult:
    """Result of converting a single page."""

    markdown: str
    frontmatter: dict[str, Any] | None = None
    warnings: list[str] = field(default_factory=list)
    skipped_sections: list[str] = field(default_factory=list)
    unknown_macros: list[str] = field(default_factory=list)


class MarkdownConverter:
    """Converts Confluence storage format to Markdown."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.parser = ConfluenceParser()

    def convert(self, page: PageNode, export: ConfluenceExport) -> ConversionResult:
        """Convert a single page to Markdown.

        Args:
            page: The page to convert.
            export: The full export (for resolving internal links).

        Returns:
            ConversionResult with the Markdown content and metadata.
        """
        warnings: list[str] = []
        skipped_sections: list[str] = []
        unknown_macros: list[str] = []

        if not page.body_content.strip():
            markdown = ""
        else:
            try:
                document = self.parser.parse(page.body_content)
                context = ConversionContext(
                    export=export,
                    current_page=page,
                    settings=self.settings,
                    warnings=warnings,
                    skipped_sections=skipped_sections,
                    unknown_macros=unknown_macros,
                )
                markdown = self._convert_document(document, context)
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
            skipped_sections=skipped_sections,
            unknown_macros=unknown_macros,
        )

    def _build_frontmatter(self, page: PageNode) -> dict[str, Any]:
        """Build frontmatter dictionary for a page."""
        frontmatter: dict[str, Any] = {}
        fields = self.settings.content.frontmatter_fields

        if "title" in fields:
            frontmatter["title"] = page.title
        if "created_date" in fields and page.created_date:
            frontmatter["created_date"] = page.created_date.isoformat()
        if "modified_date" in fields and page.modified_date:
            frontmatter["modified_date"] = page.modified_date.isoformat()
        if "labels" in fields and page.labels:
            frontmatter["labels"] = page.labels

        return frontmatter

    def _format_frontmatter(self, frontmatter: dict[str, Any]) -> str:
        """Format frontmatter as YAML."""
        lines = ["---"]
        for key, value in frontmatter.items():
            if isinstance(value, list):
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {item}")
            elif isinstance(value, str) and ("\n" in value or ":" in value):
                lines.append(f'{key}: "{value}"')
            else:
                lines.append(f"{key}: {value}")
        lines.append("---")
        return "\n".join(lines)

    def _convert_document(self, document: Any, context: ConversionContext) -> str:
        """Convert a parsed document to Markdown."""
        parts: list[str] = []
        heading_path: list[str] = []
        skip_until_heading_level: int | None = None

        root = document.root
        if not hasattr(root, 'children'):
            return document.text or ""

        for node in root.children:
            # Handle heading hierarchy for section filtering
            if isinstance(node, HeadingElement):
                level = self._get_heading_level(node)
                text = self._get_node_text(node)

                # Reset skip state if we've gone back up in heading hierarchy
                if skip_until_heading_level is not None and level <= skip_until_heading_level:
                    skip_until_heading_level = None

                # Update heading path
                while heading_path and len(heading_path) >= level:
                    heading_path.pop()
                heading_path.append(text)

                # Check if this section should be skipped
                if self._should_skip_section(heading_path, context):
                    context.skipped_sections.append("/".join(heading_path))
                    skip_until_heading_level = level
                    continue

            # Skip content if we're in a skipped section
            if skip_until_heading_level is not None:
                continue

            # Convert the node
            md = self._convert_node(node, context)
            if md:
                parts.append(md)

        return "\n\n".join(parts)

    def _should_skip_section(
        self, heading_path: list[str], context: ConversionContext
    ) -> bool:
        """Check if current section should be excluded per settings."""
        path_str = "/".join(heading_path)
        for pattern in self.settings.exclude_sections:
            if fnmatch(path_str, pattern):
                return True
        return False

    def _get_heading_level(self, node: HeadingElement) -> int:
        """Get numeric heading level from HeadingElement."""
        type_to_level = {
            HeadingType.H1: 1,
            HeadingType.H2: 2,
            HeadingType.H3: 3,
            HeadingType.H4: 4,
            HeadingType.H5: 5,
            HeadingType.H6: 6,
        }
        return type_to_level.get(node.type, 1)

    def _get_node_text(self, node: Any) -> str:
        """Recursively extract text content from a node and its children."""
        if isinstance(node, Text):
            return node.text or ""

        parts = []
        if hasattr(node, 'children'):
            for child in node.children:
                parts.append(self._get_node_text(child))

        return "".join(parts)

    def _convert_node(self, node: Any, context: ConversionContext) -> str:
        """Convert a single parsed node to Markdown."""
        if isinstance(node, HeadingElement):
            level = min(self._get_heading_level(node), self.settings.output.max_heading_level)
            text = self._get_node_text(node)
            return f"{'#' * level} {text}"

        elif isinstance(node, TextBreakElement):
            # Paragraphs and line breaks
            return self._convert_text_element(node, context)

        elif isinstance(node, Text):
            return node.text or ""

        elif isinstance(node, TextEffectElement):
            return self._convert_text_effect(node, context)

        elif isinstance(node, ListElement):
            return self._convert_list(node, context)

        elif isinstance(node, Table):
            return self._convert_table(node, context)

        elif isinstance(node, LinkElement):
            return self._convert_link(node, context)

        elif isinstance(node, Image):
            return self._convert_image(node, context)

        elif isinstance(node, CodeMacro):
            return self._convert_code_macro(node, context)

        elif isinstance(node, PanelMacro):
            return self._convert_panel_macro(node, context)

        elif isinstance(node, ExpandMacro):
            return self._convert_expand_macro(node, context)

        elif isinstance(node, Fragment):
            # Process children
            parts = []
            for child in node.children:
                md = self._convert_node(child, context)
                if md:
                    parts.append(md)
            return "\n\n".join(parts)

        else:
            # Unknown node type
            node_type = type(node).__name__
            if "Macro" in node_type:
                macro_name = getattr(node, "name", node_type)
                context.unknown_macros.append(macro_name)
                return self._handle_unknown_macro(node, macro_name, context)
            # For other unknown types, just try to get text
            text = self._get_node_text(node)
            return text if text else ""

    def _convert_text_element(self, node: TextBreakElement, context: ConversionContext) -> str:
        """Convert a text break element (paragraph) to Markdown."""
        parts = []
        for child in node.children:
            if isinstance(child, Text):
                parts.append(child.text or "")
            elif isinstance(child, TextEffectElement):
                parts.append(self._convert_text_effect(child, context))
            elif isinstance(child, LinkElement):
                parts.append(self._convert_link(child, context))
            elif isinstance(child, Image):
                parts.append(self._convert_image(child, context))
            else:
                parts.append(self._get_node_text(child))
        return "".join(parts)

    def _convert_text_effect(self, node: TextEffectElement, context: ConversionContext) -> str:
        """Convert text effect (bold, italic, etc.) to Markdown."""
        text = self._get_node_text(node)

        if node.type == TextEffectType.STRONG:
            return f"**{text}**"
        elif node.type == TextEffectType.EMPHASIS:
            return f"*{text}*"
        elif node.type == TextEffectType.MONOSPACE:
            return f"`{text}`"
        elif node.type == TextEffectType.STRIKETHROUGH:
            return f"~~{text}~~"
        elif node.type == TextEffectType.UNDERLINE:
            return f"<u>{text}</u>"
        elif node.type == TextEffectType.SUBSCRIPT:
            return f"<sub>{text}</sub>"
        elif node.type == TextEffectType.SUPERSCRIPT:
            return f"<sup>{text}</sup>"
        elif node.type == TextEffectType.BLOCKQUOTE:
            lines = text.split("\n")
            return "\n".join(f"> {line}" for line in lines)
        else:
            return text

    def _convert_list(self, node: ListElement, context: ConversionContext) -> str:
        """Convert a list element to Markdown."""
        lines = []
        is_ordered = node.type == ListType.ORDERED

        for i, item in enumerate(node.children, 1):
            if isinstance(item, ListItem):
                text = self._get_node_text(item)
                if is_ordered:
                    lines.append(f"{i}. {text}")
                else:
                    lines.append(f"- {text}")

        return "\n".join(lines)

    def _convert_table(self, node: Table, context: ConversionContext) -> str:
        """Convert a table to GFM Markdown."""
        lines = []

        for i, row in enumerate(node.children):
            if isinstance(row, TableRow):
                cells = []
                for cell in row.children:
                    if isinstance(cell, TableCell):
                        cells.append(self._get_node_text(cell))

                lines.append("| " + " | ".join(cells) + " |")

                # Add header separator after first row
                if i == 0:
                    lines.append("| " + " | ".join(["---"] * len(cells)) + " |")

        return "\n".join(lines)

    def _convert_link(self, node: LinkElement, context: ConversionContext) -> str:
        """Convert a link to Markdown."""
        text = self._get_node_text(node)
        href = getattr(node, 'url', "") or getattr(node, 'href', "") or ""

        # Handle internal page links
        page_id = getattr(node, 'page_id', None)
        page_title = getattr(node, 'page_title', None)

        if page_id or page_title:
            return self._convert_internal_link(node, text, context)

        if href:
            return f"[{text}]({href})"
        return text

    def _convert_internal_link(
        self, node: Any, text: str, context: ConversionContext
    ) -> str:
        """Convert an internal Confluence page link."""
        page_id = getattr(node, 'page_id', None)
        page_title = getattr(node, 'page_title', None) or text

        style = self.settings.content.links.internal_link_style

        if style == "title_only":
            return f"[{page_title}]"

        # Try to find the target page
        target_page = None
        if page_id and context.export:
            target_page = context.export.pages_by_id.get(str(page_id))

        if target_page:
            # Calculate relative path
            rel_path = self._calculate_relative_path(
                context.current_page, target_page
            )
            return f"[{text or target_page.title}]({rel_path})"
        else:
            # Missing page link
            missing_handling = self.settings.content.links.missing_page_links
            context.warnings.append(f"Link target not found: {page_title}")

            if missing_handling == "comment":
                return f"<!-- Link to missing page: {page_title} -->[{text}]"
            elif missing_handling == "strip":
                return text
            else:  # preserve
                return f"[{text}]"

    def _calculate_relative_path(
        self, from_page: PageNode, to_page: PageNode
    ) -> str:
        """Calculate relative path from one page to another."""
        from_parts = from_page.path.split("/")[:-1]  # Directory of source
        to_parts = to_page.path.split("/")

        # Find common prefix
        common = 0
        for i in range(min(len(from_parts), len(to_parts))):
            if from_parts[i] == to_parts[i]:
                common += 1
            else:
                break

        # Build relative path
        up_count = len(from_parts) - common
        rel_parts = [".."] * up_count + to_parts[common:]

        # Convert to filename
        if rel_parts:
            rel_parts[-1] = self._slugify(rel_parts[-1]) + ".md"
        else:
            rel_parts = [self._slugify(to_page.title) + ".md"]

        return "/".join(rel_parts)

    def _slugify(self, text: str) -> str:
        """Convert text to kebab-case slug."""
        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")

    def _convert_image(self, node: Image, context: ConversionContext) -> str:
        """Convert an image to Markdown."""
        alt = getattr(node, 'alt', "") or ""
        src = getattr(node, 'url', "") or getattr(node, 'src', "") or getattr(node, 'filename', "") or ""
        return f"![{alt}]({src})"

    def _convert_code_macro(self, node: CodeMacro, context: ConversionContext) -> str:
        """Convert a code macro to a fenced code block."""
        language = getattr(node, 'language', "") or ""
        code = self._get_node_text(node)
        return f"```{language}\n{code}\n```"

    def _convert_panel_macro(self, node: PanelMacro, context: ConversionContext) -> str:
        """Convert info/warning/note/tip panels to Markdown callouts."""
        panel_type = getattr(node, 'panel_type', "info") or "info"
        content = self._get_node_text(node)

        icons = {
            "info": "Info",
            "warning": "Warning",
            "note": "Note",
            "tip": "Tip",
        }
        header = icons.get(panel_type.lower(), panel_type.title())

        lines = content.split("\n")
        quoted = "\n".join(f"> {line}" for line in lines)
        return f"> **{header}:** {quoted.lstrip('> ')}"

    def _convert_expand_macro(self, node: ExpandMacro, context: ConversionContext) -> str:
        """Convert expand/collapse sections to HTML details."""
        title = getattr(node, 'title', "Details") or "Details"
        content = self._get_node_text(node)
        return f"<details>\n<summary>{title}</summary>\n\n{content}\n\n</details>"

    def _handle_unknown_macro(
        self, node: Any, macro_name: str, context: ConversionContext
    ) -> str:
        """Handle macros without a specific converter."""
        handling = self.settings.content.unknown_macro_handling
        text = self._get_node_text(node)

        if handling == "comment":
            return f"<!-- Unknown macro: {macro_name} -->\n{text}"
        elif handling == "strip":
            return ""
        else:  # preserve_text
            return text


@dataclass
class ConversionContext:
    """Context passed through conversion for state tracking."""

    export: ConfluenceExport
    current_page: PageNode
    settings: Settings
    warnings: list[str] = field(default_factory=list)
    skipped_sections: list[str] = field(default_factory=list)
    unknown_macros: list[str] = field(default_factory=list)
