"""
Priority record field validation utilities.

This module provides validation utilities for enhanced fields extracted from
the 16 priority STDF record types. It ensures data integrity and consistency
for critical field values used in package test processing.

Priority Records Supported:
- FAR, MIR, MRR (File records)
- PIR, PRR (Part records)
- PTR, FTR (Test records)
- PCR, HBR, SBR, TSR (Summary records)
- BPS, DTR, GDR, RDR, SDR (Specialized records)
"""

import re
from typing import Any, Dict, List, Optional, Union, Tuple
from datetime import datetime
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of field validation operations."""

    is_valid: bool
    field_name: str
    field_value: Any
    validation_message: str = ""
    severity: str = "info"  # info, warning, error


class PriorityFieldValidator:
    """Validator for priority record fields with enhanced validation rules."""

    # Valid ranges for common field types
    VALID_RANGES = {
        'site_num': (0, 255),           # U1: 0-255
        'head_num': (0, 255),           # U1: 0-255
        'test_num': (0, 4294967295),    # U4: 0-4,294,967,295
        'hard_bin': (0, 65535),         # U2: 0-65,535
        'soft_bin': (0, 65535),         # U2: 0-65,535
        'part_count': (0, 4294967295),  # U4: 0-4,294,967,295
        'timestamp': (0, 4294967295),   # U4: 0-4,294,967,295 (Unix timestamp)
    }

    # Valid CPU types for Intel constraint
    VALID_CPU_TYPES = {1, 2}  # VAX (1) and Intel x86 (2) - both little-endian

    # Valid STDF versions
    VALID_STDF_VERSIONS = {4}  # Only V4 supported

    # Valid test flag patterns (common bit combinations)
    VALID_TEST_FLAGS = {
        0x00: "Pass, valid result",
        0x01: "Fail, valid result",
        0x02: "Pass, invalid result",
        0x03: "Fail, invalid result",
        0x04: "Pass, unreliable result",
        0x05: "Fail, unreliable result",
        0x08: "Pass, timeout occurred",
        0x09: "Fail, timeout occurred",
        0x10: "Pass, test not executed",
        0x11: "Fail, test not executed",
        0x20: "Pass, test aborted",
        0x21: "Fail, test aborted"
    }

    @classmethod
    def validate_numeric_range(cls, field_name: str, value: Union[int, float],
                             min_val: Optional[Union[int, float]] = None,
                             max_val: Optional[Union[int, float]] = None) -> ValidationResult:
        """
        Validate numeric field is within specified range.

        Args:
            field_name: Name of the field being validated
            value: Numeric value to validate
            min_val: Minimum allowed value (optional)
            max_val: Maximum allowed value (optional)

        Returns:
            ValidationResult: Validation result with details
        """
        if not isinstance(value, (int, float)):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=value,
                validation_message=f"Expected numeric value, got {type(value).__name__}",
                severity="error"
            )

        # Use predefined range if available
        if field_name in cls.VALID_RANGES and min_val is None and max_val is None:
            min_val, max_val = cls.VALID_RANGES[field_name]

        if min_val is not None and value < min_val:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=value,
                validation_message=f"Value {value} below minimum {min_val}",
                severity="error"
            )

        if max_val is not None and value > max_val:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=value,
                validation_message=f"Value {value} above maximum {max_val}",
                severity="error"
            )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            field_value=value,
            validation_message="Valid numeric value",
            severity="info"
        )

    @classmethod
    def validate_string_field(cls, field_name: str, value: str,
                             max_length: Optional[int] = None,
                             allow_empty: bool = True,
                             pattern: Optional[str] = None) -> ValidationResult:
        """
        Validate string field format and constraints.

        Args:
            field_name: Name of the field being validated
            value: String value to validate
            max_length: Maximum allowed length (optional)
            allow_empty: Whether empty strings are allowed
            pattern: Regular expression pattern to match (optional)

        Returns:
            ValidationResult: Validation result with details
        """
        if not isinstance(value, str):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=value,
                validation_message=f"Expected string value, got {type(value).__name__}",
                severity="error"
            )

        if not allow_empty and len(value) == 0:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=value,
                validation_message="Empty string not allowed",
                severity="error"
            )

        if max_length is not None and len(value) > max_length:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=value,
                validation_message=f"String length {len(value)} exceeds maximum {max_length}",
                severity="error"
            )

        # Check for non-ASCII characters (STDF uses ASCII encoding)
        try:
            value.encode('ascii')
        except UnicodeEncodeError:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=value,
                validation_message="String contains non-ASCII characters",
                severity="warning"
            )

        # Pattern validation
        if pattern is not None:
            if not re.match(pattern, value):
                return ValidationResult(
                    is_valid=False,
                    field_name=field_name,
                    field_value=value,
                    validation_message=f"String does not match required pattern: {pattern}",
                    severity="error"
                )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            field_value=value,
            validation_message="Valid string value",
            severity="info"
        )

    @classmethod
    def validate_timestamp(cls, field_name: str, timestamp: int) -> ValidationResult:
        """
        Validate STDF timestamp field.

        Args:
            field_name: Name of the timestamp field
            timestamp: Unix timestamp value (U4)

        Returns:
            ValidationResult: Validation result with details
        """
        # Basic numeric range check
        range_result = cls.validate_numeric_range(field_name, timestamp, 0, 4294967295)
        if not range_result.is_valid:
            return range_result

        # Zero timestamp is often valid (means not set)
        if timestamp == 0:
            return ValidationResult(
                is_valid=True,
                field_name=field_name,
                field_value=timestamp,
                validation_message="Zero timestamp (not set)",
                severity="info"
            )

        # Check if timestamp is reasonable (after 1990, before 2040)
        min_reasonable = 631152000   # 1990-01-01 00:00:00 UTC
        max_reasonable = 2209032000  # 2040-01-01 00:00:00 UTC

        if timestamp < min_reasonable:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=timestamp,
                validation_message=f"Timestamp {timestamp} appears too old (before 1990)",
                severity="warning"
            )

        if timestamp > max_reasonable:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=timestamp,
                validation_message=f"Timestamp {timestamp} appears too new (after 2040)",
                severity="warning"
            )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            field_value=timestamp,
            validation_message=f"Valid timestamp: {datetime.fromtimestamp(timestamp)}",
            severity="info"
        )

    @classmethod
    def validate_cpu_type(cls, cpu_type: int) -> ValidationResult:
        """
        Validate CPU type for Intel constraint compliance.

        Args:
            cpu_type: CPU type value from FAR record

        Returns:
            ValidationResult: Validation result with details
        """
        if cpu_type in cls.VALID_CPU_TYPES:
            cpu_names = {1: "VAX (little-endian)", 2: "Intel x86 (little-endian)"}
            return ValidationResult(
                is_valid=True,
                field_name="cpu_type",
                field_value=cpu_type,
                validation_message=f"Valid Intel-compatible CPU: {cpu_names[cpu_type]}",
                severity="info"
            )
        else:
            return ValidationResult(
                is_valid=False,
                field_name="cpu_type",
                field_value=cpu_type,
                validation_message=f"Unsupported CPU type {cpu_type}. Only Intel-compatible (1,2) supported.",
                severity="error"
            )

    @classmethod
    def validate_stdf_version(cls, stdf_version: int) -> ValidationResult:
        """
        Validate STDF version field.

        Args:
            stdf_version: STDF version value from FAR record

        Returns:
            ValidationResult: Validation result with details
        """
        if stdf_version in cls.VALID_STDF_VERSIONS:
            return ValidationResult(
                is_valid=True,
                field_name="stdf_version",
                field_value=stdf_version,
                validation_message=f"Valid STDF version: V{stdf_version}",
                severity="info"
            )
        else:
            return ValidationResult(
                is_valid=False,
                field_name="stdf_version",
                field_value=stdf_version,
                validation_message=f"Unsupported STDF version {stdf_version}. Only V4 supported.",
                severity="error"
            )

    @classmethod
    def validate_test_flags(cls, field_name: str, test_flags: int) -> ValidationResult:
        """
        Validate test flag field combinations.

        Args:
            field_name: Name of the test flag field
            test_flags: Test flag value (typically U1)

        Returns:
            ValidationResult: Validation result with details
        """
        # Check if it's a known flag combination
        if test_flags in cls.VALID_TEST_FLAGS:
            return ValidationResult(
                is_valid=True,
                field_name=field_name,
                field_value=test_flags,
                validation_message=f"Valid test flags: {cls.VALID_TEST_FLAGS[test_flags]}",
                severity="info"
            )

        # For unknown combinations, analyze individual bits
        flag_meanings = []
        if test_flags & 0x01: flag_meanings.append("Fail")
        else: flag_meanings.append("Pass")

        if test_flags & 0x02: flag_meanings.append("Invalid result")
        if test_flags & 0x04: flag_meanings.append("Unreliable result")
        if test_flags & 0x08: flag_meanings.append("Timeout occurred")
        if test_flags & 0x10: flag_meanings.append("Not executed")
        if test_flags & 0x20: flag_meanings.append("Aborted")
        if test_flags & 0x40: flag_meanings.append("Pass/Fail invalid")
        if test_flags & 0x80: flag_meanings.append("Result invalid")

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            field_value=test_flags,
            validation_message=f"Test flags (0x{test_flags:02X}): {', '.join(flag_meanings)}",
            severity="info"
        )

    @classmethod
    def validate_coordinate_pair(cls, x_coord: int, y_coord: int) -> ValidationResult:
        """
        Validate coordinate pair fields (typically from PRR record).

        Args:
            x_coord: X coordinate (signed I2)
            y_coord: Y coordinate (signed I2)

        Returns:
            ValidationResult: Validation result with details
        """
        # Check individual coordinate ranges (signed 16-bit)
        coord_min, coord_max = -32768, 32767

        for coord_name, coord_val in [("x_coord", x_coord), ("y_coord", y_coord)]:
            if not isinstance(coord_val, int):
                return ValidationResult(
                    is_valid=False,
                    field_name=coord_name,
                    field_value=coord_val,
                    validation_message=f"Expected integer coordinate, got {type(coord_val).__name__}",
                    severity="error"
                )

            if coord_val < coord_min or coord_val > coord_max:
                return ValidationResult(
                    is_valid=False,
                    field_name=coord_name,
                    field_value=coord_val,
                    validation_message=f"Coordinate {coord_val} out of range [{coord_min}, {coord_max}]",
                    severity="error"
                )

        return ValidationResult(
            is_valid=True,
            field_name="coordinates",
            field_value=(x_coord, y_coord),
            validation_message=f"Valid coordinate pair: ({x_coord}, {y_coord})",
            severity="info"
        )

    @classmethod
    def validate_binary_data(cls, field_name: str, binary_data: bytes,
                           max_length: Optional[int] = None) -> ValidationResult:
        """
        Validate binary data field.

        Args:
            field_name: Name of the binary field
            binary_data: Binary data to validate
            max_length: Maximum allowed length in bytes (optional)

        Returns:
            ValidationResult: Validation result with details
        """
        if not isinstance(binary_data, bytes):
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=binary_data,
                validation_message=f"Expected bytes, got {type(binary_data).__name__}",
                severity="error"
            )

        if max_length is not None and len(binary_data) > max_length:
            return ValidationResult(
                is_valid=False,
                field_name=field_name,
                field_value=binary_data,
                validation_message=f"Binary data length {len(binary_data)} exceeds maximum {max_length}",
                severity="error"
            )

        return ValidationResult(
            is_valid=True,
            field_name=field_name,
            field_value=binary_data,
            validation_message=f"Valid binary data: {len(binary_data)} bytes",
            severity="info"
        )

    @classmethod
    def validate_record_fields(cls, record_type: str, field_dict: Dict[str, Any]) -> List[ValidationResult]:
        """
        Validate all fields for a specific priority record type.

        Args:
            record_type: Type of record (e.g., "FAR", "MIR", "PRR", etc.)
            field_dict: Dictionary of field names to values

        Returns:
            List[ValidationResult]: List of validation results for all fields
        """
        results = []

        # Record-specific validation rules
        if record_type == "FAR":
            results.append(cls.validate_cpu_type(field_dict.get('cpu_type', 0)))
            results.append(cls.validate_stdf_version(field_dict.get('stdf_ver', 0)))

        elif record_type == "MIR":
            results.append(cls.validate_timestamp("setup_t", field_dict.get('setup_t', 0)))
            results.append(cls.validate_timestamp("start_t", field_dict.get('start_t', 0)))
            results.append(cls.validate_numeric_range("stat_num", field_dict.get('stat_num', 0)))

            # Validate string fields (30 fields)
            string_fields = ['lot_id', 'part_typ', 'node_nam', 'tstr_typ', 'job_nam', 'job_rev']
            for field_name in string_fields:
                if field_name in field_dict:
                    results.append(cls.validate_string_field(field_name, field_dict[field_name], max_length=255))

        elif record_type == "PRR":
            results.append(cls.validate_numeric_range("head_num", field_dict.get('head_num', 0)))
            results.append(cls.validate_numeric_range("site_num", field_dict.get('site_num', 0)))
            results.append(cls.validate_numeric_range("hard_bin", field_dict.get('hard_bin', 0)))
            results.append(cls.validate_coordinate_pair(
                field_dict.get('x_coord', 0),
                field_dict.get('y_coord', 0)
            ))
            results.append(cls.validate_timestamp("test_t", field_dict.get('test_t', 0)))
            results.append(cls.validate_binary_data("part_fix", field_dict.get('part_fix', b"")))

        elif record_type in ["PTR", "FTR"]:
            results.append(cls.validate_numeric_range("test_num", field_dict.get('test_num', 0)))
            results.append(cls.validate_numeric_range("head_num", field_dict.get('head_num', 0)))
            results.append(cls.validate_numeric_range("site_num", field_dict.get('site_num', 0)))
            results.append(cls.validate_test_flags("test_flg", field_dict.get('test_flg', 0)))

        # Common validations for all records
        for field_name, field_value in field_dict.items():
            if field_name.endswith('_num') and isinstance(field_value, int):
                results.append(cls.validate_numeric_range(field_name, field_value))
            elif field_name.endswith('_txt') and isinstance(field_value, str):
                results.append(cls.validate_string_field(field_name, field_value, max_length=255))

        return results


def validate_priority_record(record) -> List[ValidationResult]:
    """
    Convenience function to validate a complete priority record instance.

    Args:
        record: STDF record instance with enhanced field access

    Returns:
        List[ValidationResult]: List of validation results
    """
    if not hasattr(record, 'is_priority_record') or not record.is_priority_record:
        return [ValidationResult(
            is_valid=False,
            field_name="record_type",
            field_value=getattr(record, 'record_name', 'Unknown'),
            validation_message="Not a priority record",
            severity="error"
        )]

    # Get enhanced field dictionary
    if hasattr(record, 'get_enhanced_field_dict'):
        field_dict = record.get_enhanced_field_dict()
        record_name = getattr(record, 'record_name', 'Unknown')
        return PriorityFieldValidator.validate_record_fields(record_name, field_dict)
    else:
        return [ValidationResult(
            is_valid=False,
            field_name="enhanced_fields",
            field_value=None,
            validation_message="Record does not support enhanced field access",
            severity="error"
        )]


def get_validation_summary(validation_results: List[ValidationResult]) -> Dict[str, Any]:
    """
    Generate summary statistics from validation results.

    Args:
        validation_results: List of validation results

    Returns:
        Dict[str, Any]: Summary statistics
    """
    total_validations = len(validation_results)
    valid_count = sum(1 for r in validation_results if r.is_valid)
    error_count = sum(1 for r in validation_results if r.severity == "error")
    warning_count = sum(1 for r in validation_results if r.severity == "warning")

    return {
        'total_validations': total_validations,
        'valid_count': valid_count,
        'invalid_count': total_validations - valid_count,
        'error_count': error_count,
        'warning_count': warning_count,
        'success_rate': (valid_count / total_validations) * 100 if total_validations > 0 else 0,
        'validation_passed': error_count == 0
    }


# =============================================================================
# Phase 3 Utilities: T048-T050 - Enhanced Field Access and Parsing
# =============================================================================

# T048: Variable-length string parsing utilities
def parse_enhanced_variable_string(data: bytes, offset: int, encoding: str = 'ascii') -> Tuple[str, int]:
    """
    Parse variable-length string with enhanced encoding support and validation.

    Args:
        data: Raw bytes containing the string data
        offset: Starting offset in the data
        encoding: Character encoding to use (default: 'ascii')

    Returns:
        Tuple[str, int]: (parsed_string, new_offset)

    Raises:
        ValueError: If string parsing fails or data is invalid
    """
    if offset >= len(data):
        return "", offset

    # Get string length (first byte for STDF variable strings)
    if offset + 1 > len(data):
        raise ValueError(f"Insufficient data for string length at offset {offset}")

    str_length = data[offset]
    new_offset = offset + 1

    # Check if we have enough data for the string
    if new_offset + str_length > len(data):
        raise ValueError(f"Insufficient data for string of length {str_length} at offset {new_offset}")

    if str_length == 0:
        return "", new_offset

    # Extract string bytes
    string_bytes = data[new_offset:new_offset + str_length]
    new_offset += str_length

    # Decode with error handling
    try:
        decoded_string = string_bytes.decode(encoding, errors='replace')
        # Remove null terminators and clean whitespace
        decoded_string = decoded_string.rstrip('\x00').strip()
        return decoded_string, new_offset
    except (UnicodeDecodeError, LookupError) as e:
        # Fallback to latin-1 for binary-safe decoding
        decoded_string = string_bytes.decode('latin-1', errors='replace')
        decoded_string = decoded_string.rstrip('\x00').strip()
        return decoded_string, new_offset


def validate_string_encoding(string_data: str, required_encoding: str = 'ascii') -> bool:
    """
    Validate that string data conforms to required encoding.

    Args:
        string_data: String to validate
        required_encoding: Required encoding standard

    Returns:
        bool: True if string conforms to encoding
    """
    try:
        string_data.encode(required_encoding)
        return True
    except UnicodeEncodeError:
        return False


def normalize_stdf_string(string_data: str) -> str:
    """
    Normalize STDF string data for consistent processing.

    Args:
        string_data: Raw string data from STDF record

    Returns:
        str: Normalized string with consistent formatting
    """
    if not string_data:
        return ""

    # Remove null terminators and control characters
    normalized = ''.join(char for char in string_data if ord(char) >= 32 or char.isspace())

    # Normalize whitespace
    normalized = ' '.join(normalized.split())

    return normalized.strip()


# T049: Array field parsing utilities
def parse_array_field(data: bytes, offset: int, element_type: str, count: int) -> Tuple[List[Any], int]:
    """
    Parse array field with specified element type and count.

    Args:
        data: Raw bytes containing array data
        offset: Starting offset in the data
        element_type: Type of array elements ('U1', 'U2', 'U4', 'I1', 'I2', 'I4', 'R4', 'R8', 'Cn')
        count: Number of elements in the array

    Returns:
        Tuple[List[Any], int]: (parsed_array, new_offset)

    Raises:
        ValueError: If array parsing fails or data is invalid
    """
    if count == 0:
        return [], offset

    result = []
    current_offset = offset

    # Element size mapping for STDF data types
    element_sizes = {
        'U1': 1,   # 1-byte unsigned integer
        'U2': 2,   # 2-byte unsigned integer
        'U4': 4,   # 4-byte unsigned integer
        'I1': 1,   # 1-byte signed integer
        'I2': 2,   # 2-byte signed integer
        'I4': 4,   # 4-byte signed integer
        'R4': 4,   # 4-byte float
        'R8': 8,   # 8-byte float
    }

    if element_type in element_sizes:
        element_size = element_sizes[element_type]
        total_size = element_size * count

        if current_offset + total_size > len(data):
            raise ValueError(f"Insufficient data for array of {count} {element_type} elements")

        for i in range(count):
            element_data = data[current_offset:current_offset + element_size]

            if element_type.startswith('U'):  # Unsigned integers
                if element_size == 1:
                    value = element_data[0]
                elif element_size == 2:
                    value = int.from_bytes(element_data, byteorder='little', signed=False)
                else:  # element_size == 4
                    value = int.from_bytes(element_data, byteorder='little', signed=False)
            elif element_type.startswith('I'):  # Signed integers
                if element_size == 1:
                    value = int.from_bytes(element_data, byteorder='little', signed=True)
                elif element_size == 2:
                    value = int.from_bytes(element_data, byteorder='little', signed=True)
                else:  # element_size == 4
                    value = int.from_bytes(element_data, byteorder='little', signed=True)
            elif element_type == 'R4':  # 4-byte float
                import struct
                value = struct.unpack('<f', element_data)[0]
            elif element_type == 'R8':  # 8-byte float
                import struct
                value = struct.unpack('<d', element_data)[0]

            result.append(value)
            current_offset += element_size

    elif element_type.startswith('C'):  # Variable length string array
        for i in range(count):
            string_value, current_offset = parse_enhanced_variable_string(data, current_offset)
            result.append(string_value)
    else:
        raise ValueError(f"Unsupported array element type: {element_type}")

    return result, current_offset


def parse_variable_array(data: bytes, offset: int, element_type: str) -> Tuple[List[Any], int]:
    """
    Parse variable-count array where first element is the count.

    Args:
        data: Raw bytes containing array data
        offset: Starting offset in the data
        element_type: Type of array elements

    Returns:
        Tuple[List[Any], int]: (parsed_array, new_offset)
    """
    if offset >= len(data):
        return [], offset

    # First byte/element is the count
    if element_type in ['U1', 'I1']:
        count = data[offset]
        count_offset = offset + 1
    elif element_type in ['U2', 'I2']:
        if offset + 2 > len(data):
            raise ValueError("Insufficient data for array count")
        count = int.from_bytes(data[offset:offset + 2], byteorder='little', signed=False)
        count_offset = offset + 2
    else:
        raise ValueError(f"Unsupported count type for variable array: {element_type}")

    # Parse the actual array elements
    return parse_array_field(data, count_offset, element_type, count)


def validate_array_bounds(array_data: List[Any], expected_type: str, max_count: int = 65535) -> bool:
    """
    Validate array data bounds and type constraints.

    Args:
        array_data: Array data to validate
        expected_type: Expected element type
        max_count: Maximum allowed array count

    Returns:
        bool: True if array is valid
    """
    if len(array_data) > max_count:
        return False

    # Type-specific validation
    type_ranges = {
        'U1': (0, 255),
        'U2': (0, 65535),
        'U4': (0, 4294967295),
        'I1': (-128, 127),
        'I2': (-32768, 32767),
        'I4': (-2147483648, 2147483647)
    }

    if expected_type in type_ranges:
        min_val, max_val = type_ranges[expected_type]
        return all(isinstance(item, int) and min_val <= item <= max_val for item in array_data)

    return True  # No validation for other types


# T050: Generic data handling utilities
def parse_generic_binary_data(data: bytes, offset: int, length: int) -> Tuple[bytes, int]:
    """
    Parse generic binary data field with specified length.

    Args:
        data: Raw bytes containing binary data
        offset: Starting offset in the data
        length: Number of bytes to extract

    Returns:
        Tuple[bytes, int]: (binary_data, new_offset)

    Raises:
        ValueError: If insufficient data available
    """
    if offset + length > len(data):
        raise ValueError(f"Insufficient data: need {length} bytes at offset {offset}, only {len(data) - offset} available")

    binary_data = data[offset:offset + length]
    new_offset = offset + length

    return binary_data, new_offset


def convert_to_json_safe_type(value: Any) -> Any:
    """
    Convert STDF field values to JSON-serializable types.

    Args:
        value: Field value of any type

    Returns:
        Any: JSON-safe representation of the value
    """
    if value is None:
        return None

    # Handle bytes
    if isinstance(value, bytes):
        try:
            # Try to decode as UTF-8 first
            return value.decode('utf-8')
        except UnicodeDecodeError:
            # Fall back to hex representation for binary data
            return value.hex()

    # Handle numpy types and other numeric types
    if hasattr(value, 'item'):  # numpy scalar
        return value.item()

    # Handle lists and tuples
    if isinstance(value, (list, tuple)):
        return [convert_to_json_safe_type(item) for item in value]

    # Handle dictionaries
    if isinstance(value, dict):
        return {str(k): convert_to_json_safe_type(v) for k, v in value.items()}

    # Handle standard types
    if isinstance(value, (int, float, str, bool)):
        return value

    # Convert unknown types to string representation
    return str(value)


def validate_field_data_integrity(field_name: str, field_value: Any, expected_type: str) -> ValidationResult:
    """
    Validate field data integrity and type compliance.

    Args:
        field_name: Name of the field being validated
        field_value: Value to validate
        expected_type: Expected STDF data type

    Returns:
        ValidationResult: Validation result with details
    """
    # Type mapping for validation
    type_validators = {
        'U1': lambda v: isinstance(v, int) and 0 <= v <= 255,
        'U2': lambda v: isinstance(v, int) and 0 <= v <= 65535,
        'U4': lambda v: isinstance(v, int) and 0 <= v <= 4294967295,
        'I1': lambda v: isinstance(v, int) and -128 <= v <= 127,
        'I2': lambda v: isinstance(v, int) and -32768 <= v <= 32767,
        'I4': lambda v: isinstance(v, int) and -2147483648 <= v <= 2147483647,
        'R4': lambda v: isinstance(v, (int, float)),
        'R8': lambda v: isinstance(v, (int, float)),
        'C1': lambda v: isinstance(v, str),
        'Cn': lambda v: isinstance(v, str),
        'B1': lambda v: isinstance(v, bytes),
        'Bn': lambda v: isinstance(v, bytes),
        'xU1': lambda v: isinstance(v, list) and all(isinstance(x, int) and 0 <= x <= 255 for x in v),
        'xU2': lambda v: isinstance(v, list) and all(isinstance(x, int) and 0 <= x <= 65535 for x in v),
    }

    validator = type_validators.get(expected_type)
    if validator is None:
        return ValidationResult(
            is_valid=True,  # Unknown type, assume valid
            field_name=field_name,
            field_value=field_value,
            validation_message=f"No validator available for type {expected_type}",
            severity="warning"
        )

    is_valid = validator(field_value)

    return ValidationResult(
        is_valid=is_valid,
        field_name=field_name,
        field_value=field_value,
        validation_message="Field data is valid" if is_valid else f"Field data does not match expected type {expected_type}",
        severity="info" if is_valid else "error"
    )