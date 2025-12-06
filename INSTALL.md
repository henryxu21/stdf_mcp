# Quick Installation Guide

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Claude Desktop (for MCP integration)

## Installation Steps

### 1. Clone or Download the Repository

```bash
git clone https://github.com/your-org/stdf-mcp.git
cd stdf-mcp
```

Or download and extract the ZIP file.

### 2. Install the Package

```bash
pip install -e .
```

This installs the package in editable mode with all required dependencies:
- `mcp>=1.0.0` - Model Context Protocol SDK
- `numpy>=1.24.0` - Statistical calculations
- `matplotlib>=3.6.0` - Visualization
- `openpyxl>=3.1.0` - Excel file generation

### 3. Verify Installation

```bash
# Test the server starts
python -m stdf_mcp.simple_server --help

# Run tests (optional)
pytest
```

### 4. Configure Claude Desktop

#### For macOS:
Edit `~/Library/Application Support/Claude/claude_desktop_config.json`

#### For Windows:
Edit `%APPDATA%/Claude/claude_desktop_config.json`

Add this configuration:

```json
{
  "mcpServers": {
    "stdf": {
      "command": "python",
      "args": ["-m", "stdf_mcp.simple_server"],
      "cwd": "/FULL/PATH/TO/stdf-mcp"
    }
  }
}
```

**Important**: Replace `/FULL/PATH/TO/stdf-mcp` with the actual absolute path to your installation directory.

#### Example paths:
- **macOS**: `/Users/yourname/projects/stdf-mcp`
- **Windows**: `C:\\Users\\YourName\\Projects\\stdf-mcp`

### 5. Restart Claude Desktop

Close and reopen Claude Desktop. The STDF MCP server should now be available.

### 6. Test the Connection

In Claude Desktop, try:
```
"List available STDF tools"
```

You should see 17 tools listed.

## Development Installation

For development with additional tools:

```bash
pip install -e ".[dev]"
```

This includes:
- pytest - Testing framework
- black - Code formatter
- flake8 - Linter
- mypy - Type checker
- pytest-cov - Coverage reporting

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'stdf_mcp'"

**Solution**: Make sure you're in the project directory and run:
```bash
pip install -e .
```

### Issue: Server not appearing in Claude Desktop

**Solutions**:
1. Verify the configuration file path is correct
2. Ensure `cwd` uses the absolute path to the installation
3. Restart Claude Desktop completely
4. Check Claude Desktop logs for error messages

### Issue: Import errors for dependencies

**Solution**: Reinstall dependencies:
```bash
pip install --upgrade -e .
```

### Issue: Tests failing

**Solution**: Install development dependencies:
```bash
pip install -e ".[dev]"
pytest
```

## Quick Test

After installation, test with a sample STDF file:

```bash
# In Claude Desktop
"Extract file overview from TestCases/example.stdf"
```

## What's Next?

- See [README.md](README.md) for full documentation
- Check `TestCases/` directory for sample STDF files
- Try the usage examples in the README
- Read tool documentation for specific features

## Support

- **Issues**: Report at GitHub Issues
- **Questions**: Check README.md troubleshooting section
- **Contributing**: See CONTRIBUTING guidelines in README.md

---

Installation complete! You're ready to use the STDF MCP Server with Claude.
