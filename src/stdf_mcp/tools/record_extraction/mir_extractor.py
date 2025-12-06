"""
MIR (Master Information Record) extractor.

Extracts MIR records from STDF V4 files using the existing parser infrastructure.
Handles multiple MIR instances for multi-session files.
"""

from typing import Dict, Any, List
from pathlib import Path

from ...stdf.parser import STDFV4Parser
from ...stdf.records import MIRRecord
from .common import validate_stdf_file


def extract_mir_record(file_path: str) -> Dict[str, Any]:
    """
    Extract MIR record(s) from STDF file.

    Collects all MIR instances (supports multi-session files).
    Returns complete field extraction with all 38 MIR fields.

    Args:
        file_path: Absolute path to STDF file

    Returns:
        Dict with structure:
        {
            "record_type": "MIR",
            "count": <int>,
            "records": [
                {
                    "record_type": 1,
                    "record_subtype": 10,
                    "setup_t": <int>,
                    "start_t": <int>,
                    "stat_num": <int>,
                    "mode_cod": <str>,
                    "rtst_cod": <str>,
                    "prot_cod": <str>,
                    "burn_tim": <int>,
                    "cmod_cod": <str>,
                    "lot_id": <str>,
                    "part_typ": <str>,
                    ... (30 total string fields)
                }
            ]
        }

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is not valid STDF format or MIR not found

    Examples:
        >>> result = extract_mir_record("TestCases/example_2.stdf")
        >>> result["record_type"]
        'MIR'
        >>> result["count"] >= 1
        True
        >>> "lot_id" in result["records"][0]
        True
    """
    # Validate file before extraction
    validate_stdf_file(file_path)

    # Create parser and extract MIR record(s)
    parser = STDFV4Parser()
    path = Path(file_path)

    mir_records: List[Dict[str, Any]] = []

    try:
        # Stream through records and collect all MIR instances
        for record in parser.parse_records(path):
            if isinstance(record, MIRRecord):
                # Use get_enhanced_field_dict() for complete field extraction
                mir_dict = {
                    'record_type': record.record_type,
                    'record_subtype': record.record_subtype,
                    **record.get_enhanced_field_dict()
                }
                mir_records.append(mir_dict)

        if not mir_records:
            raise ValueError(
                f"MIR record not found in file {file_path}. "
                "File may be corrupted or incomplete."
            )

        return {
            "record_type": "MIR",
            "count": len(mir_records),
            "records": mir_records
        }

    except Exception as e:
        # Re-raise as ValueError with clear message
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        raise ValueError(f"Error extracting MIR record: {str(e)}")
