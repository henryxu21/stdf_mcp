"""
Statistical analysis utilities for STDF-V4 data.

This module provides comprehensive statistical analysis capabilities
for test data including descriptive statistics, distribution analysis,
correlation analysis, and outlier detection.
"""

import math
import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any, Union
from collections import defaultdict
from enum import Enum

from .stdf_data import STDFData, TestResult, PartResult


class DistributionType(Enum):
    """Statistical distribution types."""
    NORMAL = "Normal"
    UNIFORM = "Uniform"
    BIMODAL = "Bimodal"
    SKEWED_LEFT = "Skewed_Left"
    SKEWED_RIGHT = "Skewed_Right"
    UNKNOWN = "Unknown"


@dataclass
class DescriptiveStats:
    """Descriptive statistics for a dataset."""

    count: int = 0
    mean: float = 0.0
    median: float = 0.0
    mode: Optional[float] = None
    std_dev: float = 0.0
    variance: float = 0.0
    min_value: float = 0.0
    max_value: float = 0.0
    range_value: float = 0.0
    q1: float = 0.0  # First quartile
    q3: float = 0.0  # Third quartile
    iqr: float = 0.0  # Interquartile range
    skewness: float = 0.0
    kurtosis: float = 0.0
    coefficient_of_variation: float = 0.0


@dataclass
class DistributionAnalysis:
    """Distribution analysis results."""

    distribution_type: DistributionType = DistributionType.UNKNOWN
    normality_test_p_value: Optional[float] = None
    is_normal: bool = False
    outlier_count: int = 0
    outlier_indices: List[int] = field(default_factory=list)
    outlier_values: List[float] = field(default_factory=list)
    percentiles: Dict[int, float] = field(default_factory=dict)


@dataclass
class CorrelationAnalysis:
    """Correlation analysis between tests."""

    test1_num: int
    test2_num: int
    test1_name: Optional[str] = None
    test2_name: Optional[str] = None
    correlation_coefficient: float = 0.0
    correlation_strength: str = "None"  # Weak, Moderate, Strong
    p_value: Optional[float] = None
    sample_size: int = 0


@dataclass
class TestStatistics:
    """Complete statistical analysis for a test."""

    test_number: int
    test_name: Optional[str] = None
    descriptive_stats: DescriptiveStats = field(default_factory=DescriptiveStats)
    distribution_analysis: DistributionAnalysis = field(default_factory=DistributionAnalysis)
    pass_rate: float = 0.0
    within_limits_rate: float = 0.0
    cpk: Optional[float] = None  # Process capability index
    cp: Optional[float] = None   # Process capability
    sigma_level: Optional[float] = None


@dataclass
class YieldStatistics:
    """Yield-related statistical analysis."""

    overall_yield: float = 0.0
    yield_by_site: Dict[str, float] = field(default_factory=dict)
    yield_by_bin: Dict[int, float] = field(default_factory=dict)
    yield_confidence_interval: Tuple[float, float] = (0.0, 0.0)
    yield_standard_error: float = 0.0


