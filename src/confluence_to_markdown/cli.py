"""Click CLI entry point for the converter."""

import sys
from pathlib import Path

import click

from confluence_to_markdown.builder import ConversionBuilder
from confluence_to_markdown.config import Settings
from confluence_to_markdown.export_parser import ExportParser
from confluence_to_markdown.logging_config import setup_logging


@click.group()
@click.option(
    "--config",
    "-c",
    default="settings.yaml",
    help="Path to settings file",
    type=click.Path(),
)
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging")
@click.pass_context
def cli(ctx: click.Context, config: str, verbose: bool) -> None:
    """Confluence HTML Export to Markdown converter."""
    ctx.ensure_object(dict)
    ctx.obj["config_path"] = config
    ctx.obj["verbose"] = verbose

    # Load settings
    config_path = Path(config)
    if config_path.exists():
        settings = Settings.load(config_path)
    else:
        settings = Settings.default()

    ctx.obj["settings"] = settings

    # Setup logging
    setup_logging(settings, verbose)


@cli.command()
@click.argument("export_path", type=click.Path(exists=True))
@click.option("--force", "-f", is_flag=True, help="Force regeneration of all files")
@click.pass_context
def convert(ctx: click.Context, export_path: str, force: bool) -> None:
    """Convert a Confluence HTML export to Markdown.

    EXPORT_PATH: Path to HTML export ZIP or extracted directory
    """
    settings: Settings = ctx.obj["settings"]
    builder = ConversionBuilder(settings)

    result = builder.convert_export(export_path, force=force)

    # Print summary
    click.echo()
    click.echo(f"Conversion complete:")
    click.echo(f"  Pages converted: {result.pages_converted}")
    click.echo(f"  Pages skipped:   {result.pages_skipped}")
    click.echo(f"  Pages failed:    {result.pages_failed}")
    click.echo(f"  Total time:      {result.total_time_ms}ms")

    # Print warnings if any
    warnings = []
    for report in result.page_reports:
        warnings.extend(report.warnings)

    if warnings:
        click.echo()
        click.echo(f"Warnings ({len(warnings)}):")
        for warning in warnings[:10]:
            click.echo(f"  - {warning}")
        if len(warnings) > 10:
            click.echo(f"  ... and {len(warnings) - 10} more")

    if result.pages_failed > 0:
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show status of imports and what would be converted."""
    settings: Settings = ctx.obj["settings"]

    # Check imports directory
    imports_dir = settings.imports_dir
    if not imports_dir.exists():
        click.echo(f"Imports directory not found: {imports_dir}")
        return

    exports = list(imports_dir.glob("*.zip")) + [
        d for d in imports_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"
    ]

    if not exports:
        click.echo(f"No exports found in {imports_dir}")
        return

    click.echo(f"Found {len(exports)} export(s) in {imports_dir}:")
    for export_path in exports:
        click.echo(f"  - {export_path.name}")

        try:
            parser = ExportParser()
            export = parser.parse(export_path)
            click.echo(f"    Space: {export.space.name} ({export.space.key})")
            click.echo(f"    Pages: {len(export.pages_by_id)}")
        except Exception as e:
            click.echo(f"    Error: {e}")

    # Check build state
    builder = ConversionBuilder(settings)
    status_info = builder.get_status()
    click.echo()
    click.echo("Build state:")
    click.echo(f"  State file exists: {status_info['state_file_exists']}")
    if status_info["exports_in_state"]:
        click.echo(f"  Cached exports: {', '.join(status_info['exports_in_state'])}")


@cli.command()
@click.pass_context
def clean(ctx: click.Context) -> None:
    """Remove all generated Markdown files."""
    settings: Settings = ctx.obj["settings"]
    builder = ConversionBuilder(settings)

    removed = builder.clean()
    click.echo(f"Cleaned {removed} files")


@cli.command()
@click.argument("page_title")
@click.pass_context
def preview(ctx: click.Context, page_title: str) -> None:
    """Preview conversion of a single page without writing to disk.

    PAGE_TITLE: Title of the page to preview
    """
    settings: Settings = ctx.obj["settings"]

    # Find the export and page
    imports_dir = settings.imports_dir
    exports = list(imports_dir.glob("*.zip")) + [
        d for d in imports_dir.iterdir() if d.is_dir() and d.name != ".gitkeep"
    ]

    if not exports:
        click.echo(f"No exports found in {imports_dir}")
        sys.exit(1)

    parser = ExportParser()
    from confluence_to_markdown.converter import MarkdownConverter

    converter = MarkdownConverter(settings)

    for export_path in exports:
        try:
            export = parser.parse(export_path)
            # Search by title
            page = next((p for p in export.pages if p.title == page_title), None)

            if page:
                click.echo(f"Found page in: {export_path.name}")
                click.echo(f"Page: {page.title}")
                click.echo("-" * 40)

                result = converter.convert(page, export)
                click.echo(result.markdown)

                if result.warnings:
                    click.echo("-" * 40)
                    click.echo("Warnings:")
                    for warning in result.warnings:
                        click.echo(f"  - {warning}")

                return

        except Exception as e:
            click.echo(f"Error parsing {export_path.name}: {e}", err=True)

    click.echo(f"Page not found: {page_title}")
    sys.exit(1)


def main() -> None:
    """Main entry point."""
    cli()


if __name__ == "__main__":
    main()
