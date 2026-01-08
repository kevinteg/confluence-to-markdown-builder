"""Make-like build orchestration for incremental conversion."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from confluence_to_markdown.config import Settings
from confluence_to_markdown.converter import ConversionResult, MarkdownConverter
from confluence_to_markdown.export_parser import ConfluenceExport, ExportParser, PageNode

logger = logging.getLogger(__name__)


@dataclass
class PageConversionReport:
    """Detailed report for a single page conversion."""

    page_id: str
    page_title: str
    output_file: str
    status: Literal["success", "partial", "failed"]
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    conversion_time_ms: int = 0


@dataclass
class BuildResult:
    """Result of a full build operation."""

    pages_converted: int
    pages_skipped: int
    pages_failed: int
    total_time_ms: int
    page_reports: list[PageConversionReport] = field(default_factory=list)


@dataclass
class PageState:
    """State of a single page in the build cache."""

    title: str
    output_path: str
    content_hash: str
    converted_at: str


@dataclass
class ExportState:
    """State of a single export in the build cache."""

    source_path: str
    source_mtime: str
    source_hash: str
    pages: dict[str, PageState] = field(default_factory=dict)


@dataclass
class BuildState:
    """Full build state for incremental builds."""

    version: str = "1.0"
    settings_hash: str = ""
    exports: dict[str, ExportState] = field(default_factory=dict)


class ConversionBuilder:
    """Orchestrates conversion with caching and incremental builds."""

    STATE_FILE = ".confluence-build-state.json"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.parser = ExportParser()
        self.converter = MarkdownConverter(settings)
        self.state = self._load_state()

    def convert_export(
        self,
        export_path: str | Path,
        force: bool = False,
    ) -> BuildResult:
        """Convert an export with incremental build logic.

        Args:
            export_path: Path to the export ZIP or directory.
            force: If True, reconvert all pages regardless of cache.

        Returns:
            BuildResult with conversion statistics and reports.
        """
        start_time = time.time()
        export_path = Path(export_path)

        logger.info(f"Starting conversion of export: {export_path.name}")

        # Parse the export
        export = self.parser.parse(export_path)
        logger.info(f"Parsed {len(export.pages_by_id)} pages from HTML files")

        # Determine which pages need conversion
        pages_to_convert = self._determine_pages_to_convert(export, force)
        logger.info(
            f"{len(pages_to_convert)} pages need conversion "
            f"({len(export.pages_by_id) - len(pages_to_convert)} unchanged)"
        )

        # Convert pages
        reports: list[PageConversionReport] = []
        pages_converted = 0
        pages_failed = 0

        for page in pages_to_convert:
            report = self._convert_page(page, export)
            reports.append(report)

            if report.status == "failed":
                pages_failed += 1
            else:
                pages_converted += 1

        # Update and save state
        self._update_state(export, reports)
        self._save_state()

        total_time_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Conversion complete: {pages_converted} pages converted, "
            f"{pages_failed} failed, {total_time_ms}ms"
        )

        return BuildResult(
            pages_converted=pages_converted,
            pages_skipped=len(export.pages_by_id) - len(pages_to_convert),
            pages_failed=pages_failed,
            total_time_ms=total_time_ms,
            page_reports=reports,
        )

    def get_status(self) -> dict:
        """Get current status of exports and build state."""
        return {
            "state_file_exists": Path(self.STATE_FILE).exists(),
            "exports_in_state": list(self.state.exports.keys()),
            "settings_hash": self.state.settings_hash,
        }

    def clean(self) -> int:
        """Remove all generated files and build state.

        Returns:
            Number of files removed.
        """
        removed = 0

        # Remove export directory contents
        exports_dir = self.settings.exports_dir
        if exports_dir.exists():
            for item in exports_dir.rglob("*"):
                if item.is_file() and item.name != ".gitkeep":
                    item.unlink()
                    removed += 1

        # Remove state file
        state_file = Path(self.STATE_FILE)
        if state_file.exists():
            state_file.unlink()
            removed += 1

        self.state = BuildState()

        logger.info(f"Cleaned {removed} files")
        return removed

    def _determine_pages_to_convert(
        self, export: ConfluenceExport, force: bool
    ) -> list[PageNode]:
        """Determine which pages need conversion."""
        pages_to_convert: list[PageNode] = []

        # Check if settings changed (forces full rebuild)
        current_settings_hash = self._hash_settings()
        if self.state.settings_hash != current_settings_hash:
            logger.info("Settings changed, forcing full rebuild")
            return export.all_pages

        export_name = export.path.name
        export_state = self.state.exports.get(export_name)

        for page in export.walk_pages():
            should_convert = False
            reason = ""

            if force:
                should_convert = True
                reason = "forced"
            elif export_state is None:
                should_convert = True
                reason = "new export"
            else:
                page_state = export_state.pages.get(page.id)
                if page_state is None:
                    should_convert = True
                    reason = "new page"
                elif not Path(page_state.output_path).exists():
                    should_convert = True
                    reason = "output missing"
                elif page.content_hash != page_state.content_hash:
                    should_convert = True
                    reason = "content changed"

            if should_convert:
                logger.debug(f"Will convert '{page.title}': {reason}")
                pages_to_convert.append(page)
            else:
                logger.debug(f"Skipping '{page.title}': unchanged")

        return pages_to_convert

    def _convert_page(
        self, page: PageNode, export: ConfluenceExport
    ) -> PageConversionReport:
        """Convert a single page and write to disk."""
        start_time = time.time()
        output_path = self._get_output_path(page, export)

        logger.info(f"Converting: {page.title}")

        try:
            result: ConversionResult = self.converter.convert(page, export)

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            output_path.write_text(result.markdown)

            # Log warnings
            for warning in result.warnings:
                logger.warning(f"  {warning}")

            conversion_time_ms = int((time.time() - start_time) * 1000)

            status: Literal["success", "partial", "failed"] = "success"
            if result.warnings:
                status = "partial"

            return PageConversionReport(
                page_id=page.id,
                page_title=page.title,
                output_file=str(output_path),
                status=status,
                warnings=result.warnings,
                conversion_time_ms=conversion_time_ms,
            )

        except Exception as e:
            logger.error(f"Failed to convert '{page.title}': {e}")
            conversion_time_ms = int((time.time() - start_time) * 1000)

            return PageConversionReport(
                page_id=page.id,
                page_title=page.title,
                output_file=str(output_path),
                status="failed",
                errors=[str(e)],
                conversion_time_ms=conversion_time_ms,
            )

    def _get_output_path(self, page: PageNode, export: ConfluenceExport) -> Path:
        """Calculate output path for a page (always flat structure)."""
        exports_dir = self.settings.exports_dir

        # Always use flat structure
        filename = page.title
        if self.settings.output.filename_style == "slugify":
            filename = self._slugify(filename)
        return exports_dir / export.space.key.lower() / f"{filename}.md"

    def _slugify(self, text: str) -> str:
        """Convert text to kebab-case slug."""
        import re

        text = text.lower()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        text = re.sub(r"-+", "-", text)
        return text.strip("-")

    def _update_state(
        self, export: ConfluenceExport, reports: list[PageConversionReport]
    ) -> None:
        """Update build state after conversion."""
        export_name = export.path.name

        # Get or create export state
        if export_name not in self.state.exports:
            self.state.exports[export_name] = ExportState(
                source_path=str(export.path),
                source_mtime=datetime.now().isoformat(),
                source_hash="",
            )

        export_state = self.state.exports[export_name]

        # Update page states
        for report in reports:
            if report.status != "failed":
                page = export.pages_by_id.get(report.page_id)
                if page:
                    export_state.pages[page.id] = PageState(
                        title=page.title,
                        output_path=report.output_file,
                        content_hash=page.content_hash,
                        converted_at=datetime.now().isoformat(),
                    )

        # Update settings hash
        self.state.settings_hash = self._hash_settings()

    def _load_state(self) -> BuildState:
        """Load build state from disk."""
        state_file = Path(self.STATE_FILE)
        if not state_file.exists():
            return BuildState()

        try:
            data = json.loads(state_file.read_text())
            return self._parse_state(data)
        except Exception as e:
            logger.warning(f"Failed to load build state: {e}")
            return BuildState()

    def _parse_state(self, data: dict) -> BuildState:
        """Parse build state from JSON data."""
        state = BuildState(
            version=data.get("version", "1.0"),
            settings_hash=data.get("settings_hash", ""),
        )

        for export_name, export_data in data.get("exports", {}).items():
            pages = {}
            for page_id, page_data in export_data.get("pages", {}).items():
                pages[page_id] = PageState(
                    title=page_data.get("title", ""),
                    output_path=page_data.get("output_path", ""),
                    content_hash=page_data.get("content_hash", ""),
                    converted_at=page_data.get("converted_at", ""),
                )

            state.exports[export_name] = ExportState(
                source_path=export_data.get("source_path", ""),
                source_mtime=export_data.get("source_mtime", ""),
                source_hash=export_data.get("source_hash", ""),
                pages=pages,
            )

        return state

    def _save_state(self) -> None:
        """Save build state to disk."""
        data = {
            "version": self.state.version,
            "settings_hash": self.state.settings_hash,
            "exports": {},
        }

        for export_name, export_state in self.state.exports.items():
            pages = {}
            for page_id, page_state in export_state.pages.items():
                pages[page_id] = {
                    "title": page_state.title,
                    "output_path": page_state.output_path,
                    "content_hash": page_state.content_hash,
                    "converted_at": page_state.converted_at,
                }

            data["exports"][export_name] = {
                "source_path": export_state.source_path,
                "source_mtime": export_state.source_mtime,
                "source_hash": export_state.source_hash,
                "pages": pages,
            }

        Path(self.STATE_FILE).write_text(json.dumps(data, indent=2))

    def _hash_settings(self) -> str:
        """Generate hash of relevant settings for cache invalidation."""
        # Hash settings that affect output
        relevant = {
            "exclude_pages": self.settings.exclude_pages,
            "content": {
                "include_frontmatter": self.settings.content.include_frontmatter,
            },
            "output": {
                "filename_style": self.settings.output.filename_style,
            },
        }
        content = json.dumps(relevant, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
