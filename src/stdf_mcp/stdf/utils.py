"""
Utility functions and helpers for STDF-V4 processing.

This module provides common utility functions, formatters,
and helpers used throughout the STDF MCP server implementation.
"""

import os
import json
from typing import Any, Dict, List, Optional, Union
from pathlib import Path
from datetime import datetime


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human-readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"


def format_duration(milliseconds: int) -> str:
    """
    Format duration in human-readable format.

    Args:
        milliseconds: Duration in milliseconds

    Returns:
        str: Formatted duration string
    """
    if milliseconds < 1000:
        return f"{milliseconds} ms"
    elif milliseconds < 60000:
        return f"{milliseconds / 1000:.1f} s"
    else:
        minutes = milliseconds // 60000
        seconds = (milliseconds % 60000) / 1000
        return f"{minutes}m {seconds:.1f}s"


def format_percentage(value: float, decimal_places: int = 1) -> str:
    """
    Format percentage value.

    Args:
        value: Percentage value (0-100)
        decimal_places: Number of decimal places

    Returns:
        str: Formatted percentage string
    """
    return f"{value:.{decimal_places}f}%"


def format_test_result(result_value: Optional[float],
                      units: Optional[str] = None,
                      decimal_places: int = 3) -> str:
    """
    Format test result value with units.

    Args:
        result_value: Test result value
        units: Measurement units
        decimal_places: Number of decimal places

    Returns:
        str: Formatted result string
    """
    if result_value is None:
        return "N/A"

    formatted_value = f"{result_value:.{decimal_places}f}"
    if units:
        return f"{formatted_value} {units}"
    else:
        return formatted_value


def safe_json_serialize(obj: Any) -> str:
    """
    Safely serialize object to JSON with datetime handling.

    Args:
        obj: Object to serialize

    Returns:
        str: JSON string
    """
    def json_serializer(o):
        if isinstance(o, datetime):
            return o.isoformat()
        elif isinstance(o, Path):
            return str(o)
        elif hasattr(o, '__dict__'):
            return o.__dict__
        else:
            return str(o)

    return json.dumps(obj, default=json_serializer, indent=2)


def validate_file_path(file_path: Union[str, Path]) -> Path:
    """
    Validate and normalize file path.

    Args:
        file_path: Path to validate

    Returns:
        Path: Validated path object

    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If path is invalid
    """
    if isinstance(file_path, str):
        path = Path(file_path)
    else:
        path = file_path

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    return path.resolve()


def create_output_filename(base_name: str,
                          feature: str,
                          suffix: str = "csv",
                          include_timestamp: bool = True) -> str:
    """
    Create output filename following naming convention.

    Args:
        base_name: Base filename (without extension)
        feature: Feature name
        suffix: File suffix/extension
        include_timestamp: Include timestamp in filename

    Returns:
        str: Generated filename

    Note:
        Follows pattern: <STDF_file_name>_<Feature>_<TimeStamp>.<suffix>
    """
    # Clean base name
    clean_base = base_name.replace('.stdf', '').replace('.STDF', '')

    # Build filename
    parts = [clean_base, feature]

    if include_timestamp:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        parts.append(timestamp)

    filename = "_".join(parts) + f".{suffix}"
    return filename


def ensure_output_directory(output_dir: Union[str, Path]) -> Path:
    """
    Ensure output directory exists.

    Args:
        output_dir: Output directory path

    Returns:
        Path: Validated directory path
    """
    if isinstance(output_dir, str):
        dir_path = Path(output_dir)
    else:
        dir_path = output_dir

    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_testcases_output_dir() -> Path:
    """
    Get TestCases/Output directory path.

    Returns:
        Path: TestCases/Output directory path
    """
    # Assume we're in the project root or can find it
    current_dir = Path.cwd()

    # Look for TestCases directory
    while current_dir != current_dir.parent:
        testcases_dir = current_dir / "TestCases"
        if testcases_dir.exists():
            output_dir = testcases_dir / "Output"
            ensure_output_directory(output_dir)
            return output_dir
        current_dir = current_dir.parent

    # Fallback to current directory
    fallback_dir = Path.cwd() / "output"
    ensure_output_directory(fallback_dir)
    return fallback_dir


def calculate_yield_confidence_interval(passes: int, total: int,
                                       confidence_level: float = 0.95) -> tuple:
    """
    Calculate confidence interval for yield.

    Args:
        passes: Number of passing parts
        total: Total number of parts
        confidence_level: Confidence level (0.0-1.0)

    Returns:
        tuple: (lower_bound, upper_bound) as percentages
    """
    if total == 0:
        return (0.0, 0.0)

    import math

    p = passes / total
    z_score = 1.96 if confidence_level == 0.95 else 2.576  # 95% or 99%

    # Wilson score interval (more accurate for small samples)
    denominator = 1 + (z_score ** 2) / total
    center = (p + (z_score ** 2) / (2 * total)) / denominator
    margin = z_score * math.sqrt((p * (1 - p) + (z_score ** 2) / (4 * total)) / total) / denominator

    lower = max(0.0, (center - margin) * 100.0)
    upper = min(100.0, (center + margin) * 100.0)

    return (lower, upper)


