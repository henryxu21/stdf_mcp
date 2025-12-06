"""
SDR (Site Description Record) extractor for STDF files.

Extracts SDR records containing test site configuration information including
site count, site numbers, handler type, load board details, and DIB information.
"""

from pathlib import Path
from typing import Dict, Any, List

from stdf_mcp.stdf.parser import STDFV4Parser
from stdf_mcp.stdf.records.specialized_records import SDRRecord
from .common import validate_stdf_file


def extract_sdr_records(file_path: str) -> Dict[str, Any]:
    """
    Extract SDR record(s) from STDF file.

    SDR (Site Description Record) contains test site configuration information
    including site count, site numbers, handler type, handler ID, load board
    type/ID, and DIB (Device Interface Board) type/ID.

    Args:
        file_path: Absolute path to STDF file

    Returns:
        Dictionary with structure:
        {
            "record_type": "SDR",
            "count": <number_of_sdr_records>,
            "records": [
                {
                    "record_type": 1,
                    "record_subtype": 80,
                    "head_num": <test_head_number>,
                    "site_grp": <site_group_number>,
                    "site_cnt": <number_of_test_sites>,
                    "site_num": [<array_of_site_numbers>],
                    "hand_typ": <handler_type>,
                    "hand_id": <handler_id>,
                    "card_typ": <card_type>,
                    "card_id": <card_id>,
                    "load_typ": <load_board_type>,
                    "load_id": <load_board_id>,
                    "dib_typ": <dib_type>,
                    "dib_id": <dib_id>,
                    "cabl_typ": <cable_type>,
                    "cabl_id": <cable_id>,
                    "cont_typ": <contactor_type>,
                    "cont_id": <contactor_id>,
                    "lasr_typ": <laser_type>,
                    "lasr_id": <laser_id>,
                    "extr_typ": <extra_type>,
                    "extr_id": <extra_id>
                },
                ...
            ]
        }

    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If file is invalid STDF format

    Example:
        >>> result = extract_sdr_records("/path/to/file.stdf")
        >>> print(f"Found {result['count']} SDR records")
        >>> if result['count'] > 0:
        ...     sdr = result['records'][0]
        ...     print(f"Site count: {sdr['site_cnt']}")
        ...     print(f"Handler type: {sdr['hand_typ']}")
    """
    # Validate file before processing
    validate_stdf_file(file_path)

    # Initialize parser
    parser = STDFV4Parser()
    path = Path(file_path)

    sdr_records: List[Dict[str, Any]] = []

    try:
        # Scan file for all SDR records
        for record in parser.parse_records(path):
            if isinstance(record, SDRRecord):
                # Get field dict with all SDR fields
                sdr_dict = record.get_field_dict()
                sdr_records.append(sdr_dict)

        # SDR is typically present but not required
        # Return empty list if not found
        return {
            "record_type": "SDR",
            "count": len(sdr_records),
            "records": sdr_records
        }

    except Exception as e:
        # Re-raise known exceptions
        if isinstance(e, (FileNotFoundError, ValueError)):
            raise
        # Wrap unexpected exceptions
        raise ValueError(f"Error extracting SDR records: {str(e)}")
