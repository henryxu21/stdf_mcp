"""Input validation functions for test time extraction.

This module provides validation functions for user inputs to the
extract_test_time tool.
"""

from pathlib import Path
from typing import List, Optional


def validate_stdf_file_path(path: str) -> Path:
    """Validate STDF file path exists and is readable.

    Args:
        path: String path to STDF file

    Returns:
        Validated Path object

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If path is empty or not a file
    """
    if not path:
        raise ValueError("stdf_file_path cannot be empty")

    file_path = Path(path)

    if not file_path.exists():
        raise FileNotFoundError(f"STDF file not found: {path}")

    if not file_path.is_file():
        raise ValueError(f"Path is not a file: {path}")

    return file_path


def validate_site_numbers(site_list: Optional[List[int]]) -> None:
    """Validate site numbers are within valid STDF range.

    Args:
        site_list: Optional list of site numbers to validate

    Raises:
        ValueError: If any site number is outside valid range [0-255]
    """
    if site_list is None:
        return  # None means all sites, which is valid

    if not isinstance(site_list, list):
        raise ValueError(f"site_num must be a list, got {type(site_list)}")

    for site in site_list:
        if not isinstance(site, int):
            raise ValueError(
                f"site_num values must be integers, got {type(site)}"
            )
        if not 0 <= site <= 255:
            raise ValueError(
                f"Invalid site number: {site}. Must be in range [0-255]."
            )


def validate_output_directory(path: str) -> Path:
    """Validate output directory exists and is writable.

    Args:
        path: String path to output directory

    Returns:
        Validated Path object

    Raises:
        ValueError: If directory does not exist or is not writable
    """
    if not path:
        raise ValueError("output_directory cannot be empty")

    dir_path = Path(path)

    if not dir_path.exists():
        raise ValueError(
            f"Output directory does not exist: {path}"
        )

    if not dir_path.is_dir():
        raise ValueError(
            f"Output path is not a directory: {path}"
        )

    # Test writability by checking permissions
    if not dir_path.stat().st_mode & 0o200:  # Check write permission
        raise ValueError(
            f"Output directory is not writable: {path}"
        )

    return dir_path
