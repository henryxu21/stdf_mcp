"""
STDF-V4 specific exceptions for the MCP server.

This module defines all custom exceptions used throughout the STDF-V4
parsing and processing pipeline, providing clear error messages and
proper exception hierarchy for error handling.
"""

from typing import Optional, Any, List


class STDFError(Exception):
    """Base exception for all STDF-related errors."""

    def __init__(self, message: str, file_path: Optional[str] = None):
        """
        Initialize STDF error with message and optional file context.

        Args:
            message: Error description
            file_path: Optional path to the STDF file causing the error
        """
        self.message = message
        self.file_path = file_path
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with optional file context."""
        if self.file_path:
            return f"{self.message} (File: {self.file_path})"
        return self.message


class InvalidSTDFFormatError(STDFError):
    """Raised when file is not a valid STDF format."""

    def __init__(self, message: str = "Invalid STDF format",
                 file_path: Optional[str] = None):
        super().__init__(message, file_path)


class UnsupportedSTDFVersionError(STDFError):
    """Raised when STDF version is not supported (e.g., V3)."""

    def __init__(self, version: str, file_path: Optional[str] = None):
        message = (f"STDF-{version} is not supported. "
                  f"Only STDF-V4 files are supported.")
        super().__init__(message, file_path)


class UnsupportedTestScopeError(STDFError):
    """Raised when test scope is not supported (e.g., wafer test)."""

    def __init__(self, test_scope: str, file_path: Optional[str] = None):
        message = (f"{test_scope} data is not supported. "
                  f"Only package/final test data is supported.")
        super().__init__(message, file_path)


class UnsupportedCPUArchitectureError(STDFError):
    """Raised when CPU architecture is not supported (e.g., big-endian, non-Intel CPU)."""

    def __init__(self, message: str, cpu_type: int, file_path: Optional[str] = None):
        super().__init__(message, file_path)
        self.cpu_type = cpu_type

    def get_user_guidance(self) -> str:
        """Provide helpful guidance for CPU architecture errors."""
        return (
            "This STDF file was generated on a non-Intel CPU system. "
            "Please use an Intel CPU system to generate STDF files, or "
            "convert the file using an appropriate analysis tool that "
            "supports endianness conversion."
        )


class CorruptedSTDFFileError(STDFError):
    """Raised when STDF file is corrupted or truncated."""

    def __init__(self, message: str = "Corrupted STDF file detected",
                 file_path: Optional[str] = None,
                 position: Optional[int] = None):
        if position is not None:
            message = f"{message} at byte position {position}"
        super().__init__(message, file_path)


class UnsupportedRecordTypeError(STDFError):
    """Raised when encountering unsupported record types (e.g., wafer records)."""

    def __init__(self, record_type: int, record_subtype: int,
                 file_path: Optional[str] = None):
        message = (f"Record type {record_type}:{record_subtype} is not supported. "
                  f"Only package test records are supported.")
        super().__init__(message, file_path)


class RecordParsingError(STDFError):
    """Raised when unable to parse a specific record."""

    def __init__(self, record_type: int, record_subtype: int,
                 parsing_error: str, file_path: Optional[str] = None,
                 position: Optional[int] = None):
        message = (f"Failed to parse record {record_type}:{record_subtype}: "
                  f"{parsing_error}")
        if position is not None:
            message = f"{message} at position {position}"
        super().__init__(message, file_path)


class IntegrityValidationError(STDFError):
    """Raised when file integrity validation fails."""

    def __init__(self, issues: List[str], file_path: Optional[str] = None):
        message = f"File integrity validation failed: {'; '.join(issues)}"
        super().__init__(message, file_path)
        self.issues = issues


class FileSizeExceededError(STDFError):
    """Raised when file size exceeds the configured limit."""

    def __init__(self, file_size: int, max_size: int,
                 file_path: Optional[str] = None):
        message = (f"File size {file_size} bytes exceeds maximum allowed "
                  f"size of {max_size} bytes")
        super().__init__(message, file_path)
        self.file_size = file_size
        self.max_size = max_size


class MemoryLimitExceededError(STDFError):
    """Raised when memory usage exceeds configured limits during processing."""

    def __init__(self, current_usage: int, max_usage: int,
                 operation: str = "file processing"):
        message = (f"Memory usage {current_usage} MB exceeds limit of "
                  f"{max_usage} MB during {operation}")
        super().__init__(message)
        self.current_usage = current_usage
        self.max_usage = max_usage


class SequenceValidationError(STDFError):
    """Raised when record sequence validation fails."""

    def __init__(self, sequence_error: str, site_num: Optional[int] = None,
                 file_path: Optional[str] = None):
        message = f"Record sequence validation failed: {sequence_error}"
        if site_num is not None:
            message = f"{message} (Site: {site_num})"
        super().__init__(message, file_path)


class EndiannessMismatchError(STDFError):
    """Raised when endianness detection or handling fails."""

    def __init__(self, detected_endian: str, expected_endian: str,
                 file_path: Optional[str] = None):
        message = (f"Endianness mismatch: detected {detected_endian}, "
                  f"expected {expected_endian}")
        super().__init__(message, file_path)


class MCPToolError(STDFError):
    """Base exception for MCP tool-specific errors."""

    def __init__(self, tool_name: str, message: str,
                 file_path: Optional[str] = None):
        formatted_message = f"{tool_name}: {message}"
        super().__init__(formatted_message, file_path)
        self.tool_name = tool_name


class MetadataExtractionError(MCPToolError):
    """Raised when metadata extraction fails."""

    def __init__(self, tool_name: str, extraction_error: str,
                 file_path: Optional[str] = None):
        message = f"Metadata extraction failed: {extraction_error}"
        super().__init__(tool_name, message, file_path)


class FilteringError(MCPToolError):
    """Raised when data filtering operations fail."""

    def __init__(self, filter_criteria: str, error_details: str,
                 file_path: Optional[str] = None):
        message = f"Filtering failed for criteria '{filter_criteria}': {error_details}"
        super().__init__("extract_filtered_data", message, file_path)


class StatisticsCalculationError(MCPToolError):
    """Raised when statistical calculations fail."""

    def __init__(self, calculation_type: str, error_details: str,
                 file_path: Optional[str] = None):
        message = f"Statistics calculation failed for {calculation_type}: {error_details}"
        super().__init__("calculate_statistics", message, file_path)


class VisualizationError(MCPToolError):
    """Raised when visualization generation fails."""

    def __init__(self, chart_type: str, error_details: str,
                 file_path: Optional[str] = None):
        message = f"Visualization generation failed for {chart_type}: {error_details}"
        super().__init__("generate_visualization", message, file_path)


class ExportError(MCPToolError):
    """Raised when data export operations fail."""

    def __init__(self, export_format: str, error_details: str,
                 file_path: Optional[str] = None):
        message = f"Export failed for format {export_format}: {error_details}"
        super().__init__("export_csv", message, file_path)


def format_stdf_error(error: Exception, context: Optional[str] = None) -> str:
    """
    Format STDF error for consistent error reporting.

    Args:
        error: The exception to format
        context: Optional context information

    Returns:
        str: Formatted error message
    """
    if isinstance(error, STDFError):
        message = str(error)
        if context:
            message = f"{context}: {message}"
        return message
    else:
        # Format non-STDF errors consistently
        error_type = type(error).__name__
        message = f"{error_type}: {str(error)}"
        if context:
            message = f"{context}: {message}"
        return message


def is_recoverable_error(error: Exception) -> bool:
    """
    Determine if an error is recoverable and processing can continue.

    Args:
        error: The exception to check

    Returns:
        bool: True if error is recoverable, False otherwise
    """
    # File format and version errors are not recoverable
    if isinstance(error, (InvalidSTDFFormatError, UnsupportedSTDFVersionError,
                         UnsupportedTestScopeError, UnsupportedCPUArchitectureError,
                         CorruptedSTDFFileError)):
        return False

    # Memory and size limit errors are not recoverable
    if isinstance(error, (FileSizeExceededError, MemoryLimitExceededError)):
        return False

    # Record-level errors might be recoverable (skip bad records)
    if isinstance(error, (RecordParsingError, UnsupportedRecordTypeError)):
        return True

    # Tool-level errors are often recoverable
    if isinstance(error, MCPToolError):
        return True

    # Unknown errors are not recoverable by default
    return False