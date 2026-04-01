"""Unit tests for lottery statistics analysis."""

from datetime import date, timedelta

import pytest

from src.analysis.statistics import LotteryStatistics, OverallStats
from src.models.lottery import PensionRound


def _make_round(num: int, group: int = 1, numbers: list[int] | None = None) -> PensionRound:
    """Helper to create a PensionRound with minimal boilerplate."""
    return PensionRound(
        round_number=num,
        draw_date=date(2020, 5, 7) + timedelta(weeks=num - 1),
        group=group,
        numbers=numbers or [0, 1, 2, 3, 4, 5],
        bonus_numbers=[9, 8, 7, 6, 5, 4],
    )


@pytest.fixture()
def sample_rounds() -> list[PensionRound]:
    """Create 20 rounds with varied data."""
    rounds = []
    for i in range(1, 21):
        rounds.append(_make_round(
            num=i,
            group=(i % 5) + 1,
            numbers=[i % 10, (i + 1) % 10, (i + 2) % 10,
                     (i + 3) % 10, (i + 4) % 10, (i + 5) % 10],
        ))
    return rounds


class TestLotteryStatistics:
    """Test LotteryStatistics analysis methods."""

    def test_analyze_returns_overall_stats(self, sample_rounds: list[PensionRound]) -> None:
        """analyze() returns OverallStats with correct totals."""
        stats = LotteryStatistics(sample_rounds)
        result = stats.analyze()
        assert isinstance(result, OverallStats)
        assert result.total_rounds == 20

    def test_position_frequency(self, sample_rounds: list[PensionRound]) -> None:
        """get_position_frequency returns counts for all 10 digits."""
        stats = LotteryStatistics(sample_rounds)
        freq = stats.get_position_frequency(0)
        assert len(freq) == 10
        assert sum(freq.values()) == 20

    def test_hot_digits_returns_list(self, sample_rounds: list[PensionRound]) -> None:
        """get_hot_digits returns up to 3 digits."""
        stats = LotteryStatistics(sample_rounds)
        hot = stats.get_hot_digits(0, window=10)
        assert isinstance(hot, list)
        assert len(hot) <= 3
        assert all(0 <= d <= 9 for d in hot)

    def test_cold_digits_returns_list(self, sample_rounds: list[PensionRound]) -> None:
        """get_cold_digits returns up to 3 digits."""
        stats = LotteryStatistics(sample_rounds)
        cold = stats.get_cold_digits(0, window=10)
        assert isinstance(cold, list)
        assert len(cold) <= 3

    def test_gap_analysis(self, sample_rounds: list[PensionRound]) -> None:
        """get_gap_analysis returns gap for each digit."""
        stats = LotteryStatistics(sample_rounds)
        gaps = stats.get_gap_analysis(0)
        assert len(gaps) == 10
        assert all(isinstance(g, int) for g in gaps.values())

    def test_group_stats(self, sample_rounds: list[PensionRound]) -> None:
        """get_group_stats returns counts for groups 1-5."""
        stats = LotteryStatistics(sample_rounds)
        groups = stats.get_group_stats()
        assert len(groups) == 5
        assert sum(groups.values()) == 20

    def test_trend(self, sample_rounds: list[PensionRound]) -> None:
        """get_trend returns list of floats."""
        stats = LotteryStatistics(sample_rounds)
        trend = stats.get_trend(0, digit=1, window=5)
        assert len(trend) == 20
        assert all(0.0 <= v <= 1.0 for v in trend)

    def test_temporal_patterns(self, sample_rounds: list[PensionRound]) -> None:
        """get_temporal_patterns returns day_of_week and month."""
        stats = LotteryStatistics(sample_rounds)
        patterns = stats.get_temporal_patterns()
        assert "day_of_week" in patterns
        assert "month" in patterns

    def test_print_summary_is_string(self, sample_rounds: list[PensionRound]) -> None:
        """print_summary returns a non-empty string."""
        stats = LotteryStatistics(sample_rounds)
        summary = stats.print_summary()
        assert isinstance(summary, str)
        assert "연금복권720+" in summary

    def test_invalid_position_raises(self, sample_rounds: list[PensionRound]) -> None:
        """Position outside 0-5 raises ValueError."""
        stats = LotteryStatistics(sample_rounds)
        with pytest.raises(ValueError, match="position"):
            stats.get_position_frequency(6)

    def test_empty_rounds(self) -> None:
        """Empty rounds produce zero-count stats."""
        stats = LotteryStatistics([])
        result = stats.analyze()
        assert result.total_rounds == 0
