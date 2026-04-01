"""Statistical analysis module for Pension Lottery 720+ data."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..models.lottery import PensionRound


@dataclass
class PositionStats:
    """Statistics for a single digit position."""

    position: int
    frequency: dict[int, int]
    percentage: dict[int, float]
    last_seen: dict[int, int]
    gap: dict[int, int]
    hot_digits: list[int]
    cold_digits: list[int]


@dataclass
class OverallStats:
    """Overall lottery statistics."""

    total_rounds: int
    date_range: tuple[str, str]
    group_distribution: dict[int, int]
    position_stats: list[PositionStats]
    bonus_position_stats: list[PositionStats]
    digit_sum_distribution: dict[int, int]
    day_of_week_distribution: dict[int, int]
    month_distribution: dict[int, int]
    most_common_combinations: list[tuple[str, int]]


class LotteryStatistics:
    """Comprehensive statistical analysis of lottery data."""

    def __init__(self, rounds: list[PensionRound]) -> None:
        """Initialize the analyzer.

        Args:
            rounds: Historical Pension Lottery rounds.
        """
        self.rounds = sorted(rounds, key=lambda item: item.round_number)

    def analyze(self) -> OverallStats:
        """Run complete analysis and return aggregated statistics.

        Returns:
            Complete analysis result for the loaded rounds.
        """
        date_range = ("", "")
        if self.rounds:
            date_range = (
                self.rounds[0].draw_date.isoformat(),
                self.rounds[-1].draw_date.isoformat(),
            )

        return OverallStats(
            total_rounds=len(self.rounds),
            date_range=date_range,
            group_distribution=self.get_group_stats(),
            position_stats=[self._build_position_stats(position) for position in range(6)],
            bonus_position_stats=[
                self._build_position_stats(position, is_bonus=True) for position in range(6)
            ],
            digit_sum_distribution=dict(sorted(Counter(item.digit_sum for item in self.rounds).items())),
            day_of_week_distribution=dict(
                sorted(Counter(item.day_of_week for item in self.rounds).items())
            ),
            month_distribution=dict(sorted(Counter(item.month for item in self.rounds).items())),
            most_common_combinations=Counter(
                ",".join(str(digit) for digit in item.numbers) for item in self.rounds
            ).most_common(10),
        )

    def get_position_frequency(self, position: int, is_bonus: bool = False) -> dict[int, int]:
        """Get digit frequency for a specific position.

        Args:
            position: Zero-based digit position from 0 to 5.
            is_bonus: Whether to analyze bonus digits instead of main digits.

        Returns:
            Mapping of digit to appearance count.
        """
        self._validate_position(position)
        frequency = {digit: 0 for digit in range(10)}
        for item in self.rounds:
            values = item.bonus_numbers if is_bonus else item.numbers
            frequency[values[position]] += 1
        return frequency

    def get_hot_digits(self, position: int, window: int = 30, is_bonus: bool = False) -> list[int]:
        """Get recent hot digits at a position.

        Args:
            position: Zero-based digit position from 0 to 5.
            window: Number of most recent rounds to inspect.
            is_bonus: Whether to analyze bonus digits.

        Returns:
            Up to three digits with above-average recent frequency.
        """
        recent_rounds = self.rounds[-window:] if window > 0 else self.rounds
        if not recent_rounds:
            return []

        frequency = self._position_frequency_from_rounds(position, recent_rounds, is_bonus)
        average = len(recent_rounds) / 10
        gaps = self.get_gap_analysis(position, is_bonus)
        candidates = [digit for digit, count in frequency.items() if count > average] or list(range(10))
        return sorted(candidates, key=lambda digit: (-frequency[digit], gaps[digit], digit))[:3]

    def get_cold_digits(self, position: int, window: int = 30, is_bonus: bool = False) -> list[int]:
        """Get recent cold digits at a position.

        Args:
            position: Zero-based digit position from 0 to 5.
            window: Number of most recent rounds to inspect.
            is_bonus: Whether to analyze bonus digits.

        Returns:
            Up to three digits with below-average recent frequency.
        """
        recent_rounds = self.rounds[-window:] if window > 0 else self.rounds
        if not recent_rounds:
            return []

        frequency = self._position_frequency_from_rounds(position, recent_rounds, is_bonus)
        average = len(recent_rounds) / 10
        gaps = self.get_gap_analysis(position, is_bonus)
        candidates = [digit for digit, count in frequency.items() if count < average] or list(range(10))
        return sorted(candidates, key=lambda digit: (frequency[digit], -gaps[digit], digit))[:3]

    def get_gap_analysis(self, position: int, is_bonus: bool = False) -> dict[int, int]:
        """Get rounds-since-last-seen gap for each digit.

        Args:
            position: Zero-based digit position from 0 to 5.
            is_bonus: Whether to analyze bonus digits.

        Returns:
            Mapping of digit to current gap.
        """
        self._validate_position(position)
        if not self.rounds:
            return {digit: 0 for digit in range(10)}

        last_seen = self._get_last_seen(position, is_bonus)
        latest_round = self.rounds[-1].round_number
        return {
            digit: latest_round - last_seen[digit] if last_seen[digit] else len(self.rounds)
            for digit in range(10)
        }

    def get_trend(
        self,
        position: int,
        digit: int,
        window: int = 20,
        is_bonus: bool = False,
    ) -> list[float]:
        """Get rolling trend values for a digit at one position.

        Args:
            position: Zero-based digit position from 0 to 5.
            digit: Target digit from 0 to 9.
            window: Rolling window size.
            is_bonus: Whether to analyze bonus digits.

        Returns:
            Rolling appearance rate from oldest to newest round.
        """
        self._validate_position(position)
        if not 0 <= digit <= 9:
            msg = "digit must be between 0 and 9"
            raise ValueError(msg)

        values = [
            (item.bonus_numbers if is_bonus else item.numbers)[position]
            for item in self.rounds
        ]
        trend: list[float] = []
        for end_index in range(1, len(values) + 1):
            start_index = max(0, end_index - max(window, 1))
            sample = values[start_index:end_index]
            trend.append(sum(1 for value in sample if value == digit) / len(sample))
        return trend

    def get_group_stats(self) -> dict[int, int]:
        """Get group frequency distribution.

        Returns:
            Mapping of group number to count.
        """
        counts = {group: 0 for group in range(1, 6)}
        counts.update(Counter(item.group for item in self.rounds))
        return counts

    def get_temporal_patterns(self) -> dict[str, dict[int, dict[int, int]]]:
        """Analyze digit patterns by weekday and month.

        Returns:
            Nested dictionary containing main-number digit counts by time bucket.
        """
        patterns: dict[str, dict[int, dict[int, int]]] = {
            "day_of_week": {},
            "month": {},
        }
        for item in self.rounds:
            day_counts = patterns["day_of_week"].setdefault(
                item.day_of_week,
                {digit: 0 for digit in range(10)},
            )
            month_counts = patterns["month"].setdefault(item.month, {digit: 0 for digit in range(10)})
            for digit in item.numbers:
                day_counts[digit] += 1
                month_counts[digit] += 1
        return patterns

    def print_summary(self) -> str:
        """Generate a human-readable summary of the analysis.

        Returns:
            Multi-line summary text in Korean.
        """
        analysis = self.analyze()
        lines = [
            "연금복권720+ 통계 요약",
            f"- 총 회차: {analysis.total_rounds}",
            f"- 기간: {analysis.date_range[0]} ~ {analysis.date_range[1]}",
            "- 조 분포: "
            + ", ".join(
                f"{group}조 {count}회" for group, count in analysis.group_distribution.items()
            ),
        ]
        for stats in analysis.position_stats:
            hot = ", ".join(str(digit) for digit in stats.hot_digits) or "없음"
            cold = ", ".join(str(digit) for digit in stats.cold_digits) or "없음"
            lines.append(f"- 메인 {stats.position + 1}번 자리: 핫[{hot}] / 콜드[{cold}]")

        common = ", ".join(
            f"{combo} ({count}회)" for combo, count in analysis.most_common_combinations[:5]
        ) or "없음"
        lines.append(f"- 자주 나온 조합: {common}")
        return "\n".join(lines)

    def _build_position_stats(self, position: int, is_bonus: bool = False) -> PositionStats:
        frequency = self.get_position_frequency(position, is_bonus)
        total_rounds = len(self.rounds)
        last_seen = self._get_last_seen(position, is_bonus)
        history_order = sorted(frequency, key=lambda digit: (-frequency[digit], digit))
        cold_order = sorted(
            frequency,
            key=lambda digit: (frequency[digit], -self.get_gap_analysis(position, is_bonus)[digit], digit),
        )
        return PositionStats(
            position=position,
            frequency=frequency,
            percentage={
                digit: (count / total_rounds * 100) if total_rounds else 0.0
                for digit, count in frequency.items()
            },
            last_seen=last_seen,
            gap=self.get_gap_analysis(position, is_bonus),
            hot_digits=history_order[:3] if total_rounds else [],
            cold_digits=cold_order[:3] if total_rounds else [],
        )

    def _get_last_seen(self, position: int, is_bonus: bool = False) -> dict[int, int]:
        last_seen = {digit: 0 for digit in range(10)}
        for item in self.rounds:
            values = item.bonus_numbers if is_bonus else item.numbers
            last_seen[values[position]] = item.round_number
        return last_seen

    def _position_frequency_from_rounds(
        self,
        position: int,
        rounds: list[PensionRound],
        is_bonus: bool,
    ) -> dict[int, int]:
        self._validate_position(position)
        frequency = {digit: 0 for digit in range(10)}
        for item in rounds:
            values = item.bonus_numbers if is_bonus else item.numbers
            frequency[values[position]] += 1
        return frequency

    @staticmethod
    def _validate_position(position: int) -> None:
        if not 0 <= position <= 5:
            msg = "position must be between 0 and 5"
            raise ValueError(msg)
