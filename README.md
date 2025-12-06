#STDF MCP Server

A Model Context Protocol (MCP) server that enables LLMs to efficiently access, analyze, and extract information from STDF-V4 (Standard Test Data Format) files used in semiconductor testing.

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

### 17 Specialized Tools

**Metadata Extraction (6 tools):**
- `extract_file_overview` - Quick file assessment and key identifiers
- `extract_test_configuration` - Hardware setup and test environment
- `extract_yield_summary` - Test results analysis and yield calculation
- `extract_facility_details` - Manufacturing context and facility information
- `extract_program_metadata` - Test program and software version details
- `extract_test_parameters` - Comprehensive parameter listing with limits

**Record Extraction (7 tools):**
- `extract_pir_prr_records` - Part Information/Results Records
- `extract_ptr_records` - Parametric Test Records with filtering
- `extract_ftr_records` - Functional Test Records
- `extract_hbr_records` - Hardware Bin Records
- `extract_sbr_records` - Software Bin Records
- `extract_sdr_records` - Site Description Records
- `extract_mrr_record` - Master Results Record

**Test Analysis (3 tools):**
- `extract_test_parameter_summary` - Statistical summaries with test suite filtering
- `extract_filtered_data` - Excel extraction with multi-site support
- `extract_test_time` - Test execution time analysis with site filtering

**Yield Analysis (1 tool):**
- `extract_per_unit_yield` - Per-unit bin data extraction to CSV (PART_ID, HW Bin, SW Bin)

### Key Capabilities

- **STDF-V4 Format Support**: Comprehensive support for STDF-V4 specification
- **High Performance**: Handles files up to 2GB with <512MB memory through streaming parser
- **Multi-Site Support**: Parallel test site data extraction and analysis
- **Test Suite Filtering**: Filter by test name, number, or suite with regex support
- **CSV/Excel Export**: Generate analysis-ready datasets
- **Automatic Validation**: Built-in file integrity validation
- **TDD Development**: Comprehensive test coverage with real STDF files

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/your-org/stdf-mcp.git
cd stdf-mcp

# Install the package
pip install -e .
```

### Running the MCP Server

```bash
# Start the MCP server
python -m stdf_mcp.simple_server
```

The server will start and listen for MCP protocol connections on stdin/stdout.

### Configuration for Claude Desktop

Add to your Claude Desktop configuration file:

**macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "stdf": {
      "command": "python",
      "args": ["-m", "stdf_mcp.simple_server"],
      "cwd": "/path/to/stdf-mcp"
    }
  }
}
```

Replace `/path/to/stdf-mcp` with the actual path to your installation.

## Usage Examples

### Extract File Overview

```python
# In Claude with MCP server connected
"Please extract the file overview from TestCases/example.stdf"
```

Returns: Lot ID, wafer count, device info, test dates, and file statistics.

### Extract Yield Data

```python
"Extract per-unit yield data from TestCases/production_test.stdf"
```

Generates CSV with columns: PART_ID, HW Bin, SW Bin
- Output location: `TestCases/Output/production_test_YieldAnalysis_20251108_123045.csv`

### Filter Parametric Data

```python
"Extract PTR records for test 'VDD_CURRENT' from TestCases/wafer_test.stdf"
```

Returns filtered parametric test results with statistics.

### Test Time Analysis

```python
"Extract test time analysis for site 1 from TestCases/multi_site.stdf"
```

Generates CSV with per-unit test execution times and summary statistics.

## Tool Reference

### Metadata Tools

| Tool | Description | Output |
|------|-------------|--------|
| `extract_file_overview` | File summary and identifiers | JSON |
| `extract_test_configuration` | Test setup and hardware config | JSON |
| `extract_yield_summary` | Pass/fail counts and yield % | JSON |
| `extract_facility_details` | Manufacturing facility info | JSON |
| `extract_program_metadata` | Test program version/config | JSON |
| `extract_test_parameters` | All test parameters with limits | JSON |

### Record Extraction Tools

| Tool | Description | Filters | Output |
|------|-------------|---------|--------|
| `extract_pir_prr_records` | Part info and results | Site | JSON |
| `extract_ptr_records` | Parametric tests | Test name/number/suite, Site | JSON |
| `extract_ftr_records` | Functional tests | Test name/number/suite, Site | JSON |
| `extract_hbr_records` | Hardware bins | Site | JSON |
| `extract_sbr_records` | Software bins | Site | JSON |
| `extract_sdr_records` | Site descriptions | Site | JSON |
| `extract_mrr_record` | Master results | - | JSON |

### Analysis Tools

