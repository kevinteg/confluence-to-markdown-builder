# Confluence to Markdown Converter

Convert Confluence HTML space exports to Markdown files with a flat output structure.

## Features

- **HTML Export Processing**: Parses Confluence space HTML exports (no API access needed)
- **Flat Output Structure**: All pages output to a single directory for easy organization
- **Incremental Builds**: Only regenerates changed content
- **Robust Logging**: Detailed logs of conversions, warnings, and errors
- **Library + CLI**: Use as a command-line tool or import as a Python library

## Installation

```bash
git clone https://github.com/kevinteg/confluence-to-markdown-builder
cd confluence-to-markdown-builder
pip install -e ".[dev]"
```

This installs the package in development mode and adds the `confluence-to-markdown` command to your PATH.

## Quick Start

1. **Export your Confluence space**: In Confluence, go to Space Settings → Content Tools → Export, select HTML export

2. **Run the converter**:
   ```bash
   confluence-to-markdown convert ./path/to/export.zip
   ```

3. **Find your Markdown files** in the `exports/` directory

## Usage

### Basic Conversion

```bash
# Convert an export (ZIP or extracted directory)
confluence-to-markdown convert ./imports/myspace-export.zip

# Force full reconversion (ignore cache)
confluence-to-markdown convert ./imports/myspace-export.zip --force

# Use custom settings file
confluence-to-markdown -c my-settings.yaml convert ./imports/export.zip

# Verbose output
confluence-to-markdown -v convert ./imports/export.zip
```

### Other Commands

```bash
# Show status of imports and what would be converted
confluence-to-markdown status

# Preview a single page without writing files
confluence-to-markdown preview "Page Title"

# Remove all generated files
confluence-to-markdown clean
```

## Configuration

Create a `settings.yaml` file to customize behavior:

```yaml
# Input/output directories
imports_dir: ./imports
exports_dir: ./exports

# Logging
logging:
  level: INFO
  file: ./logs/converter.log

# Exclude pages by title pattern
exclude_pages:
  - "Archive/*"
  - "*/Deprecated"

# Content options
content:
  include_frontmatter: true
  frontmatter_fields:
    - title

# Output formatting
output:
  filename_style: slugify  # Creates kebab-case filenames
  max_heading_level: 6
```

## Library Usage

```python
from confluence_to_markdown import ExportParser, MarkdownConverter, Settings

# Parse an export
parser = ExportParser()
export = parser.parse("./imports/myspace-export.zip")

# List all pages
for page in export.pages:
    print(f"{page.title} ({page.filename})")

# Convert a single page
settings = Settings.default()
converter = MarkdownConverter(settings)
result = converter.convert(page, export)

print(result.markdown)
```

## How It Works

1. **Parse**: Extracts pages from HTML files in the Confluence export
2. **Filter**: Applies exclude patterns from settings to skip unwanted pages
3. **Convert**: Transforms HTML to Markdown
4. **Cache**: Tracks content hashes to enable incremental builds

## Supported HTML Elements

- Headings, paragraphs, text formatting (bold, italic, underline, strikethrough)
- Ordered and unordered lists
- Tables (converted to GFM format)
- Code blocks (with language detection)
- Links and images
- Blockquotes, horizontal rules
- Subscript and superscript

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=confluence_to_markdown

# Format code
black src/ tests/

# Lint
ruff check src/ tests/

# Type check
mypy src/
```

## License

MIT License - see LICENSE file for details.
