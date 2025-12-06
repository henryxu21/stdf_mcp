"""
Test Suite Hierarchy Inference Module.

This module provides functionality for inferring test suite hierarchy from STDF
TSR (Test Synopsis Record) records. It parses dot-delimited fully qualified test
names with escape character support and builds indexes for O(1) test suite lookup.

Key Components:
- parse_hierarchy_path(): Parse dot-delimited paths with escape character support
- is_hierarchical_name(): Detect hierarchical vs simple test names
- infer_hierarchy_from_tsr(): Extract hierarchy info from TSR records
- HierarchyInfo: Dataclass storing hierarchy information for one test
- TestSuiteInfo: Dataclass aggregating test items under a test suite
- HierarchyMap: Complete hierarchy index for O(1) suite lookup

Design Decisions (from research.md):
- Placeholder-based escape character parsing for "\\." notation
- Flat dictionary indexes with case-normalized keys for O(1) lookup
- Simple vs hierarchical name detection using unescaped dot presence
- TSR simple names (no dots) treated as non-hierarchical tests

References:
- Feature Specification: specs/007-test-suite-hierarchy/spec.md
- Research Document: specs/007-test-suite-hierarchy/research.md
- Data Model: specs/007-test-suite-hierarchy/data-model.md
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Any
import logging

logger = logging.getLogger(__name__)


def parse_hierarchy_path(qualified_name: str) -> List[str]:
    """
    Parse dot-delimited hierarchy path with escape character support.

    This function splits a hierarchical test name on unescaped dots while
    treating "\\." as a literal dot character within component names.

    Algorithm (from research.md):
    1. Replace escaped dots ("\\") with placeholder
    2. Split on remaining unescaped dots
    3. Restore escaped dots in components

    Args:
        qualified_name: Fully qualified name from TSR TEST_NAM field

    Returns:
        List[str]: Hierarchy components with escaped dots unescaped

    Raises:
        ValueError: If qualified_name is empty or whitespace-only

    Examples:
        >>> parse_hierarchy_path("Main.Subflow.Suite.Item")
        ['Main', 'Subflow', 'Suite', 'Item']

        >>> parse_hierarchy_path("Main.Test\\.V2\\.1.Suite.Item")
        ['Main', 'Test.V2.1', 'Suite', 'Item']

        >>> parse_hierarchy_path("SIMPLE_TEST_NAME")
        ['SIMPLE_TEST_NAME']

    Performance: O(n) where n = string length, <1ms for 200-char paths
    """
    # Validate input
    if not qualified_name or not qualified_name.strip():
        raise ValueError("qualified_name cannot be empty or whitespace only")

    # Handle simple names (no dots at all)
    if "." not in qualified_name:
        return [qualified_name]

    # Replace escaped dots with placeholder
    placeholder = "\x00ESCAPED_DOT\x00"
    temp = qualified_name.replace("\\.", placeholder)

    # Split on unescaped dots
    components = temp.split(".")

    # Restore escaped dots in each component
    return [c.replace(placeholder, ".") for c in components]


def is_hierarchical_name(test_nam: str) -> bool:
    """
    Detect if TEST_NAM field contains hierarchy information.

    A test name is considered hierarchical if it contains at least one
    unescaped dot (".") that acts as a hierarchy delimiter.

    Rules (from spec.md FR-002):
    - Contains at least one unescaped dot → hierarchical
    - No dots OR only escaped dots ("\\") → simple name (not hierarchical)

    Args:
        test_nam: TEST_NAM field from TSR record

    Returns:
        bool: True if hierarchical, False if simple name

    Examples:
        >>> is_hierarchical_name("Main.Subflow.Suite.Item")
        True

        >>> is_hierarchical_name("SIMPLE_TEST_NAME")
        False

        >>> is_hierarchical_name("Test\\.V2\\.1")  # Only escaped dots
        False

        >>> is_hierarchical_name("Main.Test\\.V2.Suite")  # Mixed
        True

    Performance: O(n) where n = string length
    """
    # Empty or whitespace-only is not hierarchical
    if not test_nam or not test_nam.strip():
        return False

    # Replace escaped dots temporarily to check for unescaped dots
    temp = test_nam.replace("\\.", "")

    # If any dots remain, they are unescaped (hierarchy delimiters)
    return "." in temp


@dataclass
class HierarchyInfo:
    """
    Hierarchy information inferred from a single TSR record.

    This entity captures the parsed hierarchy structure for one test item,
    extracted from the TSR record's fully qualified test name.

    Fields:
        test_num: STDF test number (0 to 2^32-1)
        test_item_name: Leaf node name (last component)
        test_suite_simple: Test suite simple name (second-to-last component)
        test_suite_qualified: Full suite path (all components except last)
        full_path: Complete TSR TEST_NAM value
        test_type: TSR TEST_TYP value ('P', 'F', 'M')
        hierarchy_depth: Number of levels in hierarchy (>= 2)

    Validation:
        - test_num must be 0 to 2^32-1
        - All string fields must be non-empty
        - hierarchy_depth must be >= 2 if specified

    Example:
        HierarchyInfo(
            test_num=1052,
            test_item_name="BT5G_RX_GAINCAL_BAND2",
            test_suite_simple="Bt5gRxGainCal",
            test_suite_qualified="Main.RxGainCal.Bt5gRxGainCal",
            full_path="Main.RxGainCal.Bt5gRxGainCal.BT5G_RX_GAINCAL_BAND2",
            test_type="P",
            hierarchy_depth=4
        )
    """

    test_num: int
    test_item_name: str
    test_suite_simple: str
    test_suite_qualified: str
    full_path: str
    test_type: Optional[str] = None
    hierarchy_depth: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate HierarchyInfo fields."""
        # Validate test_num range
        if not (0 <= self.test_num <= 2**32 - 1):
            raise ValueError(
                f"test_num {self.test_num} out of valid range 0 to 2^32-1"
            )

        # Validate non-empty strings
        if not self.test_item_name:
            raise ValueError("test_item_name cannot be empty")
        if not self.test_suite_simple:
            raise ValueError("test_suite_simple cannot be empty")
        if not self.test_suite_qualified:
            raise ValueError("test_suite_qualified cannot be empty")
        if not self.full_path:
            raise ValueError("full_path cannot be empty")

        # Validate hierarchy_depth
        if self.hierarchy_depth is not None and self.hierarchy_depth < 2:
            raise ValueError(f"hierarchy_depth must be >= 2, got {self.hierarchy_depth}")


