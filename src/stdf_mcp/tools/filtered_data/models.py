"""
Data Models for Filtered Test Data Extraction

This module defines the core data models for column-based Excel filtering:
- FilterCriteria: Input validation and filter configuration
- TestNumFilter: Optimized test number filtering (series/range)
- TestParameter: Metadata for one test parameter (one Excel column)
- DeviceTestResults: Complete test data for one device (one Excel row)
- ExcelWorksheet: Column-based worksheet structure
- ExcelWorkbook: Complete workbook with metadata
"""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Set, Tuple, Union


@dataclass
class TestNumFilter:
    """
    Optimized test number filter supporting series, ranges, and mixed inputs.

    Supports:
    - Series: [100, 105, 200] -> set-based O(1) lookup
    - Range: ["1000-1100"] -> numeric range check
    - Mixed: [100, 105, "200-250"] -> combined approach

    Validation Rules (from spec FR-010, FR-011):
    - All test_num values must be 0 to 2^32-1
    - No negative values
    - Range start must be <= end
    - Maximum range size: 10,000 tests
    """

    series_set: Set[int]  # Discrete test numbers for O(1) lookup
    ranges: List[Tuple[int, int]]  # List of (start, end) inclusive ranges

    @classmethod
    def from_input(
        cls, test_num_input: List[Union[int, str]]
    ) -> "TestNumFilter":
        """
        Parse test_num input from MCP tool.

        Args:
            test_num_input: Mixed list of integers and range strings
                Examples: [100], [100, 105, 200], ["1000-1100"], [100, "200-250"]

        Returns:
            TestNumFilter with optimized lookup structures

        Raises:
            ValueError: Invalid test_num, negative, > 2^32-1, invalid range
        """
        series_set: Set[int] = set()
        ranges: List[Tuple[int, int]] = []

        for item in test_num_input:
            if isinstance(item, int):
                # Validate test_num
                if item < 0:
                    raise ValueError(f"Negative test_num not allowed: {item}")
                if item > 2**32 - 1:
                    raise ValueError(
                        f"test_num exceeds maximum (2^32-1): {item}"
                    )

                series_set.add(item)

            elif isinstance(item, str) and "-" in item:
                # Parse range "1000-1100"
                try:
                    start_str, end_str = item.split("-", 1)
                    start, end = int(start_str.strip()), int(end_str.strip())
                except ValueError as e:
                    raise ValueError(
                        f"Invalid range format '{item}': {e}"
                    ) from e

                # Validate range values
                if start < 0 or end < 0:
                    raise ValueError(
                        f"Negative test_num in range '{item}' not allowed"
                    )
                if start > 2**32 - 1 or end > 2**32 - 1:
                    raise ValueError(
                        f"test_num in range '{item}' exceeds maximum (2^32-1)"
                    )
                if start > end:
                    raise ValueError(f"Invalid range '{item}': start > end")
                if end - start > 10000:
                    raise ValueError(
                        f"Range '{item}' exceeds maximum size 10,000"
                    )

                ranges.append((start, end))

            else:
                raise ValueError(
                    f"Invalid test_num input: {item} (type: {type(item)})"
                )

        return cls(series_set=series_set, ranges=ranges)

    def matches(self, test_num: int) -> bool:
        """
        Check if test_num matches this filter.

        Performance: O(1) for series, O(n) for ranges (n typically <10)

        Args:
            test_num: Test number to check

        Returns:
            True if matches filter, False otherwise
        """
        # Check series set first (O(1))
        if test_num in self.series_set:
            return True

        # Check ranges (O(n), typically small n)
        for start, end in self.ranges:
            if start <= test_num <= end:
                return True

        return False


