"""
Advanced Statistical Validation Engine for Stories Malik
Phase 20: Mathematical Rigor, Sample-Size Policies, Confidence Intervals & Outlier Detection.

Enforces:
1. Strict sample-size policies (N < 3: insufficient, 3 <= N < 5: preliminary, 5 <= N < 10: moderate, N >= 10: sound).
2. Outlier detection using Interquartile Range (IQR) and standard deviation thresholds.
3. Duration-adjusted metrics: Watch Time per Minute of Video Duration (WPMD) and normalized APV.
4. Welch's two-sample t-statistic and approximate p-value computation for variant comparisons.
5. 95% Confidence Intervals for means and proportions.
6. Time-since-publication normalization (preventing day-1 videos from being compared against mature 28d videos).
7. Missing-data and delayed analytics safeguards.
"""
import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple


SAMPLE_SIZE_POLICIES = {
    "insufficient": {"min_n": 0, "max_n": 2, "label": "Insufficient Data (N < 3)", "allow_conclusions": False},
    "preliminary": {"min_n": 3, "max_n": 4, "label": "Preliminary Directional Trend (3 <= N < 5)", "allow_conclusions": False},
    "moderate": {"min_n": 5, "max_n": 9, "label": "Moderate Confidence (5 <= N < 10)", "allow_conclusions": True},
    "statistically_sound": {"min_n": 10, "max_n": 999999, "label": "Statistically Sound (N >= 10)", "allow_conclusions": True},
}


def get_sample_policy(n: int) -> Dict[str, Any]:
    """Returns sample-size governance tier and whether definitive conclusions are permissible."""
    if n < 3:
        return SAMPLE_SIZE_POLICIES["insufficient"]
    elif n < 5:
        return SAMPLE_SIZE_POLICIES["preliminary"]
    elif n < 10:
        return SAMPLE_SIZE_POLICIES["moderate"]
    return SAMPLE_SIZE_POLICIES["statistically_sound"]


