"""Test parameter summary extraction combining TSR statistics with PTR limits.

This module provides functions to extract comprehensive test parameter
summaries by correlating TSR (Test Synopsis Record) statistics with PTR
(Parametric Test Record) limits from STDF files.

CSV export supports two aggregation modes (Feature 011):
- per_site: One row per test per site (default, backward compatible)
- overall: One row per test aggregated across all sites (66% size reduction)
"""

import re
import csv
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Literal
from collections import defaultdict

# Type aliases for CSV aggregation feature (Feature 011)
CsvAggregationLevelType = Literal["per_site", "overall"]

# Foundational utilities (Phase 2: T004-T006)


def _validate_test_num_inputs(
    test_num: Optional[int],
    test_num_start: Optional[int],
    test_num_end: Optional[int],
) -> None:
    """Validate test_num input parameters.

    Implements validation rules VR-1 through VR-7 per research.md Decision 5.

    Args:
        test_num: Single test number (optional)
        test_num_start: Range start (optional)
        test_num_end: Range end (optional)

    Raises:
        ValueError: If validation fails with clear error message
    """
    # VR-7: Integer type validation
    if test_num is not None and not isinstance(test_num, int):
        raise ValueError(
            f"test_num must be an integer, got {type(test_num).__name__}"
        )
    if test_num_start is not None and not isinstance(test_num_start, int):
        raise ValueError(
            f"test_num_start must be an integer, got {type(test_num_start).__name__}"
        )
    if test_num_end is not None and not isinstance(test_num_end, int):
        raise ValueError(
            f"test_num_end must be an integer, got {type(test_num_end).__name__}"
        )

    # VR-5: test_num XOR range mutual exclusion
    if test_num is not None and (
        test_num_start is not None or test_num_end is not None
    ):
        raise ValueError(
            "Cannot specify both test_num and range (test_num_start/test_num_end)"
        )

    # VR-6: Both start AND end required for range
    if (test_num_start is not None and test_num_end is None) or (
        test_num_start is None and test_num_end is not None
    ):
        raise ValueError(
            "Both start and end required for range query (test_num_start AND test_num_end)"
        )

    # VR-1: test_num >= 0
    if test_num is not None and test_num < 0:
        raise ValueError(f"test_num must be >= 0, got {test_num}")
    if test_num_start is not None and test_num_start < 0:
        raise ValueError(f"test_num_start must be >= 0, got {test_num_start}")
    if test_num_end is not None and test_num_end < 0:
        raise ValueError(f"test_num_end must be >= 0, got {test_num_end}")

    # VR-2: test_num <= 2^32-1 (STDF spec limit)
    MAX_TEST_NUM = 4294967295  # 2^32 - 1
    if test_num is not None and test_num > MAX_TEST_NUM:
        raise ValueError(
            f"test_num must be <= {MAX_TEST_NUM} (2^32-1), got {test_num}"
        )
    if test_num_start is not None and test_num_start > MAX_TEST_NUM:
        raise ValueError(
            f"test_num_start must be <= {MAX_TEST_NUM} (2^32-1), got {test_num_start}"
        )
    if test_num_end is not None and test_num_end > MAX_TEST_NUM:
        raise ValueError(
            f"test_num_end must be <= {MAX_TEST_NUM} (2^32-1), got {test_num_end}"
        )

    # VR-3: start <= end
    if test_num_start is not None and test_num_end is not None:
        if test_num_start > test_num_end:
            raise ValueError(
                f"test_num_start must be <= end, got start={test_num_start}, end={test_num_end}"
            )

    # VR-4: range size <= 10000 (performance protection)
    if test_num_start is not None and test_num_end is not None:
        range_size = test_num_end - test_num_start + 1
        if range_size > 10000:
            raise ValueError(
                f"Range size must be <= 10000, got {range_size} (from {test_num_start} to {test_num_end})"
            )


def _validate_inputs(
    file_path: str,
    test_name: Optional[str] = None,
    test_num: Optional[int] = None,
    test_num_start: Optional[int] = None,
    test_num_end: Optional[int] = None,
    test_suite_name: Optional[str] = None,
    use_regex: bool = False,
    result_limit: int = 1000,
) -> None:
    """Validate input parameters for test parameter summary extraction.

    Args:
        file_path: Absolute path to STDF V4 file
        test_name: Test parameter name or regex pattern (optional)
        test_num: Single test number (optional)
        test_num_start: Range start test number (optional)
        test_num_end: Range end test number (optional)
        test_suite_name: Test suite name filter (optional)
        use_regex: If True, validate test_name as regex pattern
        result_limit: Maximum number of summaries to return (1-10000)

    Raises:
        FileNotFoundError: If file_path does not exist
        ValueError: If inputs are invalid or no search criterion provided
    """
    # Validate file exists
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Validate result_limit range
    if not (1 <= result_limit <= 10000):
        raise ValueError(
            f"result_limit must be between 1 and 10000, got {result_limit}"
        )

    # Validate test_num inputs (VR-1 through VR-7)
    _validate_test_num_inputs(test_num, test_num_start, test_num_end)

    # Ensure at least one search criterion is provided
    has_test_name = test_name is not None
    has_test_num = test_num is not None
    has_range = test_num_start is not None and test_num_end is not None
    has_test_suite = test_suite_name is not None

    if not (has_test_name or has_test_num or has_range or has_test_suite):
        raise ValueError(
            "Must provide at least one search criterion: test_name, test_num, "
            "test_num range, or test_suite_name"
        )

    # Validate regex pattern if use_regex=True
    if use_regex and test_name is not None:
        try:
            re.compile(test_name)
        except re.error as e:
            raise ValueError(
                f"Invalid regular expression pattern: {test_name} - {str(e)}"
            )