@dataclass
class TestSuiteFilter:
    """
    Test suite filter for TSR hierarchy-based filtering.

    Supports filtering by either simple test suite name (e.g., "Bt5gRxGainCal")
    or fully qualified test suite path (e.g., "Main.RxGainCal.Bt5gRxGainCal").

    Validation Rules (from spec FR-013, FR-014):
    - suite_name must be non-empty string
    - is_qualified must match suite_name structure (dots present for qualified)
    - case_sensitive defaults to False (case-insensitive matching)
    - site_filter is optional (None = all sites)

    Usage:
        # Simple name filtering (case-insensitive)
        simple_filter = TestSuiteFilter(
            suite_name="Bt5gRxGainCal",
            is_qualified=False
        )

        # Qualified name filtering (precise targeting)
        qualified_filter = TestSuiteFilter(
            suite_name="Main.RxGainCal.Bt5gRxGainCal",
            is_qualified=True
        )

        # Case-sensitive matching
        case_filter = TestSuiteFilter(
            suite_name="Bt5gRxGainCal",
            is_qualified=False,
            case_sensitive=True
        )
    """

    suite_name: str  # Simple or qualified test suite name
    is_qualified: bool  # True if suite_name is fully qualified path

    # Optional modifiers
    case_sensitive: bool = False  # False = case-insensitive (default)
    site_filter: Optional[List[int]] = None  # None = all sites

    def __post_init__(self) -> None:
        """Validate TestSuiteFilter fields."""
        # Import here to avoid circular dependency
        from stdf_mcp.tools.filtered_data.hierarchy import is_hierarchical_name

        # Validate suite_name non-empty
        if not self.suite_name or not self.suite_name.strip():
            raise ValueError("suite_name cannot be empty or whitespace only")

        # Validate is_qualified matches suite_name structure
        has_hierarchy = is_hierarchical_name(self.suite_name)
        if self.is_qualified and not has_hierarchy:
            raise ValueError(
                f"is_qualified=True but suite_name '{self.suite_name}' "
                f"has no hierarchy (no unescaped dots). "
                f"Use is_qualified=False for simple names."
            )

        # Validate site numbers if specified
        if self.site_filter:
            for site in self.site_filter:
                if not (0 <= site <= 255):
                    raise ValueError(
                        f"Site number {site} out of valid range 0-255"
                    )

    @property
    def normalized_suite_name(self) -> str:
        """Return case-normalized suite name for matching."""
        if self.case_sensitive:
            return self.suite_name
        return self.suite_name.lower()


@dataclass
class FilterCriteria:
    """
    Filter criteria for STDF test data extraction.

    Validation Rules (from spec FR-007, FR-008, FR-010, FR-011, FR-012):
    - Exactly one of test_name_pattern, test_num_filter, or test_suite_filter
    - site_filter is optional (None = all sites)
    - output_directory must be absolute path and writable
    """

    # Test identifier filter (mutually exclusive)
    test_name_pattern: Optional[Pattern[str]] = None  # Compiled regex pattern
    test_num_filter: Optional[TestNumFilter] = None
    test_suite_filter: Optional[TestSuiteFilter] = None  # TSR hierarchy filter

    # Optional site filter
    site_filter: Optional[List[int]] = None  # None = all sites

    # Output configuration
    output_directory: Path = Path("/tmp")  # Absolute path

    def __post_init__(self) -> None:
        """Validate filter criteria."""
        # Count active filters
        active_filters = sum([
            self.test_name_pattern is not None,
            self.test_num_filter is not None,
            self.test_suite_filter is not None
        ])

        # Ensure exactly one test identifier specified
        if active_filters == 0:
            raise ValueError(
                "Must specify one of: test_name_pattern, test_num_filter, "
                "or test_suite_filter"
            )

        if active_filters > 1:
            raise ValueError(
                "Cannot specify multiple filters simultaneously: "
                "test_name_pattern, test_num_filter, test_suite_filter"
            )

        # Validate output directory is absolute
        if not self.output_directory.is_absolute():
            raise ValueError(
                f"Output directory must be absolute path: {self.output_directory}"
            )

        # Validate site numbers if specified
        if self.site_filter:
            for site in self.site_filter:
                if not (0 <= site <= 255):
                    raise ValueError(
                        f"Site number {site} out of valid range 0-255"
                    )


@dataclass
class TestParameter:
    """
    Test parameter metadata for Excel column headers.

    Represents metadata for one test parameter column in the Excel file.
    Used to generate column headers and track test parameter information.

    Column Header Format (from spec FR-020):
    - Use test_name when available (e.g., "VDD_CURRENT")
    - Fall back to "TestNum_[number]" when test_name is null
    """

    # Parameter identification
    test_name: str  # Test parameter name or "TestNum_1052"
    test_number: int  # Test number from STDF (0 to 2^32-1)

    # Optional metadata (for reference, not displayed in column header)
    units: Optional[str] = None  # Measurement units
    lo_limit: Optional[float] = None  # Lower specification limit
    hi_limit: Optional[float] = None  # Upper specification limit

    def get_column_header(self) -> str:
        """
        Generate Excel column header with sanitization.

        Rules (from spec FR-021):
        - Replace invalid characters (/ \\ ? * : [ ]) with underscore

        Returns:
            Sanitized column header name
        """
        # Replace invalid characters
        sanitized = re.sub(r"[/\\?*:\[\]]", "_", self.test_name)
        return sanitized


