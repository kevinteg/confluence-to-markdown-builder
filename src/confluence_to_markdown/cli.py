"""Click CLI entry point for the converter."""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

import click

from confluence_to_markdown.converter import MarkdownConverter
from confluence_to_markdown.config import Settings
from confluence_to_markdown.export_parser import ExportParser
from confluence_to_markdown.logging_config import setup_logging


# Fixed output directories
EXPORT_DIR = Path("confluence_export")
MARKDOWN_DIR = Path("confluence_markdown")


@click.command()
@click.argument("zip_file", type=click.Path(exists=True, path_type=Path))
@click.option("--force", "-f", is_flag=True, help="Force regeneration (clean before converting)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
def cli(zip_file: Path, force: bool, verbose: bool) -> None:
    """Convert a Confluence HTML export ZIP to Markdown.

    ZIP_FILE: Path to the Confluence HTML export ZIP file
    """
    settings = Settings.default()
    setup_logging(settings, verbose)

    # Step 1: Clean and extract ZIP
    click.echo(f"Extracting {zip_file.name}...")
    extract_count = extract_zip(zip_file, force)
    click.echo(f"  Extracted {extract_count} HTML files to {EXPORT_DIR}/")

    # Step 2: Convert HTML files to Markdown
    click.echo(f"Converting to Markdown...")
    convert_count, warnings = convert_html_files(settings)
    click.echo(f"  Converted {convert_count} files to {MARKDOWN_DIR}/")

    # Print warnings if any
    if warnings:
        click.echo()
        click.echo(f"Warnings ({len(warnings)}):")
        for warning in warnings[:10]:
            click.echo(f"  - {warning}")
        if len(warnings) > 10:
            click.echo(f"  ... and {len(warnings) - 10} more")

    click.echo()
    click.echo("Done!")


def extract_zip(zip_file: Path, force: bool) -> int:
    """Extract HTML files from ZIP to confluence_export folder.

    Removes the top-level containing folder and keeps only HTML files.

    Returns:
        Number of HTML files extracted.
    """
    # Clean export directory if force or if it exists
    if EXPORT_DIR.exists():
        if force:
            shutil.rmtree(EXPORT_DIR)
        else:
            # Remove existing files but keep directory
            for f in EXPORT_DIR.glob("*"):
                if f.is_file():
                    f.unlink()

    EXPORT_DIR.mkdir(exist_ok=True)

    html_count = 0
    with zipfile.ZipFile(zip_file, "r") as zf:
        for member in zf.namelist():
            # Skip directories
            if member.endswith("/"):
                continue

            # Only extract HTML files
            if not member.lower().endswith(".html"):
                continue

            # Get the filename without the top-level directory
            parts = Path(member).parts
            if len(parts) > 1:
                # Remove top-level folder, keep rest flattened
                filename = parts[-1]  # Just the filename
            else:
                filename = parts[0]

            # Extract to export directory
            target_path = EXPORT_DIR / filename

            # Handle duplicate filenames by adding a suffix
            if target_path.exists():
                base = target_path.stem
                suffix = target_path.suffix
                counter = 1
                while target_path.exists():
                    target_path = EXPORT_DIR / f"{base}_{counter}{suffix}"
                    counter += 1

            # Extract the file
            with zf.open(member) as source:
                target_path.write_bytes(source.read())
            html_count += 1

    return html_count


def convert_html_files(settings: Settings) -> tuple[int, list[str]]:
    """Convert all HTML files in confluence_export to Markdown.

    Returns:
        Tuple of (count of files converted, list of warnings).
    """
    # Clean markdown directory
    if MARKDOWN_DIR.exists():
        shutil.rmtree(MARKDOWN_DIR)
    MARKDOWN_DIR.mkdir()

    parser = ExportParser()
    converter = MarkdownConverter(settings)

    # Parse the export directory
    export = parser.parse(EXPORT_DIR)

    all_warnings: list[str] = []
    convert_count = 0

    for page in export.pages:
        result = converter.convert(page, export)

        # Generate output filename
        filename = slugify(page.title) + ".md"
        output_path = MARKDOWN_DIR / filename

        # Handle duplicate filenames
        if output_path.exists():
            base = output_path.stem
            counter = 1
            while output_path.exists():
                output_path = MARKDOWN_DIR / f"{base}_{counter}.md"
                counter += 1

        output_path.write_text(result.markdown)
        convert_count += 1
        all_warnings.extend(result.warnings)

    return convert_count, all_warnings


def slugify(text: str) -> str:
    """Convert text to kebab-case slug."""
    import re
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
