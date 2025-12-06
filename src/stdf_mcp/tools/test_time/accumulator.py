"""Device test time accumulator for STDF record processing.

This module handles accumulation of test time data from STDF PIR and PRR records,
maintaining chronological order and handling missing test times. Supports multi-site
testing where multiple PIRs may appear before their corresponding PRRs.
"""

from typing import Dict, List, Optional, Tuple
from stdf_mcp.stdf.records.part_records import PIRRecord, PRRRecord
from stdf_mcp.tools.test_time.models import TestTimeRecord


class DeviceTestTimeAccumulator:
    """Accumulates test time data from STDF PIR/PRR record pairs.

    Processes PIR (Part Information Record) and PRR (Part Result Record) pairs
    to extract device identification and test execution time, maintaining
    chronological order matching STDF file sequence.

    Supports multi-site testing where PIRs for multiple sites appear before
    their corresponding PRRs (e.g., PIR(site1), PIR(site2), PRR(site1), PRR(site2)).

    Attributes:
        site_filter: Optional list of site numbers to include (None = all sites)
        _records: Accumulated test time records in chronological order
        _pending_pirs: Dictionary of PIR records awaiting matching PRR, keyed by (head, site)
    """

    def __init__(self, site_filter: Optional[List[int]] = None):
        """Initialize accumulator.

        Args:
            site_filter: Optional list of site numbers [0-255] to filter.
                        None means include all sites.
        """
        self.site_filter = site_filter
        self._records: List[TestTimeRecord] = []
        # Changed from single _current_pir to dictionary to support multi-site
        self._pending_pirs: Dict[Tuple[int, int], PIRRecord] = {}  # (head, site) -> PIR

    def process_pir(self, pir: PIRRecord) -> None:
        """Process PIR record (device start).

        Stores PIR record to be matched with subsequent PRR record.
        Filters by site if site_filter is specified.
        Supports multi-site where multiple PIRs appear before PRRs.

        Args:
            pir: Part Information Record marking device test start
        """
        # Check site filtering
        if self.site_filter is not None:
            if pir.site_num not in self.site_filter:
                return  # Skip this device

        # Store PIR keyed by (head, site) to support multi-site
        key = (pir.head_num, pir.site_num)
        self._pending_pirs[key] = pir

    def process_prr(self, prr: PRRRecord) -> None:
        """Process PRR record (device completion).

        Matches PRR with previously stored PIR to create TestTimeRecord.
        Extracts test time from PRR.TEST_T field.

        Args:
            prr: Part Result Record containing test results and test time
        """
        # Look up matching PIR by (head, site)
        key = (prr.head_num, prr.site_num)
        pir = self._pending_pirs.get(key)

        if pir is None:
            # No matching PIR (filtered out, missing, or already processed)
            return

        # Extract test time from PRR.TEST_T
        test_time_seconds = self._extract_test_time(prr)

        # Create TestTimeRecord
        # Note: PART_ID comes from PRR, not PIR (PIR only has HEAD_NUM and SITE_NUM)
        record = TestTimeRecord(
            device_id=prr.part_id or "",  # Use PRR.PART_ID
            site=pir.site_num,
            head=pir.head_num,
            timestamp=None,  # PIR doesn't have timestamp in STDF-V4
            test_time_seconds=test_time_seconds,
        )

        self._records.append(record)

        # Remove processed PIR from pending dictionary
        del self._pending_pirs[key]

    def _extract_test_time(self, prr: PRRRecord) -> Optional[float]:
        """Extract test time from PRR.TEST_T field.

        Converts TEST_T from milliseconds to seconds. Treats TEST_T=0 as
        missing data per STDF convention (cannot test in 0ms).

        Args:
            prr: Part Result Record containing TEST_T field

        Returns:
            Test time in seconds, or None if TEST_T=0 (missing)
        """
        if prr.test_t == 0:
            return None  # Treat 0 as missing per research decision #3

        # Convert milliseconds to seconds
        return prr.test_t / 1000.0

    def get_records(self) -> List[TestTimeRecord]:
        """Get accumulated test time records.

        Returns:
            List of TestTimeRecord objects in chronological order
            (matching STDF file device execution sequence)
        """
        return self._records.copy()

    def get_record_count(self) -> int:
        """Get count of accumulated records.

        Returns:
            Number of device records accumulated
        """
        return len(self._records)

    def get_valid_count(self) -> int:
        """Get count of records with valid (non-null) test times.

        Returns:
            Number of devices with test_time_seconds != None
        """
        return sum(1 for r in self._records if r.test_time_seconds is not None)

    def get_null_count(self) -> int:
        """Get count of records with missing (null) test times.

        Returns:
            Number of devices with test_time_seconds == None
        """
        return sum(1 for r in self._records if r.test_time_seconds is None)
