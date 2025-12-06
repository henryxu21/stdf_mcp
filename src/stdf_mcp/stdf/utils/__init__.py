"""
STDF utilities package initialization.

This module provides utility functions and classes for STDF data processing,
validation, and analysis.
"""

from .field_parsers import (
    ValidationResult,
    PriorityFieldValidator,
    validate_priority_record,
    get_validation_summary,
    # T048: Variable-length string parsing utilities
    parse_enhanced_variable_string,
    validate_string_encoding,
    normalize_stdf_string,
    # T049: Array field parsing utilities
    parse_array_field,
    parse_variable_array,
    validate_array_bounds,
    # T050: Generic data handling utilities
    parse_generic_binary_data,
    convert_to_json_safe_type,
    validate_field_data_integrity
)

__all__ = [
    'ValidationResult',
    'PriorityFieldValidator',
    'validate_priority_record',
    'get_validation_summary',
    # T048: Variable-length string parsing utilities
    'parse_enhanced_variable_string',
    'validate_string_encoding',
    'normalize_stdf_string',
    # T049: Array field parsing utilities
    'parse_array_field',
    'parse_variable_array',
    'validate_array_bounds',
    # T050: Generic data handling utilities
    'parse_generic_binary_data',
    'convert_to_json_safe_type',
    'validate_field_data_integrity'
]