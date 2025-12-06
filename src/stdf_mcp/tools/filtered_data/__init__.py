"""
Filtered Test Data Extraction Tool

This module provides functionality for filtering STDF test data by test name/number
and optional site filtering, with output to column-based Excel format.

Key Components:
- FilterCriteria: Input validation and filter configuration
- FilterEngine: Test name/number and site filtering logic
- DeviceAccumulator: Device-centric data accumulation for column-based Excel
- ExcelGenerator: Column-based Excel file generation with dynamic columns
- extract_filtered_data: MCP tool entry point

Architecture:
- Column-based Excel format: One column per test parameter, one row per device
- Device-centric data model: Complete test cycle per row (not parameter-centric)
- Streaming STDF processing: Memory-efficient for large files (<512MB for 2GB files)
- Sparse data handling: Empty cells for tests not run on specific devices
"""

from .models import (
    FilterCriteria,
    TestNumFilter,
    TestParameter,
    DeviceTestResults,
    ExcelWorksheet,
    ExcelWorkbook,
)
from .tool import extract_filtered_data

__all__ = [
    "FilterCriteria",
    "TestNumFilter",
    "TestParameter",
    "DeviceTestResults",
    "ExcelWorksheet",
    "ExcelWorkbook",
    "extract_filtered_data",
]
