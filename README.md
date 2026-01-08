# Confluence to Markdown Converter

Convert Confluence HTML space exports to Markdown files.

## Installation

```bash
git clone https://github.com/kevinteg/confluence-to-markdown-builder
cd confluence-to-markdown-builder
pip install -e ".[dev]"
```

## Usage

```bash
# Convert a Confluence HTML export ZIP file
python -m confluence_to_markdown.cli export.zip

# With verbose output
python -m confluence_to_markdown.cli export.zip --verbose

# Force clean extraction and conversion
python -m confluence_to_markdown.cli export.zip --force
```

The tool will:
1. Extract HTML files from the ZIP to `confluence_export/` (flattened, removing top-level folder)
2. Convert each HTML file to Markdown in `confluence_markdown/`

## Output

- `confluence_export/` - Extracted HTML files from the ZIP
- `confluence_markdown/` - Converted Markdown files

## Supported HTML Elements

- Headings, paragraphs, text formatting (bold, italic, underline, strikethrough)
- Ordered and unordered lists
- Tables (converted to GFM format)
- Code blocks (with language detection)
- Links and images
- Blockquotes, horizontal rules

## Development

```bash
# Run tests
pytest

# Run tests with coverage
pytest --cov=confluence_to_markdown
```

## License

MIT License
