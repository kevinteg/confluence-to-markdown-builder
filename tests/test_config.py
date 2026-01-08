"""Tests for the configuration module."""

import tempfile
from pathlib import Path

import pytest

from confluence_to_markdown.config import (
    ContentSettings,
    LinkSettings,
    LoggingSettings,
    OutputSettings,
    Settings,
)


class TestSettings:
    """Tests for Settings class."""

    def test_default_settings(self) -> None:
        """Default settings have expected values."""
        settings = Settings.default()

        assert settings.imports_dir == Path("./imports")
        assert settings.exports_dir == Path("./exports")
        assert settings.exclude_pages == []
        assert settings.exclude_sections == []

    def test_load_nonexistent_file(self) -> None:
        """Loading nonexistent file raises error."""
        with pytest.raises(FileNotFoundError):
            Settings.load("/nonexistent/path/settings.yaml")

    def test_load_valid_yaml(self) -> None:
        """Valid YAML file loads correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write(
                """
imports_dir: ./custom/imports
exports_dir: ./custom/exports
exclude_pages:
  - "Archive/*"
exclude_sections:
  - "**/Change Log"
            """
            )
            f.flush()

            settings = Settings.load(f.name)

            assert settings.imports_dir == Path("./custom/imports")
            assert settings.exports_dir == Path("./custom/exports")
            assert "Archive/*" in settings.exclude_pages
            assert "**/Change Log" in settings.exclude_sections

            Path(f.name).unlink()

    def test_load_empty_yaml(self) -> None:
        """Empty YAML file uses defaults."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()

            settings = Settings.load(f.name)

            # Should use defaults
            assert settings.imports_dir == Path("./imports")

            Path(f.name).unlink()


class TestLoggingSettings:
    """Tests for LoggingSettings class."""

    def test_defaults(self) -> None:
        """Default logging settings."""
        settings = LoggingSettings()

        assert settings.level == "INFO"
        assert settings.file == "./logs/converter.log"


class TestContentSettings:
    """Tests for ContentSettings class."""

    def test_defaults(self) -> None:
        """Default content settings."""
        settings = ContentSettings()

        assert settings.unknown_macro_handling == "comment"
        assert settings.include_frontmatter is True
        assert "title" in settings.frontmatter_fields

    def test_link_settings_default(self) -> None:
        """Default link settings."""
        settings = ContentSettings()

        assert settings.links.internal_link_style == "relative"
        assert settings.links.missing_page_links == "comment"


class TestOutputSettings:
    """Tests for OutputSettings class."""

    def test_defaults(self) -> None:
        """Default output settings."""
        settings = OutputSettings()

        assert settings.filename_style == "slugify"
        assert settings.preserve_hierarchy is True
        assert settings.max_heading_level == 6