def _format_error_response(
    error_type: str, error_message: str, details: Optional[str] = None
) -> Dict[str, Any]:
    """Format error response with structured metadata.

    Args:
        error_type: Type of error (FileNotFound, InvalidFormat, InvalidRegex, TestNotFound)
        error_message: Human-readable error message
        details: Optional additional error details

    Returns:
        Structured error response dictionary
    """
    response = {
        "error": error_message,
        "error_type": error_type,
        "_metadata": {
            "tool": "extract_test_parameter_summary",
            "error_time": datetime.now().isoformat(),
        },
    }

    if details:
        response["details"] = details

    return response


def _create_metadata(
    tsr_count: int, ptr_count: int, file_path: str
) -> Dict[str, Any]:
    """Generate metadata for successful extraction response.

    Args:
        tsr_count: Number of TSR records found
        ptr_count: Number of PTR records correlated
        file_path: Source STDF file path

    Returns:
        Metadata dictionary with tool info and statistics
    """
    return {
        "tool": "extract_test_parameter_summary",
        "version": "1.0.0",
        "extraction_time": datetime.now().isoformat(),
        "tsr_records_found": tsr_count,
        "ptr_records_correlated": ptr_count,
        "file_path": file_path,
    }


# User Story 1 Implementation (Phase 3: T013-T018)


def _filter_tsr(
    tsr_records: List[Any],
    pattern: Optional[str] = None,
    use_regex: bool = False,
    test_num: Optional[int] = None,
    test_num_range: Optional[Tuple[int, int]] = None,
) -> List[Any]:
    """Filter TSR records by test name and/or test_num (unified filtering).

    Per research.md Decision 1: Renamed from _filter_tsr_by_name to support
    multi-criteria filtering (test_name, test_num, range).

    Args:
        tsr_records: List of TSR records
        pattern: Test name (exact) or regex pattern (optional)
        use_regex: If True, treat pattern as regex
        test_num: Single test number to match (optional)
        test_num_range: Tuple of (start, end) for range query (optional)

    Returns:
        Filtered list of TSR records matching the specified criteria
    """
    filtered = []

    for tsr in tsr_records:
        # Test name filtering (if pattern provided)
        name_match = True
        if pattern is not None:
            if not use_regex:
                # Exact match (case-sensitive)
                name_match = tsr.test_nam == pattern
            else:
                # Regex match (skip null test names)
                if tsr.test_nam is None:
                    name_match = False
                else:
                    regex = re.compile(pattern)
                    name_match = regex.match(tsr.test_nam) is not None

        # Test number filtering (if test_num or range provided)
        num_match = True
        if test_num is not None:
            # Single test_num match
            num_match = tsr.test_num == test_num
        elif test_num_range is not None:
            # Range match (inclusive)
            start, end = test_num_range
            num_match = start <= tsr.test_num <= end

        # Include TSR only if BOTH criteria match (AND logic for combined filtering)
        if name_match and num_match:
            filtered.append(tsr)

    return filtered


# Backward compatibility alias: Keep old function name for existing code
def _filter_tsr_by_name(
    tsr_records: List[Any], pattern: str, use_regex: bool = False
) -> List[Any]:
    """Filter TSR records by test name (exact or regex match).

    DEPRECATED: Use _filter_tsr() instead. Kept for backward compatibility.

    Args:
        tsr_records: List of TSR records
        pattern: Test name (exact) or regex pattern
        use_regex: If True, treat pattern as regex

    Returns:
        Filtered list of TSR records
    """
    return _filter_tsr(tsr_records, pattern=pattern, use_regex=use_regex)


def _group_ptr_by_test_num(ptr_records: List[Any]) -> Dict[int, List[Any]]:
    """Group PTR records by test_num for efficient lookup.

    Args:
        ptr_records: List of PTR records

    Returns:
        Dictionary mapping test_num to list of PTR records
    """
    grouped = defaultdict(list)
    for ptr in ptr_records:
        grouped[ptr.test_num].append(ptr)
    return dict(grouped)


