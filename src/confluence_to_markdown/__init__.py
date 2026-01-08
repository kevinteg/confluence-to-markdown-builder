"""Confluence XML Export to Markdown Converter.

A Python library and CLI tool for converting Confluence space XML exports
to Markdown files with preserved hierarchy and configurable filtering.
"""

from confluence_to_markdown.config import Settings
from confluence_to_markdown.export_parser import (
    ConfluenceExport,
    ExportParser,
    PageNode,
    Space,
)
from confluence_to_markdown.converter import ConversionResult, MarkdownConverter
from confluence_to_markdown.builder import BuildResult, ConversionBuilder

__version__ = "0.1.0"

__all__ = [
    "Settings",
    "ExportParser",
    "ConfluenceExport",
    "PageNode",
    "Space",
    "MarkdownConverter",
    "ConversionResult",
    "ConversionBuilder",
    "BuildResult",
]
