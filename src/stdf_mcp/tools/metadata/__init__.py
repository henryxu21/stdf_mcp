"""
Metadata extraction tools for STDF-V4 package test files.

This module provides all 6 metadata extraction tools for User Story 1:
- extract_file_overview: Quick file assessment and summary statistics
- extract_test_configuration: Test conditions and hardware configuration
- extract_yield_summary: Part counts, yield, and retest information
- extract_facility_details: Location, process, and engineering context
- extract_program_metadata: Program identification and specifications
- extract_test_parameters: Test parameters with filtering options

All tools enforce Intel CPU little-endian constraint and package test scope.
"""

from .file_overview import extract_file_overview
from .test_configuration import extract_test_configuration
from .yield_summary import extract_yield_summary
from .facility_details import extract_facility_details
from .program_metadata import extract_program_metadata
from .test_parameters import extract_test_parameters

# Export all metadata tools
__all__ = [
    "extract_file_overview",
    "extract_test_configuration",
    "extract_yield_summary",
    "extract_facility_details",
    "extract_program_metadata",
    "extract_test_parameters"
]

# Metadata about the tools for discovery
METADATA_TOOLS = {
    "extract_file_overview": {
        "description": "Extract quick file assessment with key identifiers and summary statistics",
        "primary_use": "File validation and overview",
        "output_sections": ["file_info", "key_identifiers", "summary_statistics"]
    },
    "extract_test_configuration": {
        "description": "Extract test conditions, hardware configuration, and site descriptions",
        "primary_use": "Test setup analysis",
        "output_sections": ["test_conditions", "hardware_configuration", "site_descriptions"]
    },
    "extract_yield_summary": {
        "description": "Extract part count records, retest information, and computed statistics",
        "primary_use": "Yield analysis and statistics",
        "output_sections": ["part_count_records", "retest_information", "computed_statistics"]
    },
    "extract_facility_details": {
        "description": "Extract location information, process information, engineering context, and timing",
        "primary_use": "Manufacturing traceability",
        "output_sections": ["location_information", "process_information", "engineering_context", "timing_information"]
    },
    "extract_program_metadata": {
        "description": "Extract program identification, specifications, tester software, and user context",
        "primary_use": "Test program analysis",
        "output_sections": ["program_identification", "specifications", "tester_software", "user_context"]
    },
    "extract_test_parameters": {
        "description": "Extract test parameters with filtering options (with_limits, without_limits, all)",
        "primary_use": "Test parameter analysis",
        "output_sections": ["parameters_with_limits", "parameters_without_limits"],
        "filter_options": ["all_parameters", "with_limits_only", "without_limits_only"]
    }
}