def _extract_limits_from_first_ptr(
    ptr_records: List[Any],
) -> Dict[str, Optional[float]]:
    """Extract limits from first PTR record (all have identical limits).

    Args:
        ptr_records: List of PTR records for a test_num

    Returns:
        Dictionary with lo_limit, hi_limit, units (or nulls if no PTR)
    """
    if not ptr_records:
        return {"lo_limit": None, "hi_limit": None, "units": None}

    first_ptr = ptr_records[0]
    lo_limit, hi_limit = first_ptr.get_scaled_limits()

    return {
        "lo_limit": lo_limit,
        "hi_limit": hi_limit,
        "units": first_ptr.units,
    }


def _extract_test_identification(tsr: Any) -> Dict[str, Any]:
    """Extract test identification fields from TSR.

    Args:
        tsr: TSR record

    Returns:
        Dictionary with test identification fields
    """
    return {
        "test_num": tsr.test_num,
        "test_nam": tsr.test_nam,
        "test_typ": tsr.test_typ,
        "head_num": tsr.head_num,
        "site_num": tsr.site_num,
        "seq_name": tsr.seq_name,
        "test_lbl": tsr.test_lbl,
    }


def _extract_execution_statistics(tsr: Any) -> Dict[str, Any]:
    """Extract execution statistics from TSR.

    Args:
        tsr: TSR record

    Returns:
        Dictionary with execution statistics
    """
    return {
        "exec_cnt": tsr.exec_cnt,
        "fail_cnt": tsr.fail_cnt,
        "alrm_cnt": tsr.alrm_cnt,
        "test_tim": tsr.test_tim,
    }


def _extract_statistical_measures(tsr: Any) -> Dict[str, Any]:
    """Extract statistical measures from TSR.

    Args:
        tsr: TSR record

    Returns:
        Dictionary with statistical measures
    """
    return {
        "test_min": tsr.test_min,
        "test_max": tsr.test_max,
        "tst_sums": tsr.tst_sums,
        "tst_sqrs": tsr.tst_sqrs,
    }


def _calculate_derived_metrics(
    exec_cnt: int,
    fail_cnt: int,
    tst_sums: Optional[float],
    tst_sqrs: Optional[float],
) -> Dict[str, Optional[float]]:
    """Calculate derived metrics from TSR statistics (Phase 6: T035).

    Calculates pass counts, pass/fail rates, mean, and standard deviation.

    Args:
        exec_cnt: Number of test executions
        fail_cnt: Number of test failures
        tst_sums: Sum of all test results (or None)
        tst_sqrs: Sum of squares of all test results (or None)

    Returns:
        Dictionary with derived metrics:
        - pass_cnt: Number of passing tests
        - pass_rate: Percentage of tests that passed
        - fail_rate: Percentage of tests that failed
        - mean: Average test result value
        - stddev: Standard deviation of test results
    """
    import math

    # Calculate pass count (always possible)
    pass_cnt = exec_cnt - fail_cnt

    # Calculate pass/fail rates (handle division by zero)
    if exec_cnt > 0:
        pass_rate = (pass_cnt / exec_cnt) * 100.0
        fail_rate = (fail_cnt / exec_cnt) * 100.0
    else:
        pass_rate = None
        fail_rate = None

    # Calculate mean and stddev (requires non-null tst_sums and tst_sqrs)
    mean = None
    stddev = None

    if tst_sums is not None and tst_sqrs is not None and exec_cnt > 0:
        mean = tst_sums / exec_cnt

        # Calculate variance: Var = E[X^2] - E[X]^2
        variance = (tst_sqrs / exec_cnt) - (mean * mean)

        # Handle negative variance (numerical precision issues)
        if variance < 0:
            variance = 0.0

        stddev = math.sqrt(variance)

    return {
        "pass_cnt": pass_cnt,
        "pass_rate": pass_rate,
        "fail_rate": fail_rate,
        "mean": mean,
        "stddev": stddev,
    }


def _correlate_tsr_with_ptr(
    tsr: Any, ptr_records: List[Any], include_derived: bool = False
) -> Dict[str, Any]:
    """Merge TSR statistics with PTR limits.

    Args:
        tsr: TSR record
        ptr_records: List of PTR records for this test_num
        include_derived: If True, include derived metrics (Phase 6: T036)

    Returns:
        Complete TestParameterSummary dictionary
    """
    # Base statistics
    execution_stats = _extract_execution_statistics(tsr)
    statistical_measures = _extract_statistical_measures(tsr)

    # Add derived metrics if requested (Phase 6)
    if include_derived:
        derived = _calculate_derived_metrics(
            exec_cnt=tsr.exec_cnt,
            fail_cnt=tsr.fail_cnt,
            tst_sums=tsr.tst_sums,
            tst_sqrs=tsr.tst_sqrs,
        )

        # Add pass/fail metrics to execution_statistics
        execution_stats["pass_cnt"] = derived["pass_cnt"]
        execution_stats["pass_rate"] = derived["pass_rate"]
        execution_stats["fail_rate"] = derived["fail_rate"]

        # Add mean/stddev to statistical_measures
        statistical_measures["mean"] = derived["mean"]
        statistical_measures["stddev"] = derived["stddev"]

    return {
        "test_identification": _extract_test_identification(tsr),
        "execution_statistics": execution_stats,
        "statistical_measures": statistical_measures,
        "test_limits": _extract_limits_from_first_ptr(ptr_records),
    }