@dataclass
class TestSuiteInfo:
    """
    Test suite summary with associated test items and metadata.

    This entity aggregates all test items belonging to a specific test suite,
    supporting both simple and qualified name access patterns.

    Fields:
        simple_name: Simple suite name (rightmost component)
        qualified_path: Fully qualified suite path
        test_item_names: List of test item names in this suite
        test_numbers: Set of STDF test numbers for O(1) lookup
        item_count: Number of test items in this suite
        hierarchy_level: Suite position in hierarchy
        parent_path: Parent subflow path

    Validation:
        - simple_name: Non-empty, no unescaped dots
        - qualified_path: Non-empty
        - test_item_names: Non-empty list, no duplicates
        - test_numbers: Non-empty set, all values 0 to 2^32-1
        - item_count must equal len(test_item_names) and len(test_numbers)

    Example:
        TestSuiteInfo(
            simple_name="Bt5gRxGainCal",
            qualified_path="Main.RxGainCal.Bt5gRxGainCal",
            test_item_names=["BT5G_RX_GAINCAL_BAND2", "BT5G_RX_GAINCAL_BAND3"],
            test_numbers={1052, 1053},
            item_count=2,
            hierarchy_level=4
        )
    """

    simple_name: str
    qualified_path: str
    test_item_names: List[str]
    test_numbers: Set[int]
    item_count: int
    hierarchy_level: Optional[int] = None
    parent_path: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate TestSuiteInfo fields."""
        # Validate simple_name
        if not self.simple_name:
            raise ValueError("simple_name cannot be empty")

        # Validate qualified_path
        if not self.qualified_path:
            raise ValueError("qualified_path cannot be empty")

        # Validate test_item_names
        if not self.test_item_names:
            raise ValueError("test_item_names cannot be empty")

        # Validate test_numbers
        if not self.test_numbers:
            raise ValueError("test_numbers cannot be empty")
        for test_num in self.test_numbers:
            if not (0 <= test_num <= 2**32 - 1):
                raise ValueError(f"test_num {test_num} out of valid range")

        # Validate item_count matches
        if self.item_count != len(self.test_item_names):
            raise ValueError(
                f"item_count {self.item_count} != len(test_item_names) {len(self.test_item_names)}"
            )
        if self.item_count != len(self.test_numbers):
            raise ValueError(
                f"item_count {self.item_count} != len(test_numbers) {len(self.test_numbers)}"
            )

    @property
    def normalized_simple_name(self) -> str:
        """Return case-normalized simple name for matching."""
        return self.simple_name.lower()

    @property
    def normalized_qualified_path(self) -> str:
        """Return case-normalized qualified path for matching."""
        return self.qualified_path.lower()


def infer_hierarchy_from_tsr(tsr_record: Any) -> Optional[HierarchyInfo]:
    """
    Infer hierarchy information from TSR record.

    This function parses the TSR TEST_NAM field to extract hierarchy structure.
    Returns None if the test name is simple (no hierarchy) or invalid.

    Args:
        tsr_record: TSRRecord instance with test_nam and test_num fields

    Returns:
        HierarchyInfo if test_nam contains hierarchy, None otherwise

    Rules (from spec.md FR-002, FR-010):
        - Returns None if test_nam is None or empty
        - Returns None if test_nam has no unescaped dots (simple name)
        - Returns None if hierarchy depth < 2 (need suite + item minimum)
        - Extracts test_suite_simple from second-to-last component
        - Extracts test_item_name from last component

    Examples:
        >>> from dataclasses import dataclass
        >>> @dataclass
        ... class TSR:
        ...     test_num: int
        ...     test_nam: str
        ...     test_typ: str
        >>> tsr = TSR(1052, "Main.RxGainCal.Bt5gRxGainCal.ITEM", "P")
        >>> info = infer_hierarchy_from_tsr(tsr)
        >>> info.test_suite_simple
        'Bt5gRxGainCal'

        >>> tsr_simple = TSR(2000, "SIMPLE_TEST_NAME", "P")
        >>> infer_hierarchy_from_tsr(tsr_simple)  # Returns None
    """
    # Check for None or empty test_nam
    if not hasattr(tsr_record, 'test_nam') or not tsr_record.test_nam:
        return None

    test_nam = tsr_record.test_nam.strip() if isinstance(tsr_record.test_nam, str) else ""
    if not test_nam:
        return None

    # Check if test_nam is hierarchical
    if not is_hierarchical_name(test_nam):
        return None

    # Parse hierarchy path
    try:
        components = parse_hierarchy_path(test_nam)
    except ValueError:
        return None

    # Need at least 2 components (TestSuite.TestItem)
    if len(components) < 2:
        return None

    # Extract components (skip empty components from leading/trailing dots)
    # Filter out empty strings to handle edge cases like ".Main.Suite.Item." or "..Main"
    non_empty_components = [c for c in components if c]

    # Re-check minimum depth after filtering
    if len(non_empty_components) < 2:
        return None

    test_item_name = non_empty_components[-1]  # Last non-empty component
    test_suite_simple = non_empty_components[-2]  # Second-to-last non-empty component
    test_suite_qualified = ".".join(non_empty_components[:-1])  # All except last
    hierarchy_depth = len(non_empty_components)

    # Get test_type if available
    test_type = getattr(tsr_record, 'test_typ', None)

    return HierarchyInfo(
        test_num=tsr_record.test_num,
        test_item_name=test_item_name,
        test_suite_simple=test_suite_simple,
        test_suite_qualified=test_suite_qualified,
        full_path=test_nam,
        test_type=test_type,
        hierarchy_depth=hierarchy_depth
    )


@dataclass
class HierarchyMap:
    """
    Complete hierarchy index for STDF file with O(1) suite lookup.

    This entity provides fast test suite filtering by maintaining multiple
    indexes optimized for different query patterns.

    Indexes:
        simple_name_index: Case-insensitive simple name → List[TestSuiteInfo]
        qualified_name_index: Case-insensitive qualified path → TestSuiteInfo
        test_num_to_hierarchy: test_num → HierarchyInfo mapping

    Statistics:
        total_test_suites: Unique test suite count
        total_hierarchical_tests: Tests with hierarchy info
        total_simple_tests: Tests without hierarchy (TSR simple names)

    Design (from research.md):
        - Flat dictionary approach for O(1) lookup performance
        - Case-normalized keys using .lower() for case-insensitive matching
        - simple_name_index returns List to handle ambiguous names
        - qualified_name_index returns single TestSuiteInfo (unique per path)

    Example:
        hierarchy_map = HierarchyMap.from_tsr_records(tsr_records)
        suites = hierarchy_map.get_test_suite("Bt5gRxGainCal", is_qualified=False)
        test_nums = hierarchy_map.get_test_numbers_for_suite(suite_filter)
    """

    simple_name_index: Dict[str, List[TestSuiteInfo]] = field(default_factory=dict)
    qualified_name_index: Dict[str, TestSuiteInfo] = field(default_factory=dict)
    test_num_to_hierarchy: Dict[int, HierarchyInfo] = field(default_factory=dict)
    total_test_suites: int = 0
    total_hierarchical_tests: int = 0
    total_simple_tests: int = 0

    @classmethod
    def from_tsr_records(cls, tsr_records: List) -> 'HierarchyMap':
        """
        Build HierarchyMap from TSR records.

        Process (from research.md):
        1. Parse each TSR TEST_NAM field
        2. Detect hierarchical vs simple names
        3. Build HierarchyInfo for hierarchical names
        4. Aggregate into TestSuiteInfo by test_suite_qualified
        5. Construct normalized indexes
        6. Calculate statistics

        Args:
            tsr_records: List of TSR records from STDF file

        Returns:
            Complete HierarchyMap with all indexes populated

        Performance: <5 seconds for 100,000 TSR records per SC-002
        """
        # Step 1: Infer hierarchy from each TSR
        hierarchy_infos: List[HierarchyInfo] = []
        simple_test_count = 0

        for tsr in tsr_records:
            hierarchy_info = infer_hierarchy_from_tsr(tsr)
            if hierarchy_info:
                hierarchy_infos.append(hierarchy_info)
            else:
                # Count as simple test (no hierarchy or None test_nam)
                if hasattr(tsr, 'test_nam') and tsr.test_nam:
                    simple_test_count += 1

        # Step 2: Aggregate HierarchyInfo into TestSuiteInfo
        # Group by test_suite_qualified (case-sensitive at this stage)
        # Use dict to track test items by test_num to avoid duplicates
        suite_aggregation: Dict[str, Dict] = {}

        for h_info in hierarchy_infos:
            qualified_key = h_info.test_suite_qualified

            if qualified_key not in suite_aggregation:
                suite_aggregation[qualified_key] = {
                    'test_suite_simple': h_info.test_suite_simple,
                    'test_suite_qualified': h_info.test_suite_qualified,
                    'test_items': {},  # Dict[test_num, test_item_name] to avoid duplicates
                    'hierarchy_depth': h_info.hierarchy_depth
                }

            # Use test_num as key to avoid duplicate test items
            suite_aggregation[qualified_key]['test_items'][h_info.test_num] = h_info.test_item_name

        # Step 3: Create TestSuiteInfo objects
        test_suite_infos: List[TestSuiteInfo] = []
        for suite_data in suite_aggregation.values():
            # Convert dict to lists
            test_items_dict = suite_data['test_items']
            test_numbers = set(test_items_dict.keys())
            test_item_names = list(test_items_dict.values())

            suite_info = TestSuiteInfo(
                simple_name=suite_data['test_suite_simple'],
                qualified_path=suite_data['test_suite_qualified'],
                test_item_names=test_item_names,
                test_numbers=test_numbers,
                item_count=len(test_numbers),
                hierarchy_level=suite_data['hierarchy_depth']
            )
            test_suite_infos.append(suite_info)

        # Step 4: Build case-insensitive indexes
        simple_name_index: Dict[str, List[TestSuiteInfo]] = {}
        qualified_name_index: Dict[str, TestSuiteInfo] = {}

        for suite_info in test_suite_infos:
            # Simple name index (may have multiple suites with same simple name)
            simple_key = suite_info.normalized_simple_name
            if simple_key not in simple_name_index:
                simple_name_index[simple_key] = []
            simple_name_index[simple_key].append(suite_info)

            # Qualified name index (unique per qualified path)
            qualified_key = suite_info.normalized_qualified_path
            qualified_name_index[qualified_key] = suite_info

        # Step 5: Build test_num_to_hierarchy mapping
        test_num_to_hierarchy = {h_info.test_num: h_info for h_info in hierarchy_infos}

        # Step 6: Calculate statistics
        total_test_suites = len(test_suite_infos)
        total_hierarchical_tests = len(hierarchy_infos)
        total_simple_tests = simple_test_count

        logger.info(
            f"HierarchyMap constructed: {total_test_suites} suites, "
            f"{total_hierarchical_tests} hierarchical tests, "
            f"{total_simple_tests} simple tests"
        )

        return cls(
            simple_name_index=simple_name_index,
            qualified_name_index=qualified_name_index,
            test_num_to_hierarchy=test_num_to_hierarchy,
            total_test_suites=total_test_suites,
            total_hierarchical_tests=total_hierarchical_tests,
            total_simple_tests=total_simple_tests
        )

    def get_test_suite(
        self,
        suite_name: str,
        is_qualified: bool,
        case_sensitive: bool = False
    ) -> List[TestSuiteInfo]:
        """
        Lookup test suite by simple or qualified name.

        Args:
            suite_name: Simple name or qualified path
            is_qualified: True if suite_name is qualified path
            case_sensitive: True for case-sensitive matching (default False)

        Returns:
            List[TestSuiteInfo]: Matching test suites (may be empty)
                - Simple name: may return multiple matches
                - Qualified name: returns 0 or 1 match

        Performance: O(1) dictionary lookup for case-insensitive,
                     O(n) iteration for case-sensitive
        """
        if case_sensitive:
            # Case-sensitive: Need to iterate and compare original names
            if is_qualified:
                # Search through qualified index values
                for test_suite in self.qualified_name_index.values():
                    if test_suite.qualified_path == suite_name:
                        return [test_suite]
                return []
            else:
                # Search through simple index values
                results = []
                for suite_list in self.simple_name_index.values():
                    for test_suite in suite_list:
                        if test_suite.simple_name == suite_name:
                            results.append(test_suite)
                return results
        else:
            # Case-insensitive: Use normalized index keys (O(1))
            search_key = suite_name.lower()

            if is_qualified:
                # Qualified lookup: returns 0 or 1 result
                found_suite: Optional[TestSuiteInfo] = self.qualified_name_index.get(search_key)
                return [found_suite] if found_suite else []
            else:
                # Simple name lookup: may return multiple results
                results = self.simple_name_index.get(search_key, [])

                # T037: Log warning when simple name matches multiple suites
                if len(results) > 1:
                    matched_paths = [suite.qualified_path for suite in results]
                    logger.warning(
                        f"Test suite name '{suite_name}' matches {len(results)} suites. "
                        f"Use qualified name for precise filtering. "
                        f"Matched paths: {matched_paths}"
                    )

                return results

    def get_test_numbers_for_suite(self, suite_filter: Any) -> Set[int]:
        """
        Get all test numbers belonging to specified test suite.

        Args:
            suite_filter: TestSuiteFilter with suite_name, is_qualified, case_sensitive

        Returns:
            Set[int]: Test numbers for all matching suites (may be empty)

        Usage:
            matched_test_nums = hierarchy_map.get_test_numbers_for_suite(suite_filter)
            # Use matched_test_nums for O(1) PTR/FTR filtering
        """
        matched_suites = self.get_test_suite(
            suite_filter.suite_name,
            suite_filter.is_qualified,
            suite_filter.case_sensitive
        )

        # Aggregate test numbers from all matched suites
        all_test_nums: Set[int] = set()
        for suite_info in matched_suites:
            all_test_nums.update(suite_info.test_numbers)

        return all_test_nums
