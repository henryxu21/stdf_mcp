"""
STDF-V4 MCP Server Package.

This package provides a comprehensive Model Context Protocol (MCP) server
for processing Standard Test Data Format (STDF-V4) files used in
semiconductor testing. It includes parsing, validation, analysis,
and data extraction capabilities optimized for package/final test data.

Main Components:
- STDF-V4 streaming parser with integrity validation
- Comprehensive record type support (file, part, test, summary records)
- Statistical analysis and yield calculation
- Package test domain analysis
- 10-tool MCP server interface
- Data export and visualization support

Usage:
    from stdf_mcp import STDFMCPServer, convert_stdf_file

    # Run MCP server
    server = STDFMCPServer()
    await server.run()

    # Convert STDF file directly
    stdf_data = convert_stdf_file(Path("test.stdf"))
"""

# Version information
__version__ = "1.0.0"
__author__ = "STDF AI Agent"
__description__ = "STDF-V4 MCP Server for semiconductor test data analysis"

# Core imports
from .server import STDFMCPServer
from .stdf.converter import convert_stdf_file, STDFConverter
from .stdf.parser import STDFV4Parser, ParserConfig
from .stdf.stdf_data import STDFData
from .stdf.package_test import PackageTestAnalyzer
from .stdf.statistics import StatisticalAnalyzer
from .stdf.integrity import IntegrityValidator

# Exception imports
from .stdf.exceptions import (
    STDFError,
    InvalidSTDFFormatError,
    UnsupportedSTDFVersionError,
    UnsupportedTestScopeError,
    CorruptedSTDFFileError,
    RecordParsingError,
    IntegrityValidationError
)

# Utility imports - TODO: Implement missing utility functions
# from .stdf.utils import (
#     format_file_size,
#     format_duration,
#     format_percentage,
#     get_testcases_output_dir,
#     create_output_filename
# )

# Export public API
__all__ = [
    # Core classes
    "STDFMCPServer",
    "STDFConverter",
    "STDFV4Parser",
    "STDFData",
    "PackageTestAnalyzer",
    "StatisticalAnalyzer",
    "IntegrityValidator",

    # Configuration
    "ParserConfig",

    # Convenience functions
    "convert_stdf_file",

    # Exceptions
    "STDFError",
    "InvalidSTDFFormatError",
    "UnsupportedSTDFVersionError",
    "UnsupportedTestScopeError",
    "CorruptedSTDFFileError",
    "RecordParsingError",
    "IntegrityValidationError",

    # Utilities
    "format_file_size",
    "format_duration",
    "format_percentage",
    "get_testcases_output_dir",
    "create_output_filename",

    # Version info
    "__version__",
    "__author__",
    "__description__"
]


def get_version_info():
    """Get version information."""
    return {
        "version": __version__,
        "description": __description__,
        "author": __author__
    }


def main():
    """Main entry point for running STDF MCP server."""
    import asyncio
    server = STDFMCPServer()
    asyncio.run(server.run())


if __name__ == "__main__":
    main()