"""
Validation and error handling for metadata extraction tools.

This module provides comprehensive validation and error handling capabilities
for all 6 metadata extraction tools in User Story 1.

Features:
- Input validation for file paths and parameters
- Intel CPU little-endian constraint validation
- Output schema validation
- Comprehensive error handling and reporting
- Performance monitoring and timeout handling
"""

import os
import sys
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Union, Callable
from functools import wraps
import jsonschema

# Add src to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from stdf_mcp.stdf.exceptions import *


class ValidationError(Exception):
    """Custom validation error for metadata tools."""

    def __init__(self, message: str, tool_name: str = None, validation_type: str = None):
        self.tool_name = tool_name
        self.validation_type = validation_type
        super().__init__(message)


class MetadataToolValidator:
    """Comprehensive validator for metadata extraction tools."""

    def __init__(self):
        """Initialize validator with schema definitions."""
        self.schemas = self._load_validation_schemas()
        self.performance_thresholds = {
            "extract_file_overview": 5.0,  # 5 seconds max
            "extract_test_configuration": 3.0,
            "extract_yield_summary": 4.0,
            "extract_facility_details": 2.0,
            "extract_program_metadata": 2.0,
            "extract_test_parameters": 10.0  # Longer for parameter extraction
        }

    def validate_file_path(self, file_path: str, tool_name: str = None) -> Path:
        """
        Validate STDF file path input.

        Args:
            file_path: File path to validate
            tool_name: Name of calling tool (for error context)

        Returns:
            Validated Path object

        Raises:
            ValidationError: If file path is invalid
        """
        if not file_path:
            raise ValidationError("File path cannot be empty", tool_name, "input")

        if not isinstance(file_path, str):
            raise ValidationError(f"File path must be string, got {type(file_path)}", tool_name, "input")

        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            raise ValidationError(f"File does not exist: {file_path}", tool_name, "input")

        if not file_path_obj.is_file():
            raise ValidationError(f"Path is not a file: {file_path}", tool_name, "input")

        # Check file size (basic validation)
        file_size = file_path_obj.stat().st_size
        if file_size == 0:
            raise ValidationError(f"File is empty: {file_path}", tool_name, "input")

        if file_size > 2 * 1024 * 1024 * 1024:  # 2GB limit
            raise ValidationError(f"File too large (>2GB): {file_path}", tool_name, "input")

        # Check file extension (optional but helpful)
        if file_path_obj.suffix.lower() not in ['.stdf', '.std', '']:
            # Warning only, don't fail on extension
            pass

        return file_path_obj

    def validate_filter_option(self, filter_option: str, tool_name: str = None) -> str:
        """
        Validate filter option for extract_test_parameters.

        Args:
            filter_option: Filter option to validate
            tool_name: Name of calling tool (for error context)

        Returns:
            Validated filter option

        Raises:
            ValidationError: If filter option is invalid
        """
        valid_filters = ["all_parameters", "with_limits_only", "without_limits_only"]

        if not isinstance(filter_option, str):
            raise ValidationError(f"Filter option must be string, got {type(filter_option)}", tool_name, "input")

        if filter_option not in valid_filters:
            raise ValidationError(
                f"Invalid filter option: {filter_option}. Must be one of {valid_filters}",
                tool_name, "input"
            )

        return filter_option

    def validate_output_schema(self, output_data: Dict[str, Any], tool_name: str) -> bool:
        """
        Validate tool output against expected schema.

        Args:
            output_data: Tool output to validate
            tool_name: Name of tool that produced output

        Returns:
            True if validation passes

        Raises:
            ValidationError: If output schema is invalid
        """
        if tool_name not in self.schemas:
            # Skip validation if no schema defined
            return True

        try:
            jsonschema.validate(instance=output_data, schema=self.schemas[tool_name])
            return True
        except jsonschema.ValidationError as e:
            raise ValidationError(
                f"Output schema validation failed: {e.message}",
                tool_name, "output"
            )
        except Exception as e:
            raise ValidationError(
                f"Schema validation error: {str(e)}",
                tool_name, "output"
            )

    def validate_intel_cpu_constraint(self, output_data: Dict[str, Any], tool_name: str) -> bool:
        """
        Validate Intel CPU little-endian constraint in output.

        Args:
            output_data: Tool output to validate
            tool_name: Name of tool that produced output

        Returns:
            True if constraint is satisfied

        Raises:
            ValidationError: If constraint is violated
        """
        # Check for CPU type information in file_info
        if "file_info" in output_data:
            cpu_type = output_data["file_info"].get("cpu_type")
            if cpu_type and cpu_type != "little":
                raise ValidationError(
                    f"Intel CPU constraint violated: found {cpu_type}, expected little_endian",
                    tool_name, "constraint"
                )

        # Check for endianness information
        if "_metadata" in output_data:
            endianness = output_data["_metadata"].get("endianness")
            if endianness and endianness != "little":
                raise ValidationError(
                    f"Intel CPU constraint violated: found {endianness} endian",
                    tool_name, "constraint"
                )

        return True

    def validate_performance(self, execution_time: float, tool_name: str) -> bool:
        """
        Validate tool performance against thresholds.

        Args:
            execution_time: Tool execution time in seconds
            tool_name: Name of tool

        Returns:
            True if performance is acceptable

        Raises:
            ValidationError: If performance threshold is exceeded
        """
        threshold = self.performance_thresholds.get(tool_name, 5.0)

        if execution_time > threshold:
            raise ValidationError(
                f"Performance threshold exceeded: {execution_time:.2f}s > {threshold}s",
                tool_name, "performance"
            )

        return True

    def _load_validation_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Load JSON schemas for output validation."""
        return {
            "extract_file_overview": {
                "type": "object",
                "required": ["file_info", "key_identifiers", "summary_statistics"],
                "properties": {
                    "file_info": {"type": "object"},
                    "key_identifiers": {"type": "object"},
                    "summary_statistics": {"type": "object"},
                    "_metadata": {"type": "object"}
                }
            },
            "extract_test_configuration": {
                "type": "object",
                "required": ["test_conditions", "hardware_configuration", "site_descriptions"],
                "properties": {
                    "test_conditions": {"type": "object"},
                    "hardware_configuration": {"type": "object"},
                    "site_descriptions": {"type": "array"},
                    "_metadata": {"type": "object"}
                }
            },
            "extract_yield_summary": {
                "type": "object",
                "required": ["part_count_records", "retest_information", "computed_statistics"],
                "properties": {
                    "part_count_records": {"type": "array"},
                    "retest_information": {"type": "object"},
                    "computed_statistics": {"type": "object"},
                    "_metadata": {"type": "object"}
                }
            },
            "extract_facility_details": {
                "type": "object",
                "required": ["location_information", "process_information", "engineering_context", "timing_information"],
                "properties": {
                    "location_information": {"type": "object"},
                    "process_information": {"type": "object"},
                    "engineering_context": {"type": "object"},
                    "timing_information": {"type": "object"},
                    "_metadata": {"type": "object"}
                }
            },
            "extract_program_metadata": {
                "type": "object",
                "required": ["program_identification", "specifications", "tester_software", "user_context"],
                "properties": {
                    "program_identification": {"type": "object"},
                    "specifications": {"type": "object"},
                    "tester_software": {"type": "object"},
                    "user_context": {"type": "object"},
                    "_metadata": {"type": "object"}
                }
            },
            "extract_test_parameters": {
                "type": "object",
                "required": ["parameters_with_limits", "parameters_without_limits", "total_parameter_count", "filter_option"],
                "properties": {
                    "parameters_with_limits": {"type": "array"},
                    "parameters_without_limits": {"type": "array"},
                    "total_parameter_count": {"type": "integer", "minimum": 0},
                    "parametric_test_count": {"type": "integer", "minimum": 0},
                    "functional_test_count": {"type": "integer", "minimum": 0},
                    "filter_option": {"type": "string"},
                    "_metadata": {"type": "object"}
                }
            }
        }


# Global validator instance
_validator = MetadataToolValidator()


def validate_metadata_tool(tool_name: str):
    """
    Decorator to add comprehensive validation to metadata tools.

    Args:
        tool_name: Name of the tool being validated

    Returns:
        Decorated function with validation
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()

            try:
                # Validate inputs
                if args:
                    file_path = args[0]
                    _validator.validate_file_path(file_path, tool_name)

                # Special validation for extract_test_parameters
                if tool_name == "extract_test_parameters":
                    filter_option = kwargs.get("filter_option", "all_parameters")
                    if len(args) > 1:
                        filter_option = args[1]
                    _validator.validate_filter_option(filter_option, tool_name)

                # Execute tool
                result = func(*args, **kwargs)

                # Validate output
                _validator.validate_output_schema(result, tool_name)
                _validator.validate_intel_cpu_constraint(result, tool_name)

                # Validate performance
                execution_time = time.time() - start_time
                _validator.validate_performance(execution_time, tool_name)

                # Add validation metadata
                if "_metadata" not in result:
                    result["_metadata"] = {}

                result["_metadata"]["validation"] = {
                    "input_validated": True,
                    "output_validated": True,
                    "constraint_validated": True,
                    "performance_validated": True,
                    "execution_time": execution_time,
                    "validator_version": "1.0.0"
                }

                return result

            except ValidationError:
                # Re-raise validation errors as-is
                raise
            except (UnsupportedCPUArchitectureError, UnsupportedSTDFVersionError,
                   UnsupportedTestScopeError, InvalidSTDFFormatError) as e:
                # Re-raise STDF-specific errors as-is
                raise
            except Exception as e:
                # Wrap other errors in ValidationError
                raise ValidationError(
                    f"Unexpected error in tool execution: {str(e)}",
                    tool_name, "execution"
                ) from e

        return wrapper
    return decorator


def get_validation_report(error: Exception) -> Dict[str, Any]:
    """
    Generate a validation report from an error.

    Args:
        error: Exception that occurred

    Returns:
        Validation report dict
    """
    report = {
        "validation_status": "FAILED",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "timestamp": time.time()
    }

    if isinstance(error, ValidationError):
        report["tool_name"] = error.tool_name
        report["validation_type"] = error.validation_type

    return report


# Export public interface
__all__ = [
    "ValidationError",
    "MetadataToolValidator",
    "validate_metadata_tool",
    "get_validation_report"
]