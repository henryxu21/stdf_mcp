"""
Package test domain model for STDF-V4 data.

This module provides specialized data structures and operations
for package/final test analysis, including test flow modeling,
yield analysis, and bin correlation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict
import statistics

from .stdf_data import STDFData, PartResult, TestResult, TestDefinition, BinDefinition


class TestType(Enum):
    """Test type classifications for package testing."""
    PARAMETRIC = "Parametric"
    FUNCTIONAL = "Functional"
    MULTIPLE_PARAMETRIC = "Multiple_Parametric"
    UNKNOWN = "Unknown"


class FailureMode(Enum):
    """Common failure modes in package testing."""
    LOW_LIMIT = "Below_Low_Limit"
    HIGH_LIMIT = "Above_High_Limit"
    FUNCTIONAL_FAIL = "Functional_Failure"
    TIMEOUT = "Test_Timeout"
    NO_CONTACT = "No_Electrical_Contact"
    INVALID_RESULT = "Invalid_Result"
    UNKNOWN = "Unknown_Failure"


@dataclass
class TestFlowStep:
    """Represents a step in the package test flow."""

    step_number: int
    test_number: int
    test_name: Optional[str] = None
    test_type: TestType = TestType.UNKNOWN
    typical_execution_time_ms: float = 0.0
    pass_requirement: bool = True  # True if test must pass to continue
    parallel_execution: bool = False  # True if can run in parallel with other tests


@dataclass
class TestFlow:
    """Complete package test flow definition."""

    flow_name: str
    flow_version: Optional[str] = None
    total_steps: int = 0
    estimated_test_time_ms: float = 0.0
    test_steps: List[TestFlowStep] = field(default_factory=list)
    critical_tests: Set[int] = field(default_factory=set)  # Tests that must pass
    optional_tests: Set[int] = field(default_factory=set)  # Tests that can be skipped


@dataclass
class FailureAnalysis:
    """Analysis of test failures for a specific test."""

    test_number: int
    test_name: Optional[str] = None
    total_executions: int = 0
    failure_count: int = 0
    failure_rate: float = 0.0
    failure_modes: Dict[FailureMode, int] = field(default_factory=dict)
    failing_parts: List[str] = field(default_factory=list)  # Part IDs
    statistical_summary: Dict[str, float] = field(default_factory=dict)


@dataclass
class BinCorrelation:
    """Correlation analysis between bins and test failures."""

    bin_number: int
    bin_name: Optional[str] = None
    part_count: int = 0
    primary_failing_tests: List[int] = field(default_factory=list)  # Most common failing tests
    test_failure_correlation: Dict[int, float] = field(default_factory=dict)  # test_num -> correlation
    common_failure_patterns: List[List[int]] = field(default_factory=list)  # Common test combinations


@dataclass
class YieldAnalysis:
    """Comprehensive yield analysis for package testing."""

    overall_yield: float = 0.0
    yield_by_site: Dict[str, float] = field(default_factory=dict)
    yield_by_bin: Dict[int, float] = field(default_factory=dict)
    yield_trend: List[Tuple[datetime, float]] = field(default_factory=list)  # Time-based yield
    first_pass_yield: float = 0.0  # Yield without retests
    final_yield: float = 0.0  # Yield after retests


@dataclass
class PackageTestMetrics:
    """Key package test metrics and KPIs."""

    # Yield metrics
    yield_analysis: YieldAnalysis = field(default_factory=YieldAnalysis)

    # Test execution metrics
    average_test_time_ms: float = 0.0
    test_time_variance: float = 0.0
    throughput_parts_per_hour: float = 0.0

    # Quality metrics
    defect_density: float = 0.0  # Defects per million opportunities
    test_escape_rate: float = 0.0  # Tests that should have failed but passed

    # Efficiency metrics
    test_coverage: float = 0.0  # Percentage of planned tests executed
    bin_utilization: float = 0.0  # Percentage of defined bins used
    site_utilization: float = 0.0  # Percentage of test sites active


class PackageTestAnalyzer:
    """
    Analyzer for package test data with domain-specific insights.

    Provides specialized analysis capabilities for package/final test
    data including yield analysis, failure correlation, and test optimization.
    """

    def __init__(self, stdf_data: STDFData):
        """
        Initialize analyzer with STDF data.

        Args:
            stdf_data: Parsed STDF data structure
        """
        self.stdf_data = stdf_data
        self._test_flow: Optional[TestFlow] = None
        self._failure_analyses: Dict[int, FailureAnalysis] = {}
        self._bin_correlations: Dict[int, BinCorrelation] = {}

    def analyze_yield(self) -> YieldAnalysis:
        """
        Perform comprehensive yield analysis.

        Returns:
            YieldAnalysis: Detailed yield analysis results
        """
        total_parts = len(self.stdf_data.part_results)
        if total_parts == 0:
            return YieldAnalysis()

        passing_parts = sum(1 for part in self.stdf_data.part_results if part.is_passing)
        overall_yield = (passing_parts / total_parts) * 100.0

        # Yield by site
        yield_by_site = {}
        site_parts = defaultdict(list)
        for part in self.stdf_data.part_results:
            site_parts[part.site_id].append(part)

        for site_id, parts in site_parts.items():
            site_passing = sum(1 for part in parts if part.is_passing)
            yield_by_site[site_id] = (site_passing / len(parts)) * 100.0 if parts else 0.0

        # Yield by bin (for pass bins only)
        yield_by_bin = {}
        for bin_num, bin_def in self.stdf_data.hard_bins.items():
            if bin_def.is_pass_bin and bin_def.part_count > 0:
                yield_by_bin[bin_num] = (bin_def.part_count / total_parts) * 100.0

        return YieldAnalysis(
            overall_yield=overall_yield,
            yield_by_site=yield_by_site,
            yield_by_bin=yield_by_bin,
            first_pass_yield=overall_yield,  # Simplified - would need retest analysis
            final_yield=overall_yield
        )

    def analyze_test_failures(self) -> Dict[int, FailureAnalysis]:
        """
        Analyze failure patterns for each test.

        Returns:
            Dict[int, FailureAnalysis]: Test number to failure analysis mapping
        """
        if self._failure_analyses:
            return self._failure_analyses

        # Group test results by test number
        test_results_by_num = defaultdict(list)
        for part in self.stdf_data.part_results:
            for test_result in part.test_results:
                test_results_by_num[test_result.test_num].append(test_result)

        # Analyze each test
        for test_num, results in test_results_by_num.items():
            analysis = self._analyze_single_test_failures(test_num, results)
            self._failure_analyses[test_num] = analysis

        return self._failure_analyses

    def _analyze_single_test_failures(self, test_num: int, results: List[TestResult]) -> FailureAnalysis:
        """Analyze failures for a single test."""
        total_executions = len(results)
        failing_results = [r for r in results if not r.passing]
        failure_count = len(failing_results)

        failure_rate = (failure_count / total_executions) * 100.0 if total_executions > 0 else 0.0

        # Classify failure modes
        failure_modes = defaultdict(int)
        failing_parts = []

        for result in failing_results:
            failing_parts.append(result.part_id or "Unknown")

            # Determine failure mode
            if result.result_value is not None:
                if result.low_limit is not None and result.result_value < result.low_limit:
                    failure_modes[FailureMode.LOW_LIMIT] += 1
                elif result.high_limit is not None and result.result_value > result.high_limit:
                    failure_modes[FailureMode.HIGH_LIMIT] += 1
                else:
                    failure_modes[FailureMode.FUNCTIONAL_FAIL] += 1
            else:
                failure_modes[FailureMode.INVALID_RESULT] += 1

        # Statistical summary
        values = [r.result_value for r in results if r.result_value is not None]
        statistical_summary = {}
        if values:
            statistical_summary = {
                'mean': statistics.mean(values),
                'median': statistics.median(values),
                'stdev': statistics.stdev(values) if len(values) > 1 else 0.0,
                'min': min(values),
                'max': max(values)
            }

        test_def = self.stdf_data.test_definitions.get(test_num)
        test_name = test_def.test_name if test_def else None

        return FailureAnalysis(
            test_number=test_num,
            test_name=test_name,
            total_executions=total_executions,
            failure_count=failure_count,
            failure_rate=failure_rate,
            failure_modes=dict(failure_modes),
            failing_parts=failing_parts,
            statistical_summary=statistical_summary
        )

    def analyze_bin_correlations(self) -> Dict[int, BinCorrelation]:
        """
        Analyze correlations between bins and test failures.

        Returns:
            Dict[int, BinCorrelation]: Bin number to correlation analysis mapping
        """
        if self._bin_correlations:
            return self._bin_correlations

        # Group parts by hard bin
        parts_by_bin = defaultdict(list)
        for part in self.stdf_data.part_results:
            parts_by_bin[part.hard_bin].append(part)

        # Analyze each bin
        for bin_num, parts in parts_by_bin.items():
            if not parts:
                continue

            correlation = self._analyze_bin_test_correlation(bin_num, parts)
            self._bin_correlations[bin_num] = correlation

        return self._bin_correlations

    def _analyze_bin_test_correlation(self, bin_num: int, parts: List[PartResult]) -> BinCorrelation:
        """Analyze test failure correlations for a specific bin."""
        bin_def = self.stdf_data.hard_bins.get(bin_num)
        bin_name = bin_def.bin_name if bin_def else None

        # Count test failures for parts in this bin
        test_failure_counts = defaultdict(int)
        total_test_executions = defaultdict(int)

        for part in parts:
            for test_result in part.test_results:
                total_test_executions[test_result.test_num] += 1
                if not test_result.passing:
                    test_failure_counts[test_result.test_num] += 1

        # Calculate correlation (failure rate for this bin vs overall)
        test_failure_correlation = {}
        for test_num, failure_count in test_failure_counts.items():
            executions = total_test_executions[test_num]
            if executions > 0:
                bin_failure_rate = failure_count / executions
                # Compare to overall failure rate for this test
                overall_analysis = self._failure_analyses.get(test_num)
                if overall_analysis and overall_analysis.total_executions > 0:
                    overall_failure_rate = overall_analysis.failure_count / overall_analysis.total_executions
                    if overall_failure_rate > 0:
                        correlation = bin_failure_rate / overall_failure_rate
                        test_failure_correlation[test_num] = correlation

        # Find primary failing tests (highest correlation)
        primary_failing_tests = sorted(test_failure_correlation.keys(),
                                     key=lambda t: test_failure_correlation[t],
                                     reverse=True)[:5]

        return BinCorrelation(
            bin_number=bin_num,
            bin_name=bin_name,
            part_count=len(parts),
            primary_failing_tests=primary_failing_tests,
            test_failure_correlation=test_failure_correlation
        )

    def generate_test_metrics(self) -> PackageTestMetrics:
        """
        Generate comprehensive package test metrics.

        Returns:
            PackageTestMetrics: Complete metrics analysis
        """
        # Yield analysis
        yield_analysis = self.analyze_yield()

        # Test execution metrics
        test_times = [part.test_time_ms for part in self.stdf_data.part_results
                     if part.test_time_ms is not None]

        avg_test_time = statistics.mean(test_times) if test_times else 0.0
        test_time_variance = statistics.variance(test_times) if len(test_times) > 1 else 0.0

        # Throughput calculation (rough estimate)
        throughput = 0.0
        if avg_test_time > 0:
            throughput = (3600 * 1000) / avg_test_time  # Parts per hour

        # Test coverage
        planned_tests = len(self.stdf_data.test_definitions)
        executed_tests = sum(1 for td in self.stdf_data.test_definitions.values()
                           if td.execution_count > 0)
        test_coverage = (executed_tests / planned_tests) * 100.0 if planned_tests > 0 else 0.0

        # Bin utilization
        defined_bins = len(self.stdf_data.hard_bins)
        used_bins = sum(1 for bd in self.stdf_data.hard_bins.values() if bd.part_count > 0)
        bin_utilization = (used_bins / defined_bins) * 100.0 if defined_bins > 0 else 0.0

        # Site utilization
        defined_sites = len(self.stdf_data.test_sites)
        active_sites = sum(1 for si in self.stdf_data.test_sites.values()
                          if si.total_parts_tested > 0)
        site_utilization = (active_sites / defined_sites) * 100.0 if defined_sites > 0 else 0.0

        return PackageTestMetrics(
            yield_analysis=yield_analysis,
            average_test_time_ms=avg_test_time,
            test_time_variance=test_time_variance,
            throughput_parts_per_hour=throughput,
            test_coverage=test_coverage,
            bin_utilization=bin_utilization,
            site_utilization=site_utilization
        )

    def get_top_failing_tests(self, limit: int = 10) -> List[FailureAnalysis]:
        """
        Get top failing tests by failure rate.

        Args:
            limit: Maximum number of tests to return

        Returns:
            List[FailureAnalysis]: Top failing tests
        """
        self.analyze_test_failures()  # Ensure analysis is done

        failing_tests = [analysis for analysis in self._failure_analyses.values()
                        if analysis.failure_count > 0]

        return sorted(failing_tests, key=lambda x: x.failure_rate, reverse=True)[:limit]

    def get_bin_efficiency_report(self) -> Dict[str, Any]:
        """
        Generate bin efficiency report.

        Returns:
            Dict[str, Any]: Bin efficiency analysis
        """
        total_parts = len(self.stdf_data.part_results)
        if total_parts == 0:
            return {}

        bin_report = {
            'total_bins_defined': len(self.stdf_data.hard_bins),
            'total_bins_used': sum(1 for bd in self.stdf_data.hard_bins.values()
                                 if bd.part_count > 0),
            'pass_bins': [],
            'fail_bins': [],
            'unused_bins': []
        }

        for bin_num, bin_def in self.stdf_data.hard_bins.items():
            bin_info = {
                'bin_number': bin_num,
                'bin_name': bin_def.bin_name,
                'part_count': bin_def.part_count,
                'percentage': (bin_def.part_count / total_parts) * 100.0
            }

            if bin_def.part_count == 0:
                bin_report['unused_bins'].append(bin_info)
            elif bin_def.is_pass_bin:
                bin_report['pass_bins'].append(bin_info)
            else:
                bin_report['fail_bins'].append(bin_info)

        return bin_report

    def generate_package_test_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive package test summary.

        Returns:
            Dict[str, Any]: Complete package test analysis summary
        """
        metrics = self.generate_test_metrics()
        top_failing_tests = self.get_top_failing_tests(5)
        bin_report = self.get_bin_efficiency_report()

        return {
            'yield_analysis': {
                'overall_yield': metrics.yield_analysis.overall_yield,
                'yield_by_site': metrics.yield_analysis.yield_by_site,
                'first_pass_yield': metrics.yield_analysis.first_pass_yield
            },
            'test_execution': {
                'average_test_time_ms': metrics.average_test_time_ms,
                'throughput_pph': metrics.throughput_parts_per_hour,
                'test_coverage': metrics.test_coverage
            },
            'failure_analysis': {
                'top_failing_tests': [
                    {
                        'test_number': fa.test_number,
                        'test_name': fa.test_name,
                        'failure_rate': fa.failure_rate,
                        'failure_count': fa.failure_count
                    } for fa in top_failing_tests
                ]
            },
            'bin_analysis': bin_report,
            'quality_metrics': {
                'bin_utilization': metrics.bin_utilization,
                'site_utilization': metrics.site_utilization
            }
        }