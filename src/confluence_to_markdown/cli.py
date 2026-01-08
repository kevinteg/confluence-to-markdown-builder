"""Click CLI entry point for the converter."""

from __future__ import annotations

import hashlib
import shutil
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

    # Step 1: Extract ZIP
    click.echo(f"Extracting {zip_file.name}...")
    extracted, skipped = extract_zip(zip_file, force, verbose)
    click.echo(f"  Extracted: {extracted}, Already existed: {skipped}")

    # Step 2: Convert HTML files to Markdown
    click.echo(f"Converting to Markdown...")
    converted, skipped_md, warnings = convert_html_files(settings, force, verbose)
    click.echo(f"  Converted: {converted}, Already existed: {skipped_md}")

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


def extract_zip(zip_file: Path, force: bool, verbose: bool) -> tuple[int, int]:
    """Extract HTML files from ZIP to confluence_export folder.

    Removes the top-level containing folder and keeps only HTML files.

    Returns:
        Tuple of (extracted count, already existed count).
    """
    # Clean export directory if force
    if force and EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)

    EXPORT_DIR.mkdir(exist_ok=True)

    extracted = 0
    skipped = 0

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

            target_path = EXPORT_DIR / filename

            # Check if file already exists with same content
            if target_path.exists():
                # Read content from ZIP to compare
                with zf.open(member) as source:
                    new_content = source.read()

                existing_content = target_path.read_bytes()
                if existing_content == new_content:
                    skipped += 1
                    continue

                # Content differs - need to extract (handle duplicate name)
                base = target_path.stem
                suffix = target_path.suffix
                counter = 1
                while target_path.exists():
                    target_path = EXPORT_DIR / f"{base}_{counter}{suffix}"
                    counter += 1

            # Extract the file
            if verbose:
                click.echo(f"  Extracting: {filename}")

            with zf.open(member) as source:
                target_path.write_bytes(source.read())
            extracted += 1

    return extracted, skipped


def convert_html_files(settings: Settings, force: bool, verbose: bool) -> tuple[int, int, list[str]]:
    """Convert all HTML files in confluence_export to Markdown.

    Returns:
        Tuple of (converted count, already existed count, list of warnings).
    """
    # Clean markdown directory if force
    if force and MARKDOWN_DIR.exists():
        shutil.rmtree(MARKDOWN_DIR)

    MARKDOWN_DIR.mkdir(exist_ok=True)

    parser = ExportParser()
    converter = MarkdownConverter(settings)

    # Parse the export directory
    export = parser.parse(EXPORT_DIR)

    all_warnings: list[str] = []
    converted = 0
    skipped = 0

    for page in export.pages:
        result = converter.convert(page, export)

        # Generate output filename
        filename = slugify(page.title) + ".md"
        output_path = MARKDOWN_DIR / filename

        # Handle duplicate filenames
        base_path = output_path
        counter = 1
        while output_path.exists():
            # Check if content is the same
            existing_content = output_path.read_text()
            if existing_content == result.markdown:
                skipped += 1
                break
            # Different content, try next filename
            output_path = MARKDOWN_DIR / f"{base_path.stem}_{counter}.md"
            counter += 1
        else:
            # File doesn't exist or we found a unique name
            if verbose:
                click.echo(f"  Converting: {page.title} -> {output_path.name}")

            output_path.write_text(result.markdown)
            converted += 1
            all_warnings.extend(result.warnings)

    return converted, skipped, all_warnings


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