| Tool | Description | Key Features | Output |
|------|-------------|--------------|--------|
| `extract_test_parameter_summary` | Statistical summaries | Test suite filtering, Min/Max/Avg/StdDev | JSON |
| `extract_filtered_data` | Filtered data export | Test suite filtering, Multi-site | Excel (.xlsx) |
| `extract_test_time` | Test execution time | Site filtering, Statistics | CSV |
| `extract_per_unit_yield` | Per-unit bin data | 3-column format (no PorF) | CSV |

## Requirements

- **Python**: 3.11 or higher
- **Dependencies**:
  - `mcp>=1.0.0` - Model Context Protocol SDK
  - `numpy>=1.24.0` - Statistical calculations
  - `matplotlib>=3.6.0` - Visualization (future)
  - `openpyxl>=3.1.0` - Excel file generation

## Development

### Setup Development Environment

```bash
# Install with development dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src/stdf_mcp --cov-report=html

# Run specific test categories
pytest -m unit          # Unit tests only
pytest -m integration   # Integration tests only
pytest -m contract      # Contract tests only
```

### Code Quality

```bash
# Format code
black src/ tests/

# Type checking
mypy src/

# Linting
flake8 src/ tests/

# Run all quality checks
black src/ tests/ && flake8 src/ tests/ && mypy src/ && pytest
```

## Project Structure

```
stdf-mcp/
├── src/stdf_mcp/          # Main package
│   ├── stdf/              # STDF parser and record definitions
│   ├── tools/             # MCP tool implementations
│   │   ├── metadata/      # Metadata extraction tools
│   │   ├── records/       # Record extraction tools
│   │   ├── test_summary/  # Test parameter summary
│   │   ├── filtered_data/ # Filtered data extraction
│   │   ├── test_time/     # Test time analysis
│   │   └── yield_analysis/# Yield data extraction
│   └── simple_server.py   # MCP server implementation
├── tests/                 # Test suite
│   ├── unit/             # Unit tests
│   ├── integration/      # Integration tests
│   └── contract/         # Contract tests
├── TestCases/            # Sample STDF files
│   └── Output/           # Generated outputs (gitignored)
├── specs/                # Feature specifications
├── pyproject.toml        # Package configuration
└── README.md             # This file
```

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Metadata extraction | <5 seconds | All 6 metadata tools |
| Record extraction | <10 seconds | For 1GB files |
| Filtered data | <30 seconds | With Excel generation |
| Test time analysis | <10 seconds | Multi-site support |
| Yield extraction | <5 seconds | 10,000 units |
| Memory usage | <512MB | For 2GB files |

## Scope

### Supported

- ✅ STDF-V4 format exclusively
- ✅ Package/final test data
- ✅ Files up to 2GB
- ✅ Streaming/chunked processing
- ✅ Multi-site test configurations
- ✅ Test suite filtering with regex
- ✅ CSV and Excel output formats

### Not Supported

- ❌ STDF-V3 files (rejected with clear error)
- ❌ Wafer test data (package test only)
- ❌ Data retention between sessions
- ❌ Authentication/authorization
- ❌ Direct database access

## Testing

The project uses a comprehensive TDD approach:

- **Unit Tests**: Core STDF-V4 parsing and data models (80%+ coverage)
- **Integration Tests**: End-to-end workflows with real STDF files
- **Contract Tests**: MCP tool API compliance verification
- **TestCases Integration**: Real STDF-V4 files from `TestCases/` directory
- **Output Standards**: Results stored in `TestCases/Output/` with timestamped naming

## Troubleshooting

### Common Issues

**Issue**: `ModuleNotFoundError: No module named 'stdf_mcp'`
- **Solution**: Install the package with `pip install -e .`

**Issue**: MCP server not appearing in Claude Desktop
- **Solution**: Check configuration file path and ensure `cwd` points to the correct directory

**Issue**: `INVALID_STDF_FORMAT` error
- **Solution**: Verify file is STDF-V4 format. STDF-V3 is not supported.

**Issue**: `NO_PRR_RECORDS` error for yield extraction
- **Solution**: File contains no Part Results Records. Verify it's a package test file.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow PEP8 and run code quality checks
4. Write tests for new functionality
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m '[NewFeature] Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Commit Message Format

Use one of these prefixes:
- `[NewFeature]` - New functionality
- `[Enhancement]` - Improvements to existing features
- `[BugFix]` - Bug fixes
- `[Document]` - Documentation updates
- `[WIP]` - Work in progress

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- STDF-V4 Specification: [Teradyne Standard Test Data Format](https://www.teradyne.com/)
- Model Context Protocol: [Anthropic MCP](https://modelcontextprotocol.io/)

## Support

For issues, questions, or contributions:
- **Issues**: [GitHub Issues](https://github.com/your-org/stdf-mcp/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-org/stdf-mcp/discussions)

---

**Version**: 0.1.0
**Status**: Alpha
**Last Updated**: 2025-11-08
