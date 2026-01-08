"""Tests for the build orchestration module."""

import json
import tempfile
from pathlib import Path

import pytest

from confluence_to_markdown.builder import (
    BuildResult,
    BuildState,
    ConversionBuilder,
    ExportState,
    PageState,
)
from confluence_to_markdown.config import Settings
from confluence_to_markdown.export_parser import PageNode


@pytest.fixture
def settings() -> Settings:
    """Default settings for testing."""
    settings = Settings.default()
    settings.imports_dir = Path(tempfile.mkdtemp())
    settings.exports_dir = Path(tempfile.mkdtemp())
    return settings


class TestBuildState:
    """Tests for build state management."""

    def test_default_state(self) -> None:
        """Default state is empty."""
        state = BuildState()

        assert state.version == "1.0"
        assert state.settings_hash == ""
        assert state.exports == {}

    def test_page_state(self) -> None:
        """Page state stores conversion info."""
        page_state = PageState(
            title="Test Page",
            output_path="/output/test.md",
            content_hash="abc123",
            converted_at="2024-01-15T10:00:00",
        )

        assert page_state.title == "Test Page"
        assert page_state.content_hash == "abc123"


class TestConversionBuilder:
    """Tests for ConversionBuilder class."""

    def test_init_creates_state(self, settings: Settings) -> None:
        """Builder initializes with empty state."""
        builder = ConversionBuilder(settings)

        assert builder.state is not None
        assert isinstance(builder.state, BuildState)

    def test_hash_settings_consistent(self, settings: Settings) -> None:
        """Settings hash is consistent for same settings."""
        builder1 = ConversionBuilder(settings)
        builder2 = ConversionBuilder(settings)

        assert builder1._hash_settings() == builder2._hash_settings()

    def test_hash_settings_changes(self, settings: Settings) -> None:
        """Settings hash changes when settings change."""
        builder1 = ConversionBuilder(settings)
        hash1 = builder1._hash_settings()

        settings.exclude_pages = ["Test/*"]
        builder2 = ConversionBuilder(settings)
        hash2 = builder2._hash_settings()

        assert hash1 != hash2

    def test_slugify(self, settings: Settings) -> None:
        """Slugify converts to kebab-case."""
        builder = ConversionBuilder(settings)

        assert builder._slugify("Hello World") == "hello-world"
        assert builder._slugify("My Page Title") == "my-page-title"
        assert builder._slugify("Test!@#Page") == "testpage"

    def test_clean_empty_dir(self, settings: Settings) -> None:
        """Clean handles empty exports directory."""
        builder = ConversionBuilder(settings)
        removed = builder.clean()

        # Should handle gracefully
        assert removed >= 0

    def test_get_status(self, settings: Settings) -> None:
        """Get status returns expected info."""
        builder = ConversionBuilder(settings)
        status = builder.get_status()

        assert "state_file_exists" in status
        assert "exports_in_state" in status
        assert "settings_hash" in status


class TestStatePeristence:
    """Tests for state save/load."""

    def test_save_and_load_state(self, settings: Settings) -> None:
        """State can be saved and loaded."""
        builder = ConversionBuilder(settings)

        # Modify state
        builder.state.settings_hash = "test_hash"
        builder.state.exports["test.zip"] = ExportState(
            source_path="/path/to/test.zip",
            source_mtime="2024-01-15T10:00:00",
            source_hash="abc123",
            pages={
                "1": PageState(
                    title="Page 1",
                    output_path="/output/page-1.md",
                    content_hash="def456",
                    converted_at="2024-01-15T11:00:00",
                )
            },
        )

        # Save state
        builder._save_state()

        # Create new builder and load state
        builder2 = ConversionBuilder(settings)

        assert builder2.state.settings_hash == "test_hash"
        assert "test.zip" in builder2.state.exports
        assert builder2.state.exports["test.zip"].pages["1"].title == "Page 1"

        # Clean up
        Path(builder.STATE_FILE).unlink(missing_ok=True)


class TestBuildResult:
    """Tests for BuildResult class."""

    def test_build_result_creation(self) -> None:
        """BuildResult holds conversion statistics."""
        result = BuildResult(
            pages_converted=10,
            pages_skipped=5,
            pages_failed=1,
            total_time_ms=1500,
        )

        assert result.pages_converted == 10
        assert result.pages_skipped == 5
        assert result.pages_failed == 1
        assert result.total_time_ms == 1500
        assert result.page_reports == []
