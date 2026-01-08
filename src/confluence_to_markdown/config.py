"""Settings and configuration loading for the converter."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml


@dataclass
class LoggingSettings:
    """Logging configuration."""

    level: str = "INFO"
    file: str | None = "./logs/converter.log"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class LinkSettings:
    """Link handling configuration."""

    internal_link_style: Literal["relative", "title_only"] = "relative"
    missing_page_links: Literal["preserve", "comment", "strip"] = "comment"


@dataclass
class ContentSettings:
    """Content handling configuration."""

    unknown_macro_handling: Literal["comment", "strip", "preserve_text"] = "comment"
    include_frontmatter: bool = True
    frontmatter_fields: list[str] = field(
        default_factory=lambda: ["title", "created_date", "modified_date", "labels"]
    )
    links: LinkSettings = field(default_factory=LinkSettings)


@dataclass
class OutputSettings:
    """Output formatting configuration."""

    filename_style: Literal["slugify", "preserve"] = "slugify"
    preserve_hierarchy: bool = True
    max_heading_level: int = 6


@dataclass
class Settings:
    """Main settings container for the converter."""

    imports_dir: Path = field(default_factory=lambda: Path("./imports"))
    exports_dir: Path = field(default_factory=lambda: Path("./exports"))
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    exclude_pages: list[str] = field(default_factory=list)
    exclude_sections: list[str] = field(default_factory=list)
    content: ContentSettings = field(default_factory=ContentSettings)
    output: OutputSettings = field(default_factory=OutputSettings)

    @classmethod
    def load(cls, path: str | Path) -> "Settings":
        """Load settings from a YAML file.

        Args:
            path: Path to the settings YAML file.

        Returns:
            Settings instance populated from the file.

        Raises:
            FileNotFoundError: If the settings file doesn't exist.
            yaml.YAMLError: If the file contains invalid YAML.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Settings file not found: {path}")

        with open(path) as f:
            data = yaml.safe_load(f) or {}

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "Settings":
        """Create Settings from a dictionary."""
        logging_data = data.get("logging", {})
        logging_settings = LoggingSettings(
            level=logging_data.get("level", "INFO"),
            file=logging_data.get("file"),
            format=logging_data.get(
                "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            ),
        )

        content_data = data.get("content", {})
        links_data = content_data.get("links", {})
        link_settings = LinkSettings(
            internal_link_style=links_data.get("internal_link_style", "relative"),
            missing_page_links=links_data.get("missing_page_links", "comment"),
        )
        content_settings = ContentSettings(
            unknown_macro_handling=content_data.get("unknown_macro_handling", "comment"),
            include_frontmatter=content_data.get("include_frontmatter", True),
            frontmatter_fields=content_data.get(
                "frontmatter_fields", ["title", "created_date", "modified_date", "labels"]
            ),
            links=link_settings,
        )

        output_data = data.get("output", {})
        output_settings = OutputSettings(
            filename_style=output_data.get("filename_style", "slugify"),
            preserve_hierarchy=output_data.get("preserve_hierarchy", True),
            max_heading_level=output_data.get("max_heading_level", 6),
        )

        return cls(
            imports_dir=Path(data.get("imports_dir", "./imports")),
            exports_dir=Path(data.get("exports_dir", "./exports")),
            logging=logging_settings,
            exclude_pages=data.get("exclude_pages", []),
            exclude_sections=data.get("exclude_sections", []),
            content=content_settings,
            output=output_settings,
        )

    @classmethod
    def default(cls) -> "Settings":
        """Create Settings with default values."""
        return cls()
