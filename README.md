# Confluence to Markdown Converter

Convert Confluence XML space exports to Markdown files with preserved hierarchy and configurable filtering.

## Features

- **XML Export Processing**: Parses Confluence space XML exports (no API access needed)
- **Hierarchy Preservation**: Maintains page structure in output directory
- **Section Filtering**: Exclude pages or sections by heading hierarchy patterns
- **Incremental Builds**: Make-like logic to only regenerate changed content
- **Robust Logging**: Detailed logs of conversions, warnings, and errors
- **Library + CLI**: Use as a command-line tool or import as a Python library

## Installation

```bash
pip install confluence-to-markdown
```

Or for development:

```bash
git clone https://github.com/yourusername/confluence-to-markdown
cd confluence-to-markdown
pip install -e ".[dev]"
```

## Quick Start

1. **Export your Confluence space**: In Confluence, go to Space Settings → Content Tools → Export, select XML export

2. **Place the export in the imports folder**:
   ```bash
   cp ~/Downloads/myspace-export.zip ./imports/
   ```

3. **Run the converter**:
   ```bash
   confluence-to-markdown convert ./imports/myspace-export.zip
   ```

4. **Find your Markdown files** in the `exports/` directory

## Usage

### Basic Conversion

```bash
# Convert an export
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
confluence-to-markdown preview "Project/Architecture Overview"

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

# Exclude sections by heading path
exclude_sections:
  - "**/Change Log"
  - "**/Revision History"

# Content options
content:
  unknown_macro_handling: comment  # comment, strip, preserve_text
  include_frontmatter: true

# Output formatting  
output:
  filename_style: slugify  # Creates kebab-case filenames
  preserve_hierarchy: true
```

## Library Usage

```python
from confluence_to_markdown import ExportParser, MarkdownConverter, Settings

# Parse an export
parser = ExportParser()
export = parser.parse("./imports/myspace-export.zip")

# Walk the page tree
for page in export.walk_pages():
    print(f"{'  ' * page.depth}{page.title}")

# Convert a single page
settings = Settings.load("settings.yaml")
converter = MarkdownConverter(settings)
result = converter.convert(page, export)

print(result.markdown)
```

## How It Works

1. **Parse**: Extracts page tree and content from `entities.xml` in the Confluence export
2. **Filter**: Applies exclude patterns from settings to skip unwanted pages/sections
3. **Convert**: Transforms Confluence storage format (XHTML with macros) to Markdown
4. **Cache**: Tracks content hashes to enable incremental builds

## Supported Confluence Elements

- Headings, paragraphs, text formatting (bold, italic, etc.)
- Ordered and unordered lists, task lists
- Tables
- Code blocks (with language hints)
- Info, warning, note, and tip panels
- Expand/collapse sections
- Internal page links (converted to relative paths)
- Images (with attachment path rewriting)
- Blockquotes, horizontal rules

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
