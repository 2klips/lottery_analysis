"""Monte Carlo simulation for lottery number generation."""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass

from ..models.lottery import PensionRound


@dataclass
class SimulationResult:
    """Aggregated output from Monte Carlo sampling."""

    n_simulations: int
    top_combinations: list[tuple[tuple[int, ...], int]]
    position_distributions: list[dict[int, float]]
    group_distribution: dict[int, float]
    most_likely_numbers: list[int]
    most_likely_group: int
    most_likely_bonus: list[int]


class MonteCarloSimulator:
    """Generate number combinations using observed frequency distributions."""

    def __init__(self, rounds: list[PensionRound], n_simulations: int = 100_000) -> None:
        """Build probability distributions from historical data.

        Args:
            rounds: Historical Pension Lottery rounds.
            n_simulations: Number of simulations to run.

        Raises:
            ValueError: If rounds are empty or simulation count is invalid.
        """
        if not rounds:
            msg = "rounds must not be empty"
            raise ValueError(msg)
        if n_simulations < 1:
            msg = "n_simulations must be at least 1"
            raise ValueError(msg)

        self.rounds = sorted(rounds, key=lambda item: item.round_number)
        self.n_simulations = n_simulations
        self._group_distribution = self._normalize_counts(
            Counter(item.group for item in self.rounds),
            range(1, 6),
        )
        self._position_distributions = [
            self._build_position_distribution(position) for position in range(6)
        ]
        self._bonus_distributions = [
            self._build_position_distribution(position, is_bonus=True) for position in range(6)
        ]

    def simulate(self) -> SimulationResult:
        """Run simulations and aggregate the results.

        Returns:
            Aggregated Monte Carlo simulation result.
        """
        random.seed(42)
        combination_counts: Counter[tuple[int, ...]] = Counter()
        group_counts: Counter[int] = Counter()
        position_counts = [Counter() for _ in range(6)]
        bonus_counts = [Counter() for _ in range(6)]

        for _ in range(self.n_simulations):
            group = self._sample_from_distribution(self._group_distribution)
            numbers = [
                self._sample_from_distribution(distribution)
                for distribution in self._position_distributions
            ]
            bonus_numbers = [
                self._sample_from_distribution(distribution)
                for distribution in self._bonus_distributions
            ]
            group_counts[group] += 1
            combination_counts[tuple(numbers)] += 1
            for position, digit in enumerate(numbers):
                position_counts[position][digit] += 1
            for position, digit in enumerate(bonus_numbers):
                bonus_counts[position][digit] += 1

        position_distributions = [
            self._normalize_counts(counts, range(10)) for counts in position_counts
        ]
        bonus_distributions = [self._normalize_counts(counts, range(10)) for counts in bonus_counts]
        group_distribution = self._normalize_counts(group_counts, range(1, 6))
        return SimulationResult(
            n_simulations=self.n_simulations,
            top_combinations=combination_counts.most_common(10),
            position_distributions=position_distributions,
            group_distribution=group_distribution,
            most_likely_numbers=[
                self._most_likely_value(distribution) for distribution in position_distributions
            ],
            most_likely_group=self._most_likely_value(group_distribution),
            most_likely_bonus=[
                self._most_likely_value(distribution) for distribution in bonus_distributions
            ],
        )

    def _sample_from_distribution(self, distribution: dict[int, float]) -> int:
        """Weighted random sample from a probability distribution.

        Args:
            distribution: Mapping of candidate value to probability.

        Returns:
            Sampled value.
        """
        values = sorted(distribution)
        weights = [distribution[value] for value in values]
        if not any(weights):
            return values[0]
        return random.choices(values, weights=weights, k=1)[0]

    def print_report(self, result: SimulationResult) -> str:
        """Format simulation results in Korean.

        Args:
            result: Simulation output to display.

        Returns:
            Multi-line report text.
        """
        lines = [
            "연금복권720+ 몬테카를로 시뮬레이션 결과",
            f"- 시뮬레이션 횟수: {result.n_simulations:,}",
            f"- 가장 유력한 조: {result.most_likely_group}조",
            f"- 가장 유력한 번호: {' '.join(str(value) for value in result.most_likely_numbers)}",
            f"- 가장 유력한 보너스: {' '.join(str(value) for value in result.most_likely_bonus)}",
            "",
            "[자리별 확률 분포]",
        ]
        for position, distribution in enumerate(result.position_distributions, start=1):
            lines.append(f"- P{position}: {self._format_distribution(distribution)}")
        lines.append("")
        lines.append("[상위 조합]")
        for digits, count in result.top_combinations[:5]:
            lines.append(f"- {' '.join(str(value) for value in digits)}: {count}회")
        return "\n".join(lines)

    def _build_position_distribution(
        self,
        position: int,
        is_bonus: bool = False,
    ) -> dict[int, float]:
        counts = Counter(
            (item.bonus_numbers if is_bonus else item.numbers)[position] for item in self.rounds
        )
        return self._normalize_counts(counts, range(10))

    @staticmethod
    def _normalize_counts(counts: Counter[int], domain: range) -> dict[int, float]:
        total = sum(counts.values())
        if total == 0:
            return {value: 0.0 for value in domain}
        return {value: counts.get(value, 0) / total for value in domain}

    @staticmethod
    def _most_likely_value(distribution: dict[int, float]) -> int:
        best = max(distribution.values())
        return min(value for value, probability in distribution.items() if probability == best)

    @staticmethod
    def _format_distribution(distribution: dict[int, float]) -> str:
        top_values = sorted(distribution.items(), key=lambda item: (-item[1], item[0]))[:3]
        return ", ".join(f"{digit}:{probability:.0%}" for digit, probability in top_values)