@dataclass
class DeviceTestResults:
    """
    Complete test results for one device (one Excel row).

    Represents all test data for a single device test cycle in row-per-device format.
    This is the core data structure for column-based Excel output.

    Excel Row Mapping:
    - device_id -> Device_ID column (Column A)
    - site -> Site column (Column B)
    - head -> Head column (Column C)
    - timestamp -> Timestamp column (Column D)
    - test_results[param_name] -> Dynamic test result columns (E, F, G, ...)

    Sparse Data Model:
    - test_results Dict only contains entries for tests that were actually run
    - Missing tests have no dict entry (not None) -> empty Excel cells
    - Memory efficient: Only store actual results
    """

    # Device identification (from PIR record)
    device_id: str  # Package device ID (part_id from PIR)

    # Test execution context (from PIR record)
    site: int  # Test site number (0-255)
    head: int  # Test head number
    timestamp: Optional[datetime]  # Test execution time

    # Test results (sparse dictionary)
    # Key: Test parameter name (e.g., "VDD_CURRENT")
    # Value: Measured test result (float)
    # Missing tests: No dict entry (sparse)
    test_results: Dict[str, Optional[float]]

    def get_test_result(self, parameter_name: str) -> Optional[float]:
        """
        Get test result for specific parameter.

        Args:
            parameter_name: Test parameter name (e.g., "VDD_CURRENT")

        Returns:
            Test result value, or None if test not run on this device
        """
        return self.test_results.get(parameter_name, None)

    def to_excel_row(self, ordered_parameters: List[str]) -> List[Any]:
        """
        Convert to Excel row list with proper column ordering.

        Args:
            ordered_parameters: Ordered list of test parameter names (column order)

        Returns:
            List with common columns + test results in parameter order
            Format: [device_id, site, head, timestamp, result1, result2, ...]
        """
        # Common columns
        row: List[Any] = [
            self.device_id,
            self.site,
            self.head,
            self.timestamp,
        ]

        # Test result columns (in parameter order, None for missing)
        for param_name in ordered_parameters:
            result = self.test_results.get(param_name, None)
            row.append(result)

        return row


@dataclass
class ExcelWorksheet:
    """
    Complete Excel worksheet structure for column-based filtered test data.

    Structure:
    - Single worksheet: "Filtered_Test_Data"
    - Column layout:
      - Common columns (fixed, 4 columns): Device_ID, Site, Head, Timestamp
      - Test result columns (dynamic, 1-16,380): One per filtered parameter
    - Row layout:
      - One row per device in chronological order (STDF execution sequence)

    Validation Rules (from spec FR-019, FR-022, FR-023):
    - Maximum 16,384 total columns (Excel 2007+ limit)
    - Common columns: 4 (Device_ID, Site, Head, Timestamp)
    - Available for test parameters: 16,380
    - Row ordering: STDF execution sequence (chronological device order)
    """

    # Common columns (fixed)
    common_columns: List[str]  # ["Device_ID", "Site", "Head", "Timestamp"]

    # Test parameter columns (dynamic, ordered)
    test_parameters: List[TestParameter]  # Ordered list for column headers

    # Device rows (chronological order)
    # CRITICAL: Must preserve STDF execution sequence
    device_rows: List[DeviceTestResults]

    def __post_init__(self) -> None:
        """Validate worksheet structure."""
        # Validate column count
        total_columns = len(self.common_columns) + len(self.test_parameters)
        if total_columns > 16384:
            raise ValueError(
                f"Column count {total_columns} exceeds Excel limit 16,384 "
                f"(common: {len(self.common_columns)}, "
                f"parameters: {len(self.test_parameters)})"
            )

        # Ensure common columns are correct
        expected_common = ["Device_ID", "Site", "Head", "Timestamp"]
        if self.common_columns != expected_common:
            raise ValueError(f"Common columns must be {expected_common}")

        # Ensure we have data
        if not self.device_rows:
            raise ValueError("No device data to export")

    @property
    def total_columns(self) -> int:
        """Total number of columns in worksheet."""
        return len(self.common_columns) + len(self.test_parameters)

    @property
    def total_rows(self) -> int:
        """Total number of data rows (excluding header)."""
        return len(self.device_rows)

    @property
    def parameter_count(self) -> int:
        """Number of test parameter columns."""
        return len(self.test_parameters)

    def get_column_headers(self) -> List[str]:
        """
        Generate complete list of column headers for Excel.

        Returns:
            List of column headers: common columns + test parameter columns
            Example: ["Device_ID", "Site", "Head", "Timestamp", "VDD_CURRENT", ...]
        """
        # Common columns first
        headers = self.common_columns.copy()

        # Test parameter columns (sanitized)
        for param in self.test_parameters:
            headers.append(param.get_column_header())

        return headers

    def get_ordered_parameter_names(self) -> List[str]:
        """
        Get ordered list of test parameter names for row generation.

        Returns:
            List of parameter names in column order
        """
        return [param.test_name for param in self.test_parameters]