class StatisticalAnalyzer:
    """
    Comprehensive statistical analyzer for STDF data.

    Provides various statistical analysis capabilities including
    descriptive statistics, distribution analysis, correlation
    analysis, and process capability studies.
    """

    def __init__(self, stdf_data: STDFData):
        """
        Initialize statistical analyzer.

        Args:
            stdf_data: STDF data structure to analyze
        """
        self.stdf_data = stdf_data

    def calculate_descriptive_stats(self, values: List[float]) -> DescriptiveStats:
        """
        Calculate descriptive statistics for a list of values.

        Args:
            values: List of numeric values

        Returns:
            DescriptiveStats: Comprehensive descriptive statistics
        """
        if not values:
            return DescriptiveStats()

        # Remove None values and sort
        clean_values = [v for v in values if v is not None]
        if not clean_values:
            return DescriptiveStats()

        clean_values.sort()
        n = len(clean_values)

        # Basic statistics
        mean_val = statistics.mean(clean_values)
        median_val = statistics.median(clean_values)

        # Mode (most common value, if exists)
        mode_val = None
        try:
            mode_val = statistics.mode(clean_values)
        except statistics.StatisticsError:
            pass  # No unique mode

        # Variance and standard deviation
        if n > 1:
            variance_val = statistics.variance(clean_values)
            std_dev_val = statistics.stdev(clean_values)
        else:
            variance_val = 0.0
            std_dev_val = 0.0

        # Min, max, range
        min_val = min(clean_values)
        max_val = max(clean_values)
        range_val = max_val - min_val

        # Quartiles
        q1 = self._calculate_percentile(clean_values, 25)
        q3 = self._calculate_percentile(clean_values, 75)
        iqr = q3 - q1

        # Skewness and kurtosis
        skewness_val = self._calculate_skewness(clean_values, mean_val, std_dev_val)
        kurtosis_val = self._calculate_kurtosis(clean_values, mean_val, std_dev_val)

        # Coefficient of variation
        cv = (std_dev_val / mean_val) * 100.0 if mean_val != 0 else 0.0

        return DescriptiveStats(
            count=n,
            mean=mean_val,
            median=median_val,
            mode=mode_val,
            std_dev=std_dev_val,
            variance=variance_val,
            min_value=min_val,
            max_value=max_val,
            range_value=range_val,
            q1=q1,
            q3=q3,
            iqr=iqr,
            skewness=skewness_val,
            kurtosis=kurtosis_val,
            coefficient_of_variation=cv
        )

    def _calculate_percentile(self, sorted_values: List[float], percentile: int) -> float:
        """Calculate percentile value."""
        if not sorted_values:
            return 0.0

        n = len(sorted_values)
        k = (percentile / 100.0) * (n - 1)

        if k == int(k):
            return sorted_values[int(k)]
        else:
            lower = sorted_values[int(k)]
            upper = sorted_values[int(k) + 1]
            return lower + (k - int(k)) * (upper - lower)

    def _calculate_skewness(self, values: List[float], mean: float, std_dev: float) -> float:
        """Calculate skewness coefficient."""
        if std_dev == 0 or len(values) < 3:
            return 0.0

        n = len(values)
        sum_cubed_deviations = sum((x - mean) ** 3 for x in values)
        return (n * sum_cubed_deviations) / ((n - 1) * (n - 2) * (std_dev ** 3))

    def _calculate_kurtosis(self, values: List[float], mean: float, std_dev: float) -> float:
        """Calculate kurtosis coefficient."""
        if std_dev == 0 or len(values) < 4:
            return 0.0

        n = len(values)
        sum_fourth_deviations = sum((x - mean) ** 4 for x in values)
        kurtosis = (n * (n + 1) * sum_fourth_deviations) / ((n - 1) * (n - 2) * (n - 3) * (std_dev ** 4))
        return kurtosis - 3.0  # Excess kurtosis (normal = 0)

    def analyze_distribution(self, values: List[float]) -> DistributionAnalysis:
        """
        Analyze data distribution characteristics.

        Args:
            values: List of numeric values

        Returns:
            DistributionAnalysis: Distribution analysis results
        """
        if not values:
            return DistributionAnalysis()

        clean_values = [v for v in values if v is not None]
        if len(clean_values) < 3:
            return DistributionAnalysis()

        # Calculate descriptive stats first
        desc_stats = self.calculate_descriptive_stats(clean_values)

        # Outlier detection using IQR method
        outlier_indices, outlier_values = self._detect_outliers_iqr(clean_values, desc_stats)

        # Distribution type classification
        dist_type = self._classify_distribution(desc_stats)

        # Normality assessment (simplified)
        is_normal = self._assess_normality(desc_stats)

        # Calculate percentiles
        percentiles = {}
        for p in [5, 10, 25, 50, 75, 90, 95, 99]:
            percentiles[p] = self._calculate_percentile(sorted(clean_values), p)

        return DistributionAnalysis(
            distribution_type=dist_type,
            is_normal=is_normal,
            outlier_count=len(outlier_indices),
            outlier_indices=outlier_indices,
            outlier_values=outlier_values,
            percentiles=percentiles
        )

    def _detect_outliers_iqr(self, values: List[float], stats: DescriptiveStats) -> Tuple[List[int], List[float]]:
        """Detect outliers using IQR method."""
        if stats.iqr == 0:
            return [], []

        lower_bound = stats.q1 - 1.5 * stats.iqr
        upper_bound = stats.q3 + 1.5 * stats.iqr

        outlier_indices = []
        outlier_values = []

        for i, value in enumerate(values):
            if value < lower_bound or value > upper_bound:
                outlier_indices.append(i)
                outlier_values.append(value)

        return outlier_indices, outlier_values

    def _classify_distribution(self, stats: DescriptiveStats) -> DistributionType:
        """Classify distribution type based on statistics."""
        # Simple classification based on skewness and kurtosis
        skew = abs(stats.skewness)
        kurt = abs(stats.kurtosis)

        if skew < 0.5 and kurt < 2.0:
            return DistributionType.NORMAL
        elif stats.skewness > 1.0:
            return DistributionType.SKEWED_RIGHT
        elif stats.skewness < -1.0:
            return DistributionType.SKEWED_LEFT
        elif kurt > 3.0:
            return DistributionType.BIMODAL
        else:
            return DistributionType.UNKNOWN

    def _assess_normality(self, stats: DescriptiveStats) -> bool:
        """Simple normality assessment based on skewness and kurtosis."""
        return abs(stats.skewness) < 1.0 and abs(stats.kurtosis) < 2.0

    def analyze_test_statistics(self, test_num: int) -> TestStatistics:
        """
        Analyze statistics for a specific test.

        Args:
            test_num: Test number to analyze

        Returns:
            TestStatistics: Complete test statistical analysis
        """
        # Collect all results for this test
        test_results = []
        for part in self.stdf_data.part_results:
            for result in part.test_results:
                if result.test_num == test_num:
                    test_results.append(result)

        if not test_results:
            return TestStatistics(test_number=test_num)

        # Extract values and analyze
        values = [r.result_value for r in test_results if r.result_value is not None]
        descriptive_stats = self.calculate_descriptive_stats(values)
        distribution_analysis = self.analyze_distribution(values)

        # Calculate pass rate
        passing_results = sum(1 for r in test_results if r.passing)
        pass_rate = (passing_results / len(test_results)) * 100.0

        # Calculate within limits rate
        within_limits_results = sum(1 for r in test_results if r.within_limits)
        within_limits_rate = (within_limits_results / len(test_results)) * 100.0

        # Process capability (if limits available)
        cpk, cp, sigma_level = self._calculate_process_capability(test_results, descriptive_stats)

        # Get test name
        test_def = self.stdf_data.test_definitions.get(test_num)
        test_name = test_def.test_name if test_def else None

        return TestStatistics(
            test_number=test_num,
            test_name=test_name,
            descriptive_stats=descriptive_stats,
            distribution_analysis=distribution_analysis,
            pass_rate=pass_rate,
            within_limits_rate=within_limits_rate,
            cpk=cpk,
            cp=cp,
            sigma_level=sigma_level
        )

    def _calculate_process_capability(self, test_results: List[TestResult],
                                    stats: DescriptiveStats) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Calculate process capability indices."""
        if not test_results or stats.std_dev == 0:
            return None, None, None

        # Get limits from first result (assuming consistent)
        low_limit = None
        high_limit = None
        for result in test_results:
            if result.low_limit is not None:
                low_limit = result.low_limit
            if result.high_limit is not None:
                high_limit = result.high_limit
            if low_limit is not None and high_limit is not None:
                break

        if low_limit is None or high_limit is None:
            return None, None, None

        # Calculate Cp (process potential)
        spec_width = high_limit - low_limit
        process_width = 6 * stats.std_dev
        cp = spec_width / process_width if process_width > 0 else None

        # Calculate Cpk (process capability)
        cpu = (high_limit - stats.mean) / (3 * stats.std_dev)  # Upper capability
        cpl = (stats.mean - low_limit) / (3 * stats.std_dev)   # Lower capability
        cpk = min(cpu, cpl)

        # Sigma level approximation
        sigma_level = cpk * 3 + 1.5 if cpk is not None else None

        return cpk, cp, sigma_level

    def calculate_correlation_matrix(self, test_numbers: List[int]) -> Dict[Tuple[int, int], float]:
        """
        Calculate correlation matrix for specified tests.

        Args:
            test_numbers: List of test numbers to correlate

        Returns:
            Dict[Tuple[int, int], float]: Correlation coefficients
        """
        # Collect test result data
        test_data = {}
        for test_num in test_numbers:
            values = []
            for part in self.stdf_data.part_results:
                for result in part.test_results:
                    if result.test_num == test_num and result.result_value is not None:
                        values.append(result.result_value)
            test_data[test_num] = values

        # Calculate correlations
        correlations = {}
        for i, test1 in enumerate(test_numbers):
            for test2 in test_numbers[i+1:]:
                if test1 in test_data and test2 in test_data:
                    correlation = self._calculate_correlation(test_data[test1], test_data[test2])
                    correlations[(test1, test2)] = correlation

        return correlations

    def _calculate_correlation(self, x_values: List[float], y_values: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        if len(x_values) != len(y_values) or len(x_values) < 2:
            return 0.0

        # Align datasets (in case of different lengths)
        min_len = min(len(x_values), len(y_values))
        x = x_values[:min_len]
        y = y_values[:min_len]

        # Calculate correlation
        try:
            n = len(x)
            sum_x = sum(x)
            sum_y = sum(y)
            sum_xy = sum(x[i] * y[i] for i in range(n))
            sum_x_sq = sum(xi ** 2 for xi in x)
            sum_y_sq = sum(yi ** 2 for yi in y)

            numerator = n * sum_xy - sum_x * sum_y
            denominator = math.sqrt((n * sum_x_sq - sum_x ** 2) * (n * sum_y_sq - sum_y ** 2))

            return numerator / denominator if denominator != 0 else 0.0

        except (ValueError, ZeroDivisionError):
            return 0.0

    def analyze_yield_statistics(self) -> YieldStatistics:
        """
        Analyze yield-related statistics.

        Returns:
            YieldStatistics: Comprehensive yield analysis
        """
        total_parts = len(self.stdf_data.part_results)
        if total_parts == 0:
            return YieldStatistics()

        passing_parts = sum(1 for part in self.stdf_data.part_results if part.is_passing)
        overall_yield = (passing_parts / total_parts) * 100.0

        # Yield by site
        yield_by_site = {}
        site_parts = defaultdict(list)
        for part in self.stdf_data.part_results:
            site_parts[part.site_id].append(part)

        for site_id, parts in site_parts.items():
            site_passing = sum(1 for part in parts if part.is_passing)
            yield_by_site[site_id] = (site_passing / len(parts)) * 100.0

        # Yield by bin
        yield_by_bin = {}
        bin_parts = defaultdict(int)
        for part in self.stdf_data.part_results:
            bin_parts[part.hard_bin] += 1

        for bin_num, count in bin_parts.items():
            bin_def = self.stdf_data.hard_bins.get(bin_num)
            if bin_def and bin_def.is_pass_bin:
                yield_by_bin[bin_num] = (count / total_parts) * 100.0

        # Yield confidence interval (95% confidence)
        p = overall_yield / 100.0
        std_error = math.sqrt(p * (1 - p) / total_parts) if total_parts > 0 else 0.0
        margin_of_error = 1.96 * std_error * 100.0  # 95% confidence

        confidence_interval = (
            max(0.0, overall_yield - margin_of_error),
            min(100.0, overall_yield + margin_of_error)
        )

        return YieldStatistics(
            overall_yield=overall_yield,
            yield_by_site=yield_by_site,
            yield_by_bin=yield_by_bin,
            yield_confidence_interval=confidence_interval,
            yield_standard_error=std_error * 100.0
        )

    def generate_statistical_summary(self) -> Dict[str, Any]:
        """
        Generate comprehensive statistical summary.

        Returns:
            Dict[str, Any]: Complete statistical analysis summary
        """
        # Analyze key tests
        test_analyses = {}
        for test_num in list(self.stdf_data.test_definitions.keys())[:10]:  # Limit to first 10 tests
            test_analyses[test_num] = self.analyze_test_statistics(test_num)

        # Yield statistics
        yield_stats = self.analyze_yield_statistics()

        # Overall statistics
        total_parts = len(self.stdf_data.part_results)
        total_tests = len(self.stdf_data.test_definitions)

        return {
            'summary': {
                'total_parts_analyzed': total_parts,
                'total_tests_analyzed': total_tests,
                'overall_yield': yield_stats.overall_yield,
                'yield_confidence_interval': yield_stats.yield_confidence_interval
            },
            'yield_statistics': {
                'overall_yield': yield_stats.overall_yield,
                'yield_by_site': yield_stats.yield_by_site,
                'yield_standard_error': yield_stats.yield_standard_error
            },
            'test_statistics': {
                test_num: {
                    'test_name': analysis.test_name,
                    'mean': analysis.descriptive_stats.mean,
                    'std_dev': analysis.descriptive_stats.std_dev,
                    'pass_rate': analysis.pass_rate,
                    'cpk': analysis.cpk,
                    'distribution_type': analysis.distribution_analysis.distribution_type.value,
                    'outlier_count': analysis.distribution_analysis.outlier_count
                }
                for test_num, analysis in test_analyses.items()
            }
        }