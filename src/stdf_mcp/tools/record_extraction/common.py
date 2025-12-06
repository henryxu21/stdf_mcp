"""
Common utilities for STDF record extraction.

This module provides shared validation and normalization functions
used by all record extraction tools.
"""

import os
import struct
from typing import Set


# Supported STDF overview record types
SUPPORTED_RECORD_TYPES: Set[str] = {"FAR", "MIR", "HBR", "SBR", "PCR", "SDR", "MRR"}


def normalize_record_type(record_type: str) -> str:
    """
    Normalize record type string to uppercase and validate support.

    Converts the input record type to uppercase, strips whitespace,
    and validates that it's a supported overview record type.

    Args:
        record_type: Record type identifier (case-insensitive)

    Returns:
        Normalized record type in uppercase (e.g., "FAR", "MIR")

    Raises:
        ValueError: If record_type is not a supported overview record type

    Examples:
        >>> normalize_record_type("far")
        'FAR'
        >>> normalize_record_type("MIR")
        'MIR'
        >>> normalize_record_type(" hbr ")
        'HBR'
        >>> normalize_record_type("PTR")  # doctest: +SKIP
        Traceback (most recent call last):
            ...
        ValueError: Unsupported record type: PTR. Supported types: ...
    """
    normalized = record_type.upper().strip()

    if normalized not in SUPPORTED_RECORD_TYPES:
        supported_list = ", ".join(sorted(SUPPORTED_RECORD_TYPES))
        raise ValueError(
            f"Unsupported record type: {record_type}. "
            f"Supported types: {supported_list}"
        )

    return normalized


def validate_stdf_file(file_path: str) -> None:
    """
    Validate that a file exists and is a valid STDF V4 file.

    Checks that:
    1. File exists at the specified path
    2. Path points to a file (not a directory)
    3. File is not empty
    4. File starts with a valid FAR record (type=0, subtype=10)

    Args:
        file_path: Absolute path to STDF file

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If path is not a file, file is empty, or invalid STDF format

    Examples:
        >>> validate_stdf_file("/path/to/valid.stdf")  # doctest: +SKIP
        >>> validate_stdf_file("/nonexistent.stdf")  # doctest: +SKIP
        Traceback (most recent call last):
            ...
        FileNotFoundError: File not found: /nonexistent.stdf
    """
    # Check file existence
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # Check that path is a file
    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {file_path}")

    # Check file is not empty and has valid FAR record
    try:
        with open(file_path, "rb") as f:
            # Read first record header (4 bytes: length + type + subtype)
            header = f.read(4)

            if len(header) < 4:
                raise ValueError(
                    f"Invalid STDF file format: File too short "
                    f"(expected at least 4 bytes, got {len(header)})"
                )

            # Parse record header (little-endian)
            record_len, record_type, record_subtype = struct.unpack(
                "<HBB", header
            )

            # Validate FAR record (type=0, subtype=10)
            if record_type != 0 or record_subtype != 10:
                raise ValueError(
                    f"Invalid STDF file format: Expected FAR record "
                    f"(type=0, subtype=10) at start, found "
                    f"type={record_type}, subtype={record_subtype}"
                )

    except struct.error as e:
        raise ValueError(
            f"Invalid STDF file format: Failed to parse record header - {e}"
        )
    except IOError as e:
        raise ValueError(f"Invalid STDF file format: I/O error - {e}")