@dataclass
class ExcelWorkbook:
    """
    Complete Excel workbook structure for filtered test data.

    Structure:
    - Single data worksheet: "Filtered_Test_Data" (column-based format)
    - Optional metadata worksheet: "_Metadata" (filter criteria, statistics)

    This is a lightweight wrapper around ExcelWorksheet with additional metadata.
    """

    # Main data worksheet (column-based)
    worksheet: ExcelWorksheet

    # Metadata
    filter_criteria: FilterCriteria  # Original filter criteria
    stdf_file_path: Path  # Source STDF file
    extraction_time_seconds: float  # Time to extract data
    timestamp: datetime  # When extraction occurred

    @property
    def total_parts_matched(self) -> int:
        """Total number of devices that matched filter criteria."""
        return len(self.worksheet.device_rows)

    @property
    def total_test_columns(self) -> int:
        """Total number of test result columns (excluding common columns)."""
        return self.worksheet.parameter_count

    def generate_metadata_dict(self) -> Dict[str, Any]:
        """
        Generate metadata dictionary for optional metadata worksheet.

        Returns:
            Dictionary with filter criteria, statistics, and data organization
        """
        return {
            "Filter Criteria": {
                "STDF File": str(self.stdf_file_path),
                "Test Parameter Filter": self._format_parameter_filter(),
                "Site Filter": self._format_site_filter(),
                "Output Directory": str(self.filter_criteria.output_directory),
            },
            "Execution Statistics": {
                "Total Devices Matched": self.total_parts_matched,
                "Total Test Parameters": self.total_test_columns,
                "Total Columns": self.worksheet.total_columns,
                "Total Rows": self.worksheet.total_rows,
                "Extraction Time (seconds)": round(
                    self.extraction_time_seconds, 2
                ),
                "Timestamp": self.timestamp.isoformat(),
            },
            "Data Organization": {
                "Format": "Column-based (one column per test parameter)",
                "Common Columns": ", ".join(self.worksheet.common_columns),
                "Test Parameter Columns": self.total_test_columns,
                "Row Organization": "One row per device (STDF execution sequence)",
                "Sparse Data": "Empty cells for tests not run on specific devices",
            },
        }

    def _format_parameter_filter(self) -> str:
        """Format parameter filter for metadata display."""
        if self.filter_criteria.test_name_pattern:
            return (
                f'test_name="{self.filter_criteria.test_name_pattern.pattern}"'
            )
        elif self.filter_criteria.test_num_filter:
            tnf = self.filter_criteria.test_num_filter
            parts = []
            if tnf.series_set:
                parts.append(f"series={sorted(tnf.series_set)}")
            if tnf.ranges:
                parts.append(f"ranges={tnf.ranges}")
            return f"test_num({', '.join(parts)})"
        return "N/A"

    def _format_site_filter(self) -> str:
        """Format site filter for metadata display."""
        if self.filter_criteria.site_filter is None:
            return "ALL SITES"
        return str(self.filter_criteria.site_filter)