def classify_cpk_value(cpk: Optional[float]) -> str:
    """
    Classify Cpk value into performance categories.

    Args:
        cpk: Process capability index

    Returns:
        str: Performance classification
    """
    if cpk is None:
        return "Unknown"
    elif cpk >= 2.0:
        return "Excellent"
    elif cpk >= 1.67:
        return "Very Good"
    elif cpk >= 1.33:
        return "Good"
    elif cpk >= 1.0:
        return "Adequate"
    else:
        return "Poor"


def format_statistical_summary(stats_dict: Dict[str, Any]) -> str:
    """
    Format statistical summary for display.

    Args:
        stats_dict: Dictionary containing statistical values

    Returns:
        str: Formatted summary
    """
    lines = []

    if 'count' in stats_dict:
        lines.append(f"Count: {stats_dict['count']}")

    if 'mean' in stats_dict and 'std_dev' in stats_dict:
        lines.append(f"Mean ± StdDev: {stats_dict['mean']:.3f} ± {stats_dict['std_dev']:.3f}")

    if 'min_value' in stats_dict and 'max_value' in stats_dict:
        lines.append(f"Range: {stats_dict['min_value']:.3f} to {stats_dict['max_value']:.3f}")

    if 'median' in stats_dict:
        lines.append(f"Median: {stats_dict['median']:.3f}")

    if 'skewness' in stats_dict and 'kurtosis' in stats_dict:
        lines.append(f"Skewness: {stats_dict['skewness']:.2f}, Kurtosis: {stats_dict['kurtosis']:.2f}")

    return "\n".join(lines)


def validate_test_limits(low_limit: Optional[float],
                        high_limit: Optional[float],
                        result_value: Optional[float]) -> Dict[str, Any]:
    """
    Validate test result against limits.

    Args:
        low_limit: Lower specification limit
        high_limit: Upper specification limit
        result_value: Test result value

    Returns:
        Dict[str, Any]: Validation results
    """
    if result_value is None:
        return {
            'within_limits': False,
            'violation_type': 'No Result',
            'margin': None
        }

    violations = []
    margins = []

    if low_limit is not None and result_value < low_limit:
        violations.append('Below Low Limit')
        margins.append(result_value - low_limit)

    if high_limit is not None and result_value > high_limit:
        violations.append('Above High Limit')
        margins.append(high_limit - result_value)

    within_limits = len(violations) == 0

    # Calculate margin to nearest limit
    margin = None
    if low_limit is not None and high_limit is not None:
        margin = min(result_value - low_limit, high_limit - result_value)
    elif low_limit is not None:
        margin = result_value - low_limit
    elif high_limit is not None:
        margin = high_limit - result_value

    return {
        'within_limits': within_limits,
        'violation_type': ', '.join(violations) if violations else None,
        'margin': margin
    }


def generate_summary_report(stdf_data, include_statistics: bool = True) -> str:
    """
    Generate human-readable summary report.

    Args:
        stdf_data: STDFData structure
        include_statistics: Include detailed statistics

    Returns:
        str: Formatted summary report
    """
    lines = []

    # File information
    lines.append("STDF File Summary")
    lines.append("=" * 50)
    lines.append(f"File: {stdf_data.file_metadata.file_path}")
    lines.append(f"Size: {format_file_size(stdf_data.file_metadata.file_size)}")
    lines.append(f"Version: {stdf_data.file_metadata.stdf_version}")
    lines.append(f"Records: {stdf_data.file_metadata.record_count}")
    lines.append("")

    # Lot information
    lines.append("Lot Information")
    lines.append("-" * 20)
    lines.append(f"Lot ID: {stdf_data.lot_summary.lot_id or 'Unknown'}")
    lines.append(f"Part Type: {stdf_data.lot_summary.part_type or 'Unknown'}")
    lines.append(f"Test Program: {stdf_data.lot_summary.test_program or 'Unknown'}")
    lines.append("")

    # Yield summary
    lines.append("Yield Summary")
    lines.append("-" * 15)
    lines.append(f"Total Parts: {stdf_data.lot_summary.total_parts}")
    lines.append(f"Passing Parts: {stdf_data.lot_summary.passing_parts}")
    lines.append(f"Failing Parts: {stdf_data.lot_summary.failing_parts}")
    lines.append(f"Overall Yield: {format_percentage(stdf_data.lot_summary.yield_percent)}")
    lines.append("")

    # Test summary
    lines.append("Test Summary")
    lines.append("-" * 12)
    lines.append(f"Unique Tests: {len(stdf_data.test_definitions)}")
    lines.append(f"Test Sites: {len(stdf_data.test_sites)}")
    lines.append(f"Hard Bins: {len(stdf_data.hard_bins)}")
    lines.append("")

    if include_statistics:
        # Top failing tests
        failing_tests = []
        for test_num, test_def in stdf_data.test_definitions.items():
            if test_def.execution_count > 0:
                failure_rate = (test_def.failure_count / test_def.execution_count) * 100.0
                if failure_rate > 0:
                    failing_tests.append((test_def.test_name or f"Test {test_num}",
                                        failure_rate, test_def.failure_count))

        if failing_tests:
            failing_tests.sort(key=lambda x: x[1], reverse=True)
            lines.append("Top Failing Tests")
            lines.append("-" * 17)
            for name, rate, count in failing_tests[:5]:
                lines.append(f"{name}: {format_percentage(rate)} ({count} failures)")
            lines.append("")

    return "\n".join(lines)