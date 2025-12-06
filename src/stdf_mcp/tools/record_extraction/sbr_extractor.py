"""
SBR (Software Bin Record) extractor.

Extracts SBR records from STDF V4 files using the existing parser infrastructure.
Returns all software bin records (one per bin).
"""

from typing import Dict, Any, List
from pathlib import Path

from ...stdf.parser import STDFV4Parser
from ...stdf.records import SBRRecord
from .common import validate_stdf_file


def extract_sbr_records(file_path: str) -> Dict[str, Any]:
    """
    Extract SBR records from STDF file.

    Collects all SBR instances (one per software bin).

    Args:
        file_path: Absolute path to STDF file

    Returns:
        Dict with structure:
        {
            "record_type": "SBR",
            "count": <int>,
            "records": [
                {
                    "record_type": 1,
                    "record_subtype": 50,
                    "head_num": <int>,
                    "site_num": <int>,
                    "sbin_num": <int>,
                    "sbin_cnt": <int>,
                    "sbin_pf": <str>,
                    "sbin_nam": <str>
                }
            ]
        }

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is not valid STDF format

    Examples:
        >>> result = extract_sbr_records("TestCases/example_2.stdf")
        >>> result["record_type"]
        'SBR'
        >>> result["count"] >= 0
        True
    """
    # Validate file before extraction
    validate_stdf_file(file_path)

    # Create parser and extract SBR record(s)
    parser = STDFV4Parser()
    path = Path(file_path)

    sbr_records: List[Dict[str, Any]] = []

    try:
        # Stream through records and collect all SBR instances
        for record in parser.parse_records(path):
            if isinstance(record, SBRRecord):
                # Use get_enhanced_field_dict() for complete field extraction
                sbr_dict = record.get_enhanced_field_dict()
                sbr_records.append(sbr_dict)

        # Note: Empty list is valid - some files may not have SBR records
        return {
            "record_type": "SBR",
            "count": len(sbr_records),
            "records": sbr_records
        }

    except Exception as e:
        # Re-raise as ValueError with clear message
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        raise ValueError(f"Error extracting SBR records: {str(e)}")
