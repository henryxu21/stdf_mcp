"""
HBR (Hardware Bin Record) extractor.

Extracts HBR records from STDF V4 files using the existing parser infrastructure.
Returns all hardware bin records (one per bin).
"""

from typing import Dict, Any, List
from pathlib import Path

from ...stdf.parser import STDFV4Parser
from ...stdf.records import HBRRecord
from .common import validate_stdf_file


def extract_hbr_records(file_path: str) -> Dict[str, Any]:
    """
    Extract HBR records from STDF file.

    Collects all HBR instances (one per hardware bin).

    Args:
        file_path: Absolute path to STDF file

    Returns:
        Dict with structure:
        {
            "record_type": "HBR",
            "count": <int>,
            "records": [
                {
                    "record_type": 1,
                    "record_subtype": 40,
                    "head_num": <int>,
                    "site_num": <int>,
                    "hbin_num": <int>,
                    "hbin_cnt": <int>,
                    "hbin_pf": <str>,
                    "hbin_nam": <str>
                }
            ]
        }

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is not valid STDF format

    Examples:
        >>> result = extract_hbr_records("TestCases/example_2.stdf")
        >>> result["record_type"]
        'HBR'
        >>> result["count"] >= 0
        True
    """
    # Validate file before extraction
    validate_stdf_file(file_path)

    # Create parser and extract HBR record(s)
    parser = STDFV4Parser()
    path = Path(file_path)

    hbr_records: List[Dict[str, Any]] = []

    try:
        # Stream through records and collect all HBR instances
        for record in parser.parse_records(path):
            if isinstance(record, HBRRecord):
                # Use get_enhanced_field_dict() for complete field extraction
                hbr_dict = record.get_enhanced_field_dict()
                hbr_records.append(hbr_dict)

        # Note: Empty list is valid - some files may not have HBR records
        return {
            "record_type": "HBR",
            "count": len(hbr_records),
            "records": hbr_records
        }

    except Exception as e:
        # Re-raise as ValueError with clear message
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        raise ValueError(f"Error extracting HBR records: {str(e)}")