def detect_outliers_iqr(values: List[float], k: float = 1.5) -> Tuple[List[float], List[float]]:
    """
    Identifies outliers using the Interquartile Range (IQR) method.
    Returns (cleaned_values, outliers).
    """
    if len(values) < 4:
        return list(values), []

    sorted_vals = sorted(values)
    n = len(sorted_vals)
    q1 = sorted_vals[n // 4]
    q3 = sorted_vals[(3 * n) // 4]
    iqr = q3 - q1

    lower_bound = q1 - k * iqr
    upper_bound = q3 + k * iqr

    cleaned = [x for x in values if lower_bound <= x <= upper_bound]
    outliers = [x for x in values if x < lower_bound or x > upper_bound]
    return cleaned, outliers


def calculate_mean_and_confidence_interval(
    values: List[float],
    confidence: float = 0.95,
) -> Dict[str, Any]:
    """
    Computes sample mean, sample standard deviation, and (1 - alpha) confidence interval.
    Uses t-critical approximation for small samples (1.96 for large N).
    """
    if not values:
        return {
            "n": 0,
            "mean": 0.0,
            "std_dev": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "margin_of_error": 0.0,
            "policy": SAMPLE_SIZE_POLICIES["insufficient"]["label"],
        }

    n = len(values)
    mean = sum(values) / n

    if n == 1:
        return {
            "n": 1,
            "mean": round(mean, 2),
            "std_dev": 0.0,
            "ci_lower": round(mean, 2),
            "ci_upper": round(mean, 2),
            "margin_of_error": 0.0,
            "policy": SAMPLE_SIZE_POLICIES["insufficient"]["label"],
        }

    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    std_dev = math.sqrt(variance)

    # Approximate t-critical values for 95% two-tailed CI
    t_table = {2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262}
    t_crit = t_table.get(n - 1, 1.96 if n >= 30 else 2.10)

    margin_of_error = t_crit * (std_dev / math.sqrt(n))

    return {
        "n": n,
        "mean": round(mean, 2),
        "std_dev": round(std_dev, 2),
        "ci_lower": round(max(0.0, mean - margin_of_error), 2),
        "ci_upper": round(mean + margin_of_error, 2),
        "margin_of_error": round(margin_of_error, 2),
        "policy": get_sample_policy(n)["label"],
    }


def compute_duration_adjusted_watch_time(
    watch_time_minutes: float,
    duration_seconds: float,
) -> float:
    """
    Computes Watch Time Efficiency: Watch Time per Minute of Video Duration (WPMD).
    Accounts for length disparity so a 13-minute video is not falsely favored over an 8-minute video.
    WPMD = watch_time_minutes / (duration_seconds / 60.0)
    """
    if duration_seconds <= 0 or watch_time_minutes <= 0:
        return 0.0
    video_minutes = duration_seconds / 60.0
    return round(watch_time_minutes / video_minutes, 2)


def compute_welch_t_test(
    sample_control: List[float],
    sample_test: List[float],
) -> Dict[str, Any]:
    """
    Computes Welch's Two-Sample t-test for unequal variances and sample sizes.
    Returns t_stat, degrees_of_freedom, approximate p_value, and statistical significance flag.
    """
    n1, n2 = len(sample_control), len(sample_test)
    if n1 < 3 or n2 < 3:
        return {
            "valid_test": False,
            "message": f"Insufficient sample sizes for t-test (Control: {n1}, Test: {n2}; min 3 each required).",
            "t_stat": 0.0,
            "p_value": 1.0,
            "is_significant": False,
        }

    mean1 = sum(sample_control) / n1
    mean2 = sum(sample_test) / n2

    var1 = sum((x - mean1) ** 2 for x in sample_control) / (n1 - 1)
    var2 = sum((x - mean2) ** 2 for x in sample_test) / (n2 - 1)

    # Avoid zero division
    se = math.sqrt((var1 / n1) + (var2 / n2))
    if se == 0:
        return {
            "valid_test": True,
            "t_stat": 0.0,
            "p_value": 1.0,
            "is_significant": False,
            "mean_control": round(mean1, 2),
            "mean_test": round(mean2, 2),
        }

    t_stat = (mean2 - mean1) / se

    # Welch–Satterthwaite equation for degrees of freedom
    numerator = ((var1 / n1) + (var2 / n2)) ** 2
    denominator = ((var1 / n1) ** 2 / (n1 - 1)) + ((var2 / n2) ** 2 / (n2 - 1))
    df = round(numerator / denominator, 1) if denominator > 0 else 1.0

    # Approximate two-tailed p-value from standard normal for df >= 4
    # (using complementary error function approximation)
    abs_t = abs(t_stat)
    p_approx = math.erfc(abs_t / math.sqrt(2))

    is_significant = p_approx < 0.05 and (n1 + n2 >= 6)

    return {
        "valid_test": True,
        "n_control": n1,
        "n_test": n2,
        "mean_control": round(mean1, 2),
        "mean_test": round(mean2, 2),
        "delta": round(mean2 - mean1, 2),
        "t_stat": round(t_stat, 3),
        "df": df,
        "p_value": round(p_approx, 4),
        "is_significant": is_significant,
        "significance_statement": (
            f"Statistically significant difference (p = {p_approx:.4f} < 0.05, t = {t_stat:.2f})"
            if is_significant
            else f"No statistically significant difference observed (p = {p_approx:.4f} >= 0.05, t = {t_stat:.2f})"
        ),
    }


def normalize_views_by_age(views: int, days_since_publication: float) -> float:
    """
    Normalizes view count by days active using logarithmic decay curve:
    Velocity = views / ln(days_active + 2)
    Prevents comparing 2-day-old newly uploaded videos directly with 90-day-old mature videos.
    """
    days = max(0.1, float(days_since_publication))
    decay_factor = math.log(days + 2.0)
    return round(views / decay_factor, 1)


def calculate_median(values: List[float]) -> float:
    """Computes exact median of numeric values, returning 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(float(v) for v in values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return round(ordered[mid], 2)
    return round((ordered[mid - 1] + ordered[mid]) / 2.0, 2)


def compute_publication_age_days(
    publication_timestamp: Optional[str],
    reference_time: Optional[datetime] = None,
) -> Optional[float]:
    """
    Computes video publication age in days relative to `reference_time` (UTC).
    Returns None if timestamp is missing or unparseable.
    """
    if not publication_timestamp:
        return None
    try:
        dt = datetime.fromisoformat(str(publication_timestamp).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ref = reference_time or datetime.now(timezone.utc)
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)
        delta_days = (ref - dt).total_seconds() / 86400.0
        return round(max(0.05, delta_days), 2)
    except Exception:
        return None