# CSV Export Functions (Feature 010: T010-T013)


# Feature 011: CSV aggregation helper functions


def _filter_overall_summaries(summaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter summaries to return only overall aggregates (HEAD_NUM=255, SITE_NUM=0).

    According to STDF V4 specification, TSR (Test Synopsis Record) with HEAD_NUM=255
    indicates aggregate statistics across all test heads/sites. The ATE automatically
    calculates and stores these overall statistics - we don't need to compute them.

    This is the CORRECT approach per STDF spec, not manual aggregation.

    Reference: STDF V4 spec states HEAD_NUM=255 is used for summary records that
    apply to all test sites collectively.

    Args:
        summaries: List of all test summaries (per-site and overall)

    Returns:
        List containing only overall summaries (HEAD_NUM=255)
    """
    overall_summaries = []

    for summary in summaries:
        test_id = summary["test_identification"]
        head_num = test_id.get("head_num")

        # Per STDF V4 spec: HEAD_NUM=255 indicates overall aggregate
        if head_num == 255:
            # Remove head_num and site_num from overall summaries for CSV export
            # These fields don't make sense for aggregated data
            test_id_copy = test_id.copy()
            test_id_copy.pop("head_num", None)
            test_id_copy.pop("site_num", None)

            summary_copy = summary.copy()
            summary_copy["test_identification"] = test_id_copy
            overall_summaries.append(summary_copy)

    return overall_summaries


def transform_summary_to_csv_row(
    summary: Dict[str, Any],
    include_derived: bool,
    aggregation_level: CsvAggregationLevelType = "per_site",
) -> Dict[str, str]:
    """Transform nested JSON summary to flat CSV row.

    Flattens the nested test parameter summary structure into a
    single-level dictionary suitable for CSV export. All values
    are converted to strings, and null values become "N/A".

    Args:
        summary: Test parameter summary dictionary with nested structure
        include_derived: If True, include derived metric columns
                        (Pass_Count, Pass_Rate, Fail_Rate)
        aggregation_level: CSV aggregation mode (Feature 011)
                          - "per_site": Include Head_Number and Site_Number columns
                          - "overall": Omit Head_Number and Site_Number columns

    Returns:
        Flat dictionary with string values for all CSV columns

    Example:
        >>> summary = {
        ...     "test_identification": {"test_name": "VDD_CORE", "test_num": 1052},
        ...     "execution_statistics": {"exec_cnt": 100, "fail_cnt": 5},
        ...     "statistical_measures": {"test_min": 1.18, "test_max": 1.23},
        ...     "test_limits": {"lo_limit": 1.15, "hi_limit": 1.25, "units": "V"}
        ... }
        >>> row = transform_summary_to_csv_row(summary, include_derived=False)
        >>> row["Test_Name"]
        'VDD_CORE'
        >>> row["Test_Number"]
        '1052'
    """
    test_id = summary["test_identification"]
    exec_stats = summary["execution_statistics"]
    stat_measures = summary["statistical_measures"]
    limits = summary["test_limits"]

    # Helper function for null-safe string conversion
    def to_str(value):
        """Convert value to string, using 'N/A' for None."""
        if value is None:
            return "N/A"
        return str(value)

    # Build base row - columns depend on aggregation mode
    row = {
        "Test_Name": to_str(test_id.get("test_nam")),
        "Test_Number": to_str(test_id.get("test_num")),
        "Suite_Name": to_str(test_id.get("seq_name")),
    }

    # Add Head/Site columns only for per-site mode
    if aggregation_level == "per_site":
        row["Head_Number"] = to_str(test_id.get("head_num"))
        row["Site_Number"] = to_str(test_id.get("site_num"))

    # Add remaining columns (same for both modes)
    row.update(
        {
            "Test_Count": to_str(exec_stats.get("exec_cnt")),
            "Fail_Count": to_str(exec_stats.get("fail_cnt")),
            "Min_Value": to_str(stat_measures.get("test_min")),
            "Max_Value": to_str(stat_measures.get("test_max")),
            "Mean_Value": to_str(stat_measures.get("mean")),
            "Std_Dev": to_str(stat_measures.get("stddev")),
            "Low_Limit": to_str(limits.get("lo_limit")),
            "High_Limit": to_str(limits.get("hi_limit")),
            "Units": to_str(limits.get("units")),
        }
    )

    # Add derived metric columns if requested and data available
    if include_derived and "pass_cnt" in exec_stats:
        row["Pass_Count"] = to_str(exec_stats.get("pass_cnt"))
        row["Pass_Rate"] = to_str(exec_stats.get("pass_rate"))
        row["Fail_Rate"] = to_str(exec_stats.get("fail_rate"))

    return row


def generate_csv_filename(stdf_path: Path, timestamp: datetime) -> str:
    """Generate CSV filename with timestamp.

    Format: <STDF_basename>_TestParameterSummary_<YYYYMMDD_HHMMSS>.csv

    Args:
        stdf_path: Path to STDF file (used to extract basename)
        timestamp: Timestamp to include in filename

    Returns:
        Generated filename string (not full path)

    Example:
        >>> from datetime import datetime
        >>> stdf_path = Path("/path/to/example.stdf")
        >>> ts = datetime(2025, 11, 8, 14, 30, 22)
        >>> generate_csv_filename(stdf_path, ts)
        'example_TestParameterSummary_20251108_143022.csv'
    """
    stdf_basename = stdf_path.stem  # Extract filename without extension
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    return f"{stdf_basename}_TestParameterSummary_{timestamp_str}.csv"


def validate_output_path(output_directory: Optional[str]) -> bool:
    """Validate output directory path.

    Checks for common path issues:
    - Empty string or None
    - Null bytes in path
    - Excessive path length (>4096 characters)

    Args:
        output_directory: Directory path to validate

    Returns:
        True if path is valid, False otherwise

    Example:
        >>> validate_output_path("TestCases/Output")
        True
        >>> validate_output_path("")
        False
        >>> validate_output_path(None)
        False
    """
    if not output_directory:
        return False

    # Check for null bytes
    if "\x00" in output_directory:
        return False

    # Check path length (4096 is typical Linux limit, 260 for Windows)
    if len(output_directory) > 4096:
        return False

    return True


def ensure_output_directory(output_directory: str) -> bool:
    """Create output directory if it doesn't exist.

    Uses mkdir(parents=True, exist_ok=True) to safely create
    directory hierarchy.

    Args:
        output_directory: Directory path to create

    Returns:
        True if directory exists or was created successfully

    Raises:
        OSError: If directory creation fails

    Example:
        >>> ensure_output_directory("/tmp/test_output")
        True
    """
    output_dir = Path(output_directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    return True


def write_parameter_summary_csv(
    output_path: str,
    summaries: List[Dict[str, Any]],
    include_derived: bool,
    aggregation_level: CsvAggregationLevelType = "per_site",
) -> None:
    """Write test parameter summaries to CSV file.

    Uses csv.DictWriter for RFC 4180 compliant output with UTF-8 encoding.

    Args:
        output_path: Full path to output CSV file
        summaries: List of test parameter summary dictionaries
        include_derived: If True, include derived metric columns
        aggregation_level: CSV aggregation mode (Feature 011)

    Raises:
        OSError: If file cannot be written (permissions, disk full, etc.)

    Example:
        >>> summaries = [{"test_identification": {...}, ...}]
        >>> write_parameter_summary_csv("/tmp/output.csv", summaries, False)
    """
    # Define fieldnames based on aggregation mode
    if aggregation_level == "per_site":
        # Per-site mode: 14 base columns (includes Head/Site)
        fieldnames = [
            "Test_Name",
            "Test_Number",
            "Suite_Name",
            "Head_Number",
            "Site_Number",
            "Test_Count",
            "Fail_Count",
            "Min_Value",
            "Max_Value",
            "Mean_Value",
            "Std_Dev",
            "Low_Limit",
            "High_Limit",
            "Units",
        ]
    else:  # overall
        # Overall mode: 12 base columns (omits Head/Site)
        fieldnames = [
            "Test_Name",
            "Test_Number",
            "Suite_Name",
            "Test_Count",
            "Fail_Count",
            "Min_Value",
            "Max_Value",
            "Mean_Value",
            "Std_Dev",
            "Low_Limit",
            "High_Limit",
            "Units",
        ]

    # Add derived metric columns if requested (3 additional columns)
    if include_derived:
        fieldnames.extend(["Pass_Count", "Pass_Rate", "Fail_Rate"])

    # Transform summaries to CSV rows
    csv_rows = [
        transform_summary_to_csv_row(
            summary, include_derived, aggregation_level
        )
        for summary in summaries
    ]

    # Write CSV file
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(csv_rows)


def export_parameter_summary_csv(
    summaries: List[Dict[str, Any]],
    stdf_file_path: str,
    output_directory: str,
    include_derived: bool,
    aggregation_level: CsvAggregationLevelType = "per_site",
) -> Dict[str, Any]:
    """Orchestrate CSV export with error handling.

    Creates output directory, generates filename, transforms data,
    and writes CSV file. Returns success or error information.

    Args:
        summaries: List of test parameter summary dictionaries
        stdf_file_path: Path to original STDF file (for filename)
        output_directory: Directory for CSV output
        include_derived: If True, include derived metric columns
        aggregation_level: CSV aggregation mode (Feature 011)

    Returns:
        Success dict with csv_file_path, or error dict with
        error_code and error_message

    Error Codes:
        - INVALID_OUTPUT_PATH: Invalid or malformed path
        - CSV_DIR_CREATE_ERROR: Failed to create directory
        - CSV_PERMISSION_ERROR: Permission denied
        - CSV_DISK_FULL: Insufficient disk space

    Example:
        >>> result = export_parameter_summary_csv(
        ...     summaries, "/path/to/file.stdf", "TestCases/Output", False
        ... )
        >>> result["success"]
        True
        >>> result["csv_file_path"]
        '/absolute/path/to/TestCases/Output/file_TestParameterSummary_20251108_143022.csv'
    """
    # Step 1: Validate output directory path
    if not validate_output_path(output_directory):
        return {
            "success": False,
            "error_code": "INVALID_OUTPUT_PATH",
            "error_message": (
                f"Invalid output directory path: '{output_directory}'. "
                "Please provide a valid directory path."
            ),
        }

    try:
        # Step 2: Create output directory
        ensure_output_directory(output_directory)

    except OSError as e:
        return {
            "success": False,
            "error_code": "CSV_DIR_CREATE_ERROR",
            "error_message": (
                f"Failed to create output directory '{output_directory}': {str(e)}"
            ),
        }

    # Step 3: Generate CSV filename with timestamp
    stdf_path = Path(stdf_file_path)
    timestamp = datetime.now()
    filename = generate_csv_filename(stdf_path, timestamp)

    # Step 4: Build full output path
    output_dir = Path(output_directory)
    csv_path = output_dir / filename

    try:
        # Step 5: Write CSV file
        write_parameter_summary_csv(
            str(csv_path), summaries, include_derived, aggregation_level
        )

        # Step 6: Return success with absolute path
        return {
            "success": True,
            "csv_file_path": str(csv_path.absolute()),
        }

    except PermissionError:
        return {
            "success": False,
            "error_code": "CSV_PERMISSION_ERROR",
            "error_message": (
                f"Permission denied writing CSV to {output_directory}. "
                "Check directory permissions."
            ),
        }

    except OSError as e:
        # Check for disk full error
        import errno

        if e.errno == errno.ENOSPC:
            # Delete partial file on disk full
            if csv_path.exists():
                try:
                    csv_path.unlink()
                except Exception:
                    pass  # Best effort cleanup

            return {
                "success": False,
                "error_code": "CSV_DISK_FULL",
                "error_message": (
                    f"Insufficient disk space to write CSV to {output_directory}."
                ),
            }
        else:
            # Generic OSError
            return {
                "success": False,
                "error_code": "CSV_PERMISSION_ERROR",
                "error_message": (
                    f"Error writing CSV to {output_directory}: {str(e)}"
                ),
            }


def extract_test_parameter_summary(
    file_path: str,
    test_name: Optional[str] = None,
    use_regex: bool = False,
    include_derived_metrics: bool = True,
    result_limit: int = 1000,
    test_num: Optional[int] = None,
    test_num_start: Optional[int] = None,
    test_num_end: Optional[int] = None,
    test_suite_name: Optional[str] = None,
    is_suite_qualified: bool = False,
    export_csv: bool = False,
    output_directory: str = "TestCases/Output",
    csv_aggregation_level: CsvAggregationLevelType = "per_site",
) -> Dict[str, Any]:
    """Extract test parameter summary combining TSR statistics with PTR limits.

    This is the main entry point for test parameter summary extraction.
    Supports searching by test_name (exact or regex), test_num (single),
    test_num range, or test_suite_name (simple or qualified).

    Optionally exports results to CSV file for analysis in Excel or pandas.
    When CSV export is enabled, only CSV status is returned (no JSON summaries)
    to save LLM tokens.

    Examples:
        # Search by test name (exact)
        extract_test_parameter_summary(file, test_name="VDD_CORE")

        # Search by test name (regex pattern)
        extract_test_parameter_summary(file, test_name="VDD_.*", use_regex=True)

        # Search by single test_num
        extract_test_parameter_summary(file, test_num=1052)

        # Search by test_num range
        extract_test_parameter_summary(file, test_num_start=100, test_num_end=200)

        # Search by test suite (simple name)
        extract_test_parameter_summary(file, test_suite_name="Bt5gRxIp2")

        # Search by test suite (qualified name)
        extract_test_parameter_summary(file, test_suite_name="Main.RxIp2.Bt5gRxIp2",
                                       is_suite_qualified=True)

        # Export to CSV (Feature 010) - returns minimal response
        extract_test_parameter_summary(
            file, test_name="VDD_.*", use_regex=True,
            export_csv=True, output_directory="TestCases/Output"
        )

        # Export to CSV with overall aggregation (Feature 011) - 66% size reduction
        extract_test_parameter_summary(
            file, test_name="VDD_.*", use_regex=True,
            export_csv=True, csv_aggregation_level="overall"
        )

    Args:
        file_path: Absolute path to STDF V4 file
        test_name: Test parameter name (exact) or regex pattern (optional)
        use_regex: If True, treat test_name as regex pattern
        include_derived_metrics: If True, calculate derived metrics
        result_limit: Maximum number of summaries to return (1-10000)
        test_num: Single test number (optional, >= 0, <= 2^32-1)
        test_num_start: Range start test number (optional)
        test_num_end: Range end test number (optional)
        test_suite_name: Test suite name filter (simple or qualified, optional)
        is_suite_qualified: If True, treat test_suite_name as fully qualified path
        export_csv: If True, export to CSV and return minimal response (Feature 010)
        output_directory: Directory for CSV output (default: "TestCases/Output")
        csv_aggregation_level: CSV aggregation mode (Feature 011):
            - "per_site" (default): One row per test per site (14 columns with Head/Site)
            - "overall": One row per test aggregated across sites (12 columns, no Head/Site)
            Overall mode provides 60-70% file size reduction for multi-site files.

    Returns:
        When export_csv=False (default):
            Dictionary with test_parameter_pattern, match_type, matched_count,
            summaries (list of detailed test parameter data), and _metadata

        When export_csv=True AND CSV export succeeds:
            Dictionary with test_parameter_pattern, match_type, matched_count,
            csv_export (status/path), and minimal _metadata
            (summaries omitted to save LLM tokens - data is in CSV file)

        When export_csv=True AND CSV export fails:
            Dictionary with test_parameter_pattern, match_type, matched_count,
            summaries (list preserved for user access), csv_export (error info),
            and _metadata (graceful degradation - user still gets JSON data)

    Raises:
        FileNotFoundError: If file_path does not exist
        ValueError: If inputs are invalid or mutually exclusive filters provided
    """
    from stdf_mcp.stdf.parser import STDFV4Parser
    from stdf_mcp.stdf.records.summary_records import TSRRecord
    from stdf_mcp.stdf.records.test_records import PTRRecord

    # T024: Mutual exclusivity validation for test_suite_name
    active_filters = sum(
        [
            test_suite_name is not None,
            test_name is not None,
            test_num is not None,
            (test_num_start is not None or test_num_end is not None),
        ]
    )

    if active_filters > 1:
        raise ValueError(
            "test_suite_name, test_name, test_num, and test_num_start/end are mutually exclusive. "
            "Provide exactly one filter criterion."
        )

    if active_filters == 0:
        raise ValueError(
            "Must specify one filter: test_suite_name, test_name, test_num, or test_num range"
        )

    # Validate csv_aggregation_level (Feature 011 - VR-AGG-1)
    VALID_AGGREGATION_LEVELS = {"per_site", "overall"}
    if csv_aggregation_level not in VALID_AGGREGATION_LEVELS:
        raise ValueError(
            f"csv_aggregation_level must be one of {VALID_AGGREGATION_LEVELS}, "
            f"got '{csv_aggregation_level}'"
        )

    # Validate inputs (including test_num parameters)
    try:
        _validate_inputs(
            file_path,
            test_name,
            test_num,
            test_num_start,
            test_num_end,
            test_suite_name,
            use_regex,
            result_limit,
        )
    except FileNotFoundError as e:
        return _format_error_response("FileNotFound", str(e))
    except ValueError as e:
        if "regex" in str(e).lower():
            return _format_error_response("InvalidRegex", str(e))
        return _format_error_response("InvalidInput", str(e))

    # Parse STDF file
    parser = STDFV4Parser()
    tsr_records = []
    ptr_records = []

    try:
        for record in parser.parse_records(Path(file_path)):
            if isinstance(record, TSRRecord):
                tsr_records.append(record)
            elif isinstance(record, PTRRecord):
                ptr_records.append(record)
    except Exception as e:
        return _format_error_response(
            "InvalidFormat", f"Error parsing STDF file: {str(e)}"
        )

    # T025, T026, T027: Handle test suite filtering
    if test_suite_name:
        # Import hierarchy infrastructure
        from stdf_mcp.tools.filtered_data.hierarchy import HierarchyMap
        from stdf_mcp.tools.filtered_data.models import TestSuiteFilter

        # T027: Check for TSR presence
        if not tsr_records:
            return _format_error_response(
                "TestNotFound",
                "Test suite filtering requires TSR records, but none found in STDF file. "
                "Use test_name or test_num filtering instead.",
            )

        # Build HierarchyMap from TSR records
        hierarchy_map = HierarchyMap.from_tsr_records(tsr_records)

        # Create suite filter
        suite_filter = TestSuiteFilter(
            suite_name=test_suite_name,
            is_qualified=is_suite_qualified,
            case_sensitive=False,
        )

        # Get test numbers for matched suite(s)
        matched_test_nums = hierarchy_map.get_test_numbers_for_suite(
            suite_filter
        )

        # T027: Check if suite was found
        if not matched_test_nums:
            return _format_error_response(
                "TestNotFound",
                f"No matching test suite found for name '{test_suite_name}'. "
                f"Please verify the suite name exists in the STDF file.",
            )

        # Filter TSR records to only those in the matched test numbers
        filtered_tsr = [
            tsr for tsr in tsr_records if tsr.test_num in matched_test_nums
        ]

        # Apply result limit
        if len(filtered_tsr) > result_limit:
            filtered_tsr = filtered_tsr[:result_limit]

        # Use test_suite_name for search pattern
        search_pattern = f"test_suite_name='{test_suite_name}'"
        match_type = (
            "test_suite_qualified"
            if is_suite_qualified
            else "test_suite_simple"
        )
        pattern_value = test_suite_name

    else:
        # Original filtering logic for test_name/test_num
        # Filter TSR by criteria (test_name and/or test_num)
        # Create range tuple if both start and end provided
        test_num_range = None
        if test_num_start is not None and test_num_end is not None:
            test_num_range = (test_num_start, test_num_end)

        filtered_tsr = _filter_tsr(
            tsr_records,
            pattern=test_name,
            use_regex=use_regex,
            test_num=test_num,
            test_num_range=test_num_range,
        )

        # Determine search pattern for error message
        if test_num is not None:
            search_pattern = f"test_num={test_num}"
            match_type = "test_num"
            pattern_value = str(test_num)
        elif test_num_range is not None:
            search_pattern = f"test_num range {test_num_start}-{test_num_end}"
            match_type = "test_num_range"
            pattern_value = f"{test_num_start}-{test_num_end}"
        else:
            search_pattern = f"test_name='{test_name}'"
            match_type = "regex" if use_regex else "exact"
            pattern_value = test_name

        if not filtered_tsr:
            return _format_error_response(
                "TestNotFound", f"No tests found matching {search_pattern}"
            )

        # Apply result limit
        if len(filtered_tsr) > result_limit:
            filtered_tsr = filtered_tsr[:result_limit]

    # Group PTR by test_num
    ptr_by_test = _group_ptr_by_test_num(ptr_records)

    # Correlate TSR with PTR
    summaries = []
    for tsr in filtered_tsr:
        ptr_list = ptr_by_test.get(tsr.test_num, [])
        summary = _correlate_tsr_with_ptr(
            tsr, ptr_list, include_derived_metrics
        )
        summaries.append(summary)

    # Feature 011: Filter for overall mode (HEAD_NUM=255)
    # Per STDF V4 spec, HEAD_NUM=255 indicates overall aggregate across all sites
    summaries_for_csv = summaries
    if export_csv and csv_aggregation_level == "overall":
        summaries_for_csv = _filter_overall_summaries(summaries)

    # CSV Export (Feature 010: T014)
    # When CSV export enabled, attempt to generate CSV file
    if export_csv:
        csv_result = export_parameter_summary_csv(
            summaries=summaries_for_csv,
            stdf_file_path=file_path,
            output_directory=output_directory,
            include_derived=include_derived_metrics,
            aggregation_level=csv_aggregation_level,
        )

        # If CSV export succeeded, omit summaries to save LLM tokens
        if csv_result.get("success"):
            return {
                "test_parameter_pattern": pattern_value,
                "match_type": match_type,
                "matched_count": len(summaries),
                "csv_export": csv_result,
                "_metadata": {
                    "message": "Full results exported to CSV file. JSON output suppressed to save LLM tokens.",
                    "file_path": file_path,
                },
            }
        else:
            # CSV export failed - include summaries so user still gets data
            return {
                "test_parameter_pattern": pattern_value,
                "match_type": match_type,
                "matched_count": len(summaries),
                "summaries": summaries,  # Include because CSV failed
                "csv_export": csv_result,
                "_metadata": _create_metadata(
                    len(filtered_tsr),
                    sum(
                        1
                        for tsr in filtered_tsr
                        if tsr.test_num in ptr_by_test
                    ),
                    file_path,
                ),
            }

    # Format full JSON response (when CSV export disabled)
    return {
        "test_parameter_pattern": pattern_value,
        "match_type": match_type,
        "matched_count": len(summaries),
        "summaries": summaries,
        "_metadata": _create_metadata(
            len(filtered_tsr),
            sum(1 for tsr in filtered_tsr if tsr.test_num in ptr_by_test),
            file_path,
        ),
    }
