"""
Logging configuration and utilities for metadata extraction operations.

This module provides comprehensive logging capabilities for all metadata
extraction tools with structured logging, performance tracking, and audit trails.

Features:
- Structured logging with JSON output
- Performance metrics tracking
- Audit trail for Intel CPU constraint enforcement
- Tool-specific log contexts
- Configurable log levels and outputs
"""

import logging
import json
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Union
from functools import wraps
import traceback

# Configure logging format for metadata tools
METADATA_LOG_FORMAT = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S"
        },
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "detailed",
            "stream": "ext://sys.stdout"
        },
        "file": {
            "class": "logging.FileHandler",
            "level": "DEBUG",
            "formatter": "json",
            "filename": "metadata_tools.log",
            "mode": "a"
        }
    },
    "loggers": {
        "stdf_mcp.tools": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False
        },
        "stdf_mcp.tools.metadata": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False
        }
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"]
    }
}


class MetadataLogger:
    """Specialized logger for metadata extraction operations."""

    def __init__(self, name: str):
        """
        Initialize metadata logger.

        Args:
            name: Logger name (typically tool name)
        """
        self.logger = logging.getLogger(f"stdf_mcp.tools.metadata.{name}")
        self.tool_name = name
        self._setup_logger()

    def _setup_logger(self):
        """Setup logger configuration if not already configured."""
        if not self.logger.handlers:
            # Add console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
            self.logger.setLevel(logging.DEBUG)

    def log_operation_start(self, operation: str, file_path: str, **kwargs):
        """
        Log the start of a metadata extraction operation.

        Args:
            operation: Operation name
            file_path: STDF file path
            **kwargs: Additional context
        """
        self.logger.info(
            f"Starting {operation}",
            extra={
                "tool_name": self.tool_name,
                "operation": operation,
                "file_path": file_path,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "context": kwargs
            }
        )

    def log_operation_success(self, operation: str, execution_time: float, **kwargs):
        """
        Log successful completion of a metadata extraction operation.

        Args:
            operation: Operation name
            execution_time: Execution time in seconds
            **kwargs: Additional context (e.g., record counts, metrics)
        """
        self.logger.info(
            f"Completed {operation} successfully",
            extra={
                "tool_name": self.tool_name,
                "operation": operation,
                "execution_time": execution_time,
                "status": "SUCCESS",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metrics": kwargs
            }
        )

    def log_operation_error(self, operation: str, error: Exception, execution_time: float = None, **kwargs):
        """
        Log error in metadata extraction operation.

        Args:
            operation: Operation name
            error: Exception that occurred
            execution_time: Execution time before error (if available)
            **kwargs: Additional context
        """
        self.logger.error(
            f"Failed {operation}: {str(error)}",
            extra={
                "tool_name": self.tool_name,
                "operation": operation,
                "error_type": type(error).__name__,
                "error_message": str(error),
                "execution_time": execution_time,
                "status": "ERROR",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "context": kwargs,
                "traceback": traceback.format_exc()
            }
        )

    def log_intel_cpu_constraint(self, file_path: str, cpu_type: str, status: str):
        """
        Log Intel CPU constraint validation.

        Args:
            file_path: STDF file path
            cpu_type: Detected CPU type
            status: ENFORCED or VIOLATED
        """
        level = logging.INFO if status == "ENFORCED" else logging.ERROR
        self.logger.log(
            level,
            f"Intel CPU constraint {status}",
            extra={
                "tool_name": self.tool_name,
                "constraint": "intel_cpu_little_endian",
                "file_path": file_path,
                "detected_cpu_type": cpu_type,
                "constraint_status": status,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    def log_performance_metrics(self, operation: str, metrics: Dict[str, Any]):
        """
        Log performance metrics for an operation.

        Args:
            operation: Operation name
            metrics: Performance metrics dict
        """
        self.logger.info(
            f"Performance metrics for {operation}",
            extra={
                "tool_name": self.tool_name,
                "operation": operation,
                "performance_metrics": metrics,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    def log_validation_result(self, validation_type: str, status: str, details: Dict[str, Any] = None):
        """
        Log validation results.

        Args:
            validation_type: Type of validation (input, output, schema, etc.)
            status: PASS or FAIL
            details: Additional validation details
        """
        level = logging.INFO if status == "PASS" else logging.WARNING
        self.logger.log(
            level,
            f"Validation {validation_type}: {status}",
            extra={
                "tool_name": self.tool_name,
                "validation_type": validation_type,
                "validation_status": status,
                "validation_details": details or {},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )

    def log_record_processing(self, record_type: str, count: int, sample_data: Dict[str, Any] = None):
        """
        Log record processing information.

        Args:
            record_type: Type of STDF record (MIR, PIR, etc.)
            count: Number of records processed
            sample_data: Sample record data for debugging
        """
        self.logger.debug(
            f"Processed {count} {record_type} records",
            extra={
                "tool_name": self.tool_name,
                "record_type": record_type,
                "record_count": count,
                "sample_data": sample_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )


def get_metadata_logger(tool_name: str) -> MetadataLogger:
    """
    Get or create a metadata logger for a specific tool.

    Args:
        tool_name: Name of the metadata tool

    Returns:
        MetadataLogger instance
    """
    return MetadataLogger(tool_name)


def log_metadata_operation(tool_name: str, operation_name: str = None):
    """
    Decorator to automatically log metadata operations.

    Args:
        tool_name: Name of the tool
        operation_name: Optional custom operation name

    Returns:
        Decorated function with logging
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_metadata_logger(tool_name)
            operation = operation_name or func.__name__
            start_time = time.time()

            # Extract file path from arguments
            file_path = args[0] if args else kwargs.get("file_path", "unknown")

            # Log operation start
            logger.log_operation_start(operation, file_path, args=args, kwargs=kwargs)

            try:
                # Execute function
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time

                # Log success with metrics
                metrics = {}
                if isinstance(result, dict) and "_metadata" in result:
                    metrics = result["_metadata"]

                logger.log_operation_success(operation, execution_time, **metrics)

                # Log Intel CPU constraint if detected
                if isinstance(result, dict) and "file_info" in result:
                    cpu_type = result["file_info"].get("cpu_type", "unknown")
                    if cpu_type == "little":
                        logger.log_intel_cpu_constraint(file_path, cpu_type, "ENFORCED")

                return result

            except Exception as e:
                execution_time = time.time() - start_time
                logger.log_operation_error(operation, e, execution_time)

                # Log Intel CPU constraint violations specifically
                if "Intel CPU" in str(e) or "little-endian" in str(e):
                    logger.log_intel_cpu_constraint(file_path, "non-intel", "VIOLATED")

                raise

        return wrapper
    return decorator


def setup_metadata_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    Setup global logging configuration for metadata tools.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional log file path
    """
    # Set log level
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    logging.getLogger("stdf_mcp.tools.metadata").setLevel(numeric_level)

    # Add file handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        logging.getLogger("stdf_mcp.tools.metadata").addHandler(file_handler)


def get_log_summary(tool_name: str = None) -> Dict[str, Any]:
    """
    Get a summary of logged operations.

    Args:
        tool_name: Optional tool name filter

    Returns:
        Log summary dict
    """
    # This would typically read from log files or a log aggregation system
    # For now, return a placeholder structure
    return {
        "summary_generated": datetime.now(timezone.utc).isoformat(),
        "tool_filter": tool_name,
        "operations_logged": 0,  # Would be populated from actual logs
        "success_rate": 0.0,
        "average_execution_time": 0.0,
        "intel_cpu_constraints_enforced": 0,
        "validation_failures": 0
    }


# Export public interface
__all__ = [
    "MetadataLogger",
    "get_metadata_logger",
    "log_metadata_operation",
    "setup_metadata_logging",
    "get_log_summary"
]


# Example usage and testing
if __name__ == "__main__":
    # Setup logging
    setup_metadata_logging("DEBUG")

    # Test logger
    logger = get_metadata_logger("test_tool")
    logger.log_operation_start("test_operation", "/path/to/test.stdf")
    logger.log_intel_cpu_constraint("/path/to/test.stdf", "little", "ENFORCED")
    logger.log_operation_success("test_operation", 1.5, records_processed=100)

    print("Logging test completed")