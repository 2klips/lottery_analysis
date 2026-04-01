"""Advanced statistical analysis for Pension Lottery 720+ prediction improvement."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass

from ..models.lottery import PensionRound


@dataclass
class EntropyResult:
    """Entropy analysis result for one digit position."""
    position: int
    is_bonus: bool
    shannon_entropy: float
    max_entropy: float
    normalized_entropy: float
    most_biased_digit: int
    bias_strength: float

@dataclass
class CorrelationResult:
    """Cross-position correlation matrix result."""
    cramers_v_matrix: list[list[float]]
    significant_pairs: list[tuple[int, int, float]]

@dataclass
class AutocorrelationResult:
    """Autocorrelation result for one position."""
    position: int
    lag_scores: dict[int, float]
    significant_lags: list[int]

@dataclass
class SeasonalResult:
    """Monthly and weekday digit bias result."""
    monthly_bias: dict[int, dict[int, float]]
    weekday_bias: dict[int, dict[int, float]]
    strongest_monthly: tuple[int, int, float]
    strongest_weekday: tuple[int, int, float]

@dataclass
class TrendResult:
    """Recent-vs-historical trend result for one digit."""
    position: int
    digit: int
    trend_direction: str
    recent_rate: float
    historical_rate: float
    momentum: float

@dataclass
class AdvancedAnalysisReport:
    """Complete advanced analysis report."""
    entropy_results: list[EntropyResult]
    correlation: CorrelationResult
    autocorrelation_results: list[AutocorrelationResult]
    seasonal: SeasonalResult
    trend_results: list[TrendResult]

class AdvancedAnalyzer:
    """Advanced statistical analyzer for lottery data."""

    def __init__(self, rounds: list[PensionRound]) -> None:
        """Initialize the analyzer with historical rounds."""
        if not rounds:
            msg = "rounds must not be empty"
            raise ValueError(msg)
        self.rounds = sorted(rounds, key=lambda item: item.round_number)

    def full_analysis(self) -> AdvancedAnalysisReport:
        """Run all analyses and return a comprehensive report."""
        return AdvancedAnalysisReport(
            entropy_results=[self.analyze_entropy(position) for position in range(6)]
            + [self.analyze_entropy(position, is_bonus=True) for position in range(6)],
            correlation=self.analyze_correlation(),
            autocorrelation_results=[self.analyze_autocorrelation(position) for position in range(6)],
            seasonal=self.analyze_seasonal(),
            trend_results=self.analyze_trends(),
        )

    def analyze_entropy(self, position: int, is_bonus: bool = False) -> EntropyResult:
        """Calculate Shannon entropy for one digit position."""
        self._validate_position(position)
        digits = self._position_values(position, is_bonus)
        counts = Counter(digits)
        total = len(digits)
        max_entropy = math.log2(10)
        entropy = -sum((count / total) * math.log2(count / total) for count in counts.values())
        deviations = {digit: abs(counts.get(digit, 0) / total - 0.1) for digit in range(10)}
        biased_digit = max(range(10), key=lambda digit: (deviations[digit], -digit))
        return EntropyResult(
            position=position,
            is_bonus=is_bonus,
            shannon_entropy=entropy,
            max_entropy=max_entropy,
            normalized_entropy=entropy / max_entropy,
            most_biased_digit=biased_digit,
            bias_strength=deviations[biased_digit],
        )

    def analyze_correlation(self, is_bonus: bool = False) -> CorrelationResult:
        """Compute Cramér's V between all position pairs."""
        matrix = [[1.0 if row == col else 0.0 for col in range(6)] for row in range(6)]
        significant_pairs: list[tuple[int, int, float]] = []
        for left in range(6):
            left_values = self._position_values(left, is_bonus)
            for right in range(left + 1, 6):
                score = self._cramers_v(left_values, self._position_values(right, is_bonus))
                matrix[left][right] = score
                matrix[right][left] = score
                if score > 0.1:
                    significant_pairs.append((left, right, score))
        return CorrelationResult(matrix, significant_pairs)

    def analyze_autocorrelation(
        self,
        position: int,
        max_lag: int = 15,
        is_bonus: bool = False,
    ) -> AutocorrelationResult:
        """Measure categorical autocorrelation with normalized mutual information."""
        self._validate_position(position)
        digits = self._position_values(position, is_bonus)
        lag_scores: dict[int, float] = {}
        significant_lags: list[int] = []
        for lag in range(1, min(max_lag, len(digits) - 1) + 1):
            score = self._mutual_information(digits[lag:], digits[:-lag]) / math.log2(10)
            lag_scores[lag] = score
            if score > 0.02:
                significant_lags.append(lag)
        return AutocorrelationResult(position, lag_scores, significant_lags)

    def analyze_seasonal(self) -> SeasonalResult:
        """Detect monthly and weekday digit bias across all main positions."""
        monthly_counts: defaultdict[int, Counter[int]] = defaultdict(Counter)
        weekday_counts: defaultdict[int, Counter[int]] = defaultdict(Counter)
        for item in self.rounds:
            monthly_counts[item.month].update(item.numbers)
            weekday_counts[item.day_of_week].update(item.numbers)
        monthly_bias = {
            bucket: self._deviation_map(counts) for bucket, counts in sorted(monthly_counts.items())
        }
        weekday_bias = {
            bucket: self._deviation_map(counts) for bucket, counts in sorted(weekday_counts.items())
        }
        return SeasonalResult(
            monthly_bias=monthly_bias,
            weekday_bias=weekday_bias,
            strongest_monthly=self._strongest_bias(monthly_bias),
            strongest_weekday=self._strongest_bias(weekday_bias),
        )

    def analyze_trends(self, window: int = 30) -> list[TrendResult]:
        """Detect ARIMA-style momentum via recent vs historical frequency."""
        window_size = max(1, min(window, len(self.rounds)))
        recent_rounds = self.rounds[-window_size:]
        trends: list[TrendResult] = []
        for position in range(6):
            historical = Counter(item.numbers[position] for item in self.rounds)
            recent = Counter(item.numbers[position] for item in recent_rounds)
            for digit in range(10):
                historical_rate = historical.get(digit, 0) / len(self.rounds)
                recent_rate = recent.get(digit, 0) / window_size
                momentum = recent_rate - historical_rate
                if abs(momentum) <= 0.02:
                    continue
                trends.append(
                    TrendResult(
                        position=position,
                        digit=digit,
                        trend_direction=(
                            "increasing"
                            if momentum > 0.03
                            else "decreasing" if momentum < -0.03 else "stable"
                        ),
                        recent_rate=recent_rate,
                        historical_rate=historical_rate,
                        momentum=momentum,
                    )
                )
        return sorted(trends, key=lambda item: (-abs(item.momentum), item.position, item.digit))

    def print_report(self, report: AdvancedAnalysisReport) -> str:
        """Format the full analysis report in Korean."""
        weekday_names = ["월", "화", "수", "목", "금", "토", "일"]
        lines = [
            "═══════════════════════════════════════",
            "연금복권720+ 고급 통계 분석",
            "═══════════════════════════════════════",
            "",
            "[엔트로피 분석]",
        ]
        for item in report.entropy_results:
            label = f"B{item.position + 1}" if item.is_bonus else f"P{item.position + 1}"
            warning = " ⚠️" if item.normalized_entropy < 0.95 or item.bias_strength > 0.02 else ""
            lines.append(
                f"- {label}: 정규화 엔트로피 {item.normalized_entropy:.3f}{warning} "
                f"(편향 숫자 {item.most_biased_digit}, 강도 {item.bias_strength:+.1%})"
            )

        lines.extend(["", "[포지션 간 상관관계]"])
        if report.correlation.significant_pairs:
            for left, right, score in report.correlation.significant_pairs:
                lines.append(f"- P{left + 1}↔P{right + 1}: Cramér's V = {score:.3f} ⚠️")
        else:
            lines.append("- 메인 번호 간 유의미한 상관 없음")

        lines.extend(["", "[자기상관]"])
        significant_auto = [result for result in report.autocorrelation_results if result.significant_lags]
        if significant_auto:
            for result in significant_auto:
                best_lag = max(result.significant_lags, key=lambda lag: result.lag_scores[lag])
                lines.append(
                    f"- P{result.position + 1}: lag={best_lag}에서 MI={result.lag_scores[best_lag]:.3f} ⚠️"
                )
        else:
            lines.append("- 메인 번호 자리별 유의미한 자기상관 없음")

        month, month_digit, month_bias = report.seasonal.strongest_monthly
        day, day_digit, day_bias = report.seasonal.strongest_weekday
        lines.extend(["", "[계절성]"])
        lines.append(f"- {month}월: 숫자 {month_digit}가 {month_bias:+.1%} 편향")
        lines.append(f"- {weekday_names[day]}요일: 숫자 {day_digit}가 {day_bias:+.1%} 편향")
        lines.extend(["", "[시계열 추세(ARIMA 대체)]"])
        if report.trend_results:
            for trend in report.trend_results[:10]:
                arrow = "↑" if trend.momentum > 0 else "↓"
                label = {"increasing": "증가세", "decreasing": "감소세", "stable": "변동"}[
                    trend.trend_direction
                ]
                lines.append(
                    f"- P{trend.position + 1} 숫자 {trend.digit}: {arrow} {label} "
                    f"(최근 {trend.recent_rate:.1%} vs 역대 {trend.historical_rate:.1%})"
                )
        else:
            lines.append("- 뚜렷한 추세 없음")
        return "\n".join(lines)

    def _position_values(self, position: int, is_bonus: bool = False) -> list[int]:
        return [(item.bonus_numbers if is_bonus else item.numbers)[position] for item in self.rounds]

    @staticmethod
    def _cramers_v(left: list[int], right: list[int]) -> float:
        total = len(left)
        table = [[0 for _ in range(10)] for _ in range(10)]
        row_totals = [0 for _ in range(10)]
        col_totals = [0 for _ in range(10)]
        for left_digit, right_digit in zip(left, right):
            table[left_digit][right_digit] += 1
            row_totals[left_digit] += 1
            col_totals[right_digit] += 1
        chi_squared = 0.0
        for row in range(10):
            for col in range(10):
                expected = row_totals[row] * col_totals[col] / total
                if expected > 0:
                    diff = table[row][col] - expected
                    chi_squared += diff * diff / expected
        return math.sqrt(chi_squared / (total * 9)) if total else 0.0

    @staticmethod
    def _mutual_information(current: list[int], lagged: list[int]) -> float:
        total = len(current)
        if total == 0:
            return 0.0
        joint = Counter(zip(current, lagged))
        current_counts = Counter(current)
        lagged_counts = Counter(lagged)
        return sum(
            (count / total)
            * math.log2((count / total) / ((current_counts[x] / total) * (lagged_counts[y] / total)))
            for (x, y), count in joint.items()
        )

    @staticmethod
    def _deviation_map(counts: Counter[int]) -> dict[int, float]:
        total = sum(counts.values())
        if total == 0:
            return {digit: 0.0 for digit in range(10)}
        return {digit: counts.get(digit, 0) / total - 0.1 for digit in range(10)}

    @staticmethod
    def _strongest_bias(bias_map: dict[int, dict[int, float]]) -> tuple[int, int, float]:
        best = (0, 0, 0.0)
        for bucket, digits in bias_map.items():
            for digit, deviation in digits.items():
                if abs(deviation) > abs(best[2]):
                    best = (bucket, digit, deviation)
        return best

    @staticmethod
    def _validate_position(position: int) -> None:
        if not 0 <= position <= 5:
            msg = "position must be between 0 and 5"
            raise ValueError(msg)
