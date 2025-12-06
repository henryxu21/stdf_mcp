"""
PCR (Part Count Record) extractor.

Extracts PCR records from STDF V4 files using the existing parser infrastructure.
Returns all part count records (one per test site).
"""

from typing import Dict, Any, List
from pathlib import Path

from ...stdf.parser import STDFV4Parser
from ...stdf.records import PCRRecord
from .common import validate_stdf_file


def extract_pcr_records(file_path: str) -> Dict[str, Any]:
    """
    Extract PCR records from STDF file.

    Collects all PCR instances (one per test site).

    Args:
        file_path: Absolute path to STDF file

    Returns:
        Dict with structure:
        {
            "record_type": "PCR",
            "count": <int>,
            "records": [
                {
                    "record_type": 1,
                    "record_subtype": 30,
                    "head_num": <int>,
                    "site_num": <int>,
                    "part_cnt": <int>,
                    "rtst_cnt": <int>,
                    "abrt_cnt": <int>,
                    "good_cnt": <int>,
                    "func_cnt": <int>
                }
            ]
        }

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is not valid STDF format

    Examples:
        >>> result = extract_pcr_records("TestCases/example_2.stdf")
        >>> result["record_type"]
        'PCR'
        >>> result["count"] >= 0
        True
    """
    # Validate file before extraction
    validate_stdf_file(file_path)

    # Create parser and extract PCR record(s)
    parser = STDFV4Parser()
    path = Path(file_path)

    pcr_records: List[Dict[str, Any]] = []

    try:
        # Stream through records and collect all PCR instances
        for record in parser.parse_records(path):
            if isinstance(record, PCRRecord):
                # Use get_enhanced_field_dict() for complete field extraction
                pcr_dict = record.get_enhanced_field_dict()
                pcr_records.append(pcr_dict)

        # Note: Empty list is valid - some files may not have PCR records
        return {
            "record_type": "PCR",
            "count": len(pcr_records),
            "records": pcr_records
        }

    except Exception as e:
        # Re-raise as ValueError with clear message
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        raise ValueError(f"Error extracting PCR records: {str(e)}")
