"""
MRR (Master Results Record) extractor.

Extracts the MRR record from STDF V4 files using the existing parser infrastructure.
MRR is always the last record in a valid STDF file.
"""

from typing import Dict, Any
from pathlib import Path

from ...stdf.parser import STDFV4Parser
from ...stdf.records import MRRRecord
from .common import validate_stdf_file


def extract_mrr_record(file_path: str) -> Dict[str, Any]:
    """
    Extract MRR record from STDF file.

    MRR is always the last record in a valid STDF file.
    Requires full file scan to reach the end.

    Args:
        file_path: Absolute path to STDF file

    Returns:
        Dict with structure:
        {
            "record_type": "MRR",
            "count": 1,
            "records": [
                {
                    "record_type": 1,
                    "record_subtype": 20,
                    "finish_t": <int>,
                    "disp_cod": <str>,
                    "usr_desc": <str>,
                    "exc_desc": <str>
                }
            ]
        }

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is not valid STDF format or MRR not found

    Examples:
        >>> result = extract_mrr_record("TestCases/example_2.stdf")
        >>> result["record_type"]
        'MRR'
        >>> result["count"]
        1
    """
    # Validate file before extraction
    validate_stdf_file(file_path)

    # Create parser and extract MRR record
    parser = STDFV4Parser()
    path = Path(file_path)

    mrr_record = None

    try:
        # Stream through all records - MRR is at the end
        for record in parser.parse_records(path):
            if isinstance(record, MRRRecord):
                mrr_record = record
                # Note: Continue scanning in case of multiple MRR (though rare)
                # We want the last one

        if mrr_record is None:
            raise ValueError(
                f"MRR record not found in file {file_path}. "
                "File may be corrupted or incomplete."
            )

        # Build response using get_enhanced_field_dict() from record class
        mrr_dict = {
            'record_type': mrr_record.record_type,
            'record_subtype': mrr_record.record_subtype,
            **mrr_record.get_enhanced_field_dict()
        }

        return {
            "record_type": "MRR",
            "count": 1,
            "records": [mrr_dict]
        }

    except Exception as e:
        # Re-raise as ValueError with clear message
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        raise ValueError(f"Error extracting MRR record: {str(e)}")
