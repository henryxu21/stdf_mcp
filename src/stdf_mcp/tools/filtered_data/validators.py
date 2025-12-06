"""
Input Validators for Filtered Test Data Extraction.

This module provides validation functions for filter criteria, test numbers,
regex patterns, site numbers, and output directories.
"""

import re
from pathlib import Path
from typing import List, Optional, Pattern, Union


def validate_regex_pattern(pattern_str: str) -> Pattern[str]:
    """
    Validate and compile regex pattern for test name filtering.

    Args:
        pattern_str: Regex pattern string

    Returns:
        Compiled regex pattern

    Raises:
        ValueError: Invalid regex syntax
    """
    try:
        return re.compile(pattern_str)
    except re.error as e:
        raise ValueError(f"Invalid regex pattern '{pattern_str}': {e}") from e


def validate_test_num_input(test_num_input: List[Union[int, str]]) -> None:
    """
    Validate test_num input before creating TestNumFilter.

    This function performs preliminary validation. Full validation
    happens in TestNumFilter.from_input().

    Args:
        test_num_input: List of test numbers (int) or ranges (str)

    Raises:
        ValueError: Invalid input format or empty list
    """
    if not test_num_input:
        raise ValueError("test_num_input cannot be empty")

    if not isinstance(test_num_input, list):
        raise ValueError(
            f"test_num_input must be a list, got {type(test_num_input)}"
        )


def validate_site_numbers(site_filter: Optional[List[int]]) -> None:
    """
    Validate site numbers are within valid range.

    Args:
        site_filter: List of site numbers (0-255) or None for all sites

    Raises:
        ValueError: Site number out of range or invalid type
    """
    if site_filter is None:
        return  # None is valid (all sites)

    if not isinstance(site_filter, list):
        raise ValueError(
            f"site_filter must be a list or None, got {type(site_filter)}"
        )

    if not site_filter:
        raise ValueError(
            "site_filter cannot be empty list (use None for all sites)"
        )

    for site in site_filter:
        if not isinstance(site, int):
            raise ValueError(
                f"Site number must be integer, got {type(site)} for value {site}"
            )
        if not (0 <= site <= 255):
            raise ValueError(f"Site number {site} out of valid range 0-255")


def validate_output_directory(output_dir: Path) -> None:
    """
    Validate output directory path.

    Args:
        output_dir: Path to output directory

    Raises:
        ValueError: Invalid path (not absolute, doesn't exist, not writable)
    """
    if not isinstance(output_dir, Path):
        raise ValueError(
            f"output_directory must be Path object, got {type(output_dir)}"
        )

    if not output_dir.is_absolute():
        raise ValueError(
            f"Output directory must be absolute path: {output_dir}"
        )

    # Check if directory exists
    if not output_dir.exists():
        raise ValueError(f"Output directory does not exist: {output_dir}")

    # Check if it's actually a directory
    if not output_dir.is_dir():
        raise ValueError(f"Output path is not a directory: {output_dir}")

    # Check if writable (attempt to create a temporary file)
    test_file = output_dir / ".write_test"
    try:
        test_file.touch()
        test_file.unlink()  # Clean up
    except (PermissionError, OSError) as e:
        raise ValueError(f"Output directory not writable: {output_dir}") from e


def validate_filter_criteria(
    test_name_pattern: Optional[Pattern[str]],
    test_num_filter: Optional[object],
    site_filter: Optional[List[int]],
    output_directory: Path,
) -> None:
    """
    Validate complete filter criteria before creating FilterCriteria.

    This function performs cross-field validation. Individual field
    validation happens in FilterCriteria.__post_init__().

    Args:
        test_name_pattern: Compiled regex pattern or None
        test_num_filter: TestNumFilter object or None
        site_filter: List of site numbers or None
        output_directory: Path to output directory

    Raises:
        ValueError: Invalid combination of criteria
    """
    # Ensure exactly one test identifier specified
    if not test_name_pattern and not test_num_filter:
        raise ValueError(
            "Must specify either test_name_pattern or test_num_filter"
        )

    if test_name_pattern and test_num_filter:
        raise ValueError(
            "Cannot specify both test_name_pattern and test_num_filter"
        )

    # Validate individual fields
    if site_filter is not None:
        validate_site_numbers(site_filter)

    validate_output_directory(output_directory)
