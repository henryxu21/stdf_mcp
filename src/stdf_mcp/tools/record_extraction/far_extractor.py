"""
FAR (File Attributes Record) extractor.

Extracts the FAR record from STDF V4 files using the existing parser infrastructure.
"""

from typing import Dict, Any
from pathlib import Path

from ...stdf.parser import STDFV4Parser
from ...stdf.records import FARRecord
from .common import validate_stdf_file


def extract_far_record(file_path: str) -> Dict[str, Any]:
    """
    Extract FAR record from STDF file.

    Uses early termination optimization - stops reading after FAR record is found.

    Args:
        file_path: Absolute path to STDF file

    Returns:
        Dict with structure:
        {
            "record_type": "FAR",
            "count": 1,
            "records": [
                {
                    "record_type": 0,
                    "record_subtype": 10,
                    "cpu_type": <int>,
                    "stdf_ver": <int>
                }
            ]
        }

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is not valid STDF format or FAR not found

    Examples:
        >>> result = extract_far_record("TestCases/example_2.stdf")
        >>> result["record_type"]
        'FAR'
        >>> result["count"]
        1
    """
    # Validate file before extraction
    validate_stdf_file(file_path)

    # Create parser and extract FAR record
    parser = STDFV4Parser()
    path = Path(file_path)

    far_record = None

    try:
        # Stream through records and stop after FAR (first record)
        for record in parser.parse_records(path):
            if isinstance(record, FARRecord):
                far_record = record
                break  # Early termination - FAR is always first record

        if far_record is None:
            raise ValueError(
                f"FAR record not found in file {file_path}. "
                "File may be corrupted or incomplete."
            )

        # Build response using get_enhanced_field_dict() from record class
        far_dict = far_record.get_enhanced_field_dict()

        return {
            "record_type": "FAR",
            "count": 1,
            "records": [far_dict]
        }

    except Exception as e:
        # Re-raise as ValueError with clear message
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        raise ValueError(f"Error extracting FAR record: {str(e)}")
