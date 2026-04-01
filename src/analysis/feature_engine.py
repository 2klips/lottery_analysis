"""Feature engineering and dynamic ensemble weighting."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta

from ..models.lottery import PensionRound
from .predictor import LotteryPredictor


@dataclass
class FeatureSet:
    """Engineered features for one round."""

    round_number: int
    features: dict[str, float]


@dataclass
class EnsembleWeight:
    """Dynamic weight for a prediction strategy."""

    strategy_name: str
    weight: float
    backtest_accuracy: float
    recent_accuracy: float


class FeatureEngineer:
    """Advanced feature engineering for ML models."""

    def __init__(self, rounds: list[PensionRound]) -> None:
        """Initialize with sorted historical rounds."""
        if not rounds:
            msg = "rounds must not be empty"
            raise ValueError(msg)
        self.rounds = sorted(rounds, key=lambda item: item.round_number)

    def build_features(self, target_index: int) -> FeatureSet:
        """Build features from ``rounds[:target_index]`` only."""
        if not 1 <= target_index <= len(self.rounds):
            msg = "target_index must be between 1 and len(rounds)"
            raise ValueError(msg)

        history = self.rounds[:target_index]
        previous_round = history[-1]
        target_round_number, target_date = self._target_metadata(target_index)
        features: dict[str, float] = {
            "digit_sum_prev": float(previous_round.digit_sum),
            "bonus_sum_prev": float(previous_round.bonus_digit_sum),
            "group_prev": float(previous_round.group),
            "month": float(target_date.month),
            "week_of_year": float(target_date.isocalendar().week),
            "even_count_prev": float(sum(digit % 2 == 0 for digit in previous_round.numbers)),
        }
        for position in range(5):
            diff = previous_round.numbers[position + 1] - previous_round.numbers[position]
            features[f"position_diff_{position}"] = float(diff)

        for position in range(6):
            values = [item.numbers[position] for item in history]
            recent_values = values[-30:]
            recent_counts = Counter(recent_values)
            average = len(recent_values) / 10 if recent_values else 0.0
            features[f"entropy_P{position}"] = self._entropy(recent_values)
            features[f"hot_count_P{position}"] = float(
                sum(1 for digit in range(10) if recent_counts.get(digit, 0) > average)
            )
            features[f"cold_count_P{position}"] = float(
                sum(1 for digit in range(10) if recent_counts.get(digit, 0) < average)
            )

            gaps = self._gaps(values)
            streaks = self._max_streaks(values)
            for window in (10, 30):
                sample = values[-window:]
                sample_counts = Counter(sample)
                denominator = float(len(sample)) if sample else 1.0
                for digit in range(10):
                    key = f"rolling_freq_P{position}_D{digit}_W{window}"
                    features[key] = sample_counts.get(digit, 0) / denominator if sample else 0.0
            for digit in range(10):
                features[f"gap_P{position}_D{digit}"] = float(gaps[digit])
                features[f"streak_P{position}_D{digit}"] = float(streaks[digit])

        return FeatureSet(round_number=target_round_number, features=features)

    def build_dataset(self, min_history: int = 30) -> tuple[list[FeatureSet], list[list[int]]]:
        """Build feature/target samples without lookahead leakage."""
        if min_history < 1:
            msg = "min_history must be at least 1"
            raise ValueError(msg)
        if len(self.rounds) <= min_history:
            msg = "rounds must contain more items than min_history"
            raise ValueError(msg)

        features: list[FeatureSet] = []
        targets: list[list[int]] = []
        for index in range(min_history, len(self.rounds)):
            features.append(self.build_features(index))
            targets.append(self.rounds[index].numbers[:])
        return features, targets

    def _target_metadata(self, target_index: int) -> tuple[int, date]:
        if target_index < len(self.rounds):
            round_item = self.rounds[target_index]
            return round_item.round_number, round_item.draw_date
        latest_round = self.rounds[-1]
        return latest_round.round_number + 1, latest_round.draw_date + timedelta(days=7)

    @staticmethod
    def _entropy(values: list[int]) -> float:
        if not values:
            return 0.0
        counts = Counter(values)
        total = len(values)
        return -sum(
            (count / total) * math.log2(count / total)
            for count in counts.values()
            if count > 0
        )

    @staticmethod
    def _gaps(values: list[int]) -> dict[int, int]:
        default_gap = len(values)
        gaps = {digit: default_gap for digit in range(10)}
        for offset, value in enumerate(reversed(values)):
            if gaps[value] == default_gap:
                gaps[value] = offset
        return gaps

    @staticmethod
    def _max_streaks(values: list[int]) -> dict[int, int]:
        streaks = {digit: 0 for digit in range(10)}
        current_value = -1
        current_length = 0
        for value in values:
            current_length = current_length + 1 if value == current_value else 1
            current_value = value
            streaks[value] = max(streaks[value], current_length)
        return streaks


class DynamicEnsemble:
    """Dynamic ensemble weighting based on backtest performance."""

    _STRATEGIES = ("frequency", "hot", "cold", "gap", "weighted")

    def __init__(self, rounds: list[PensionRound], eval_window: int = 50) -> None:
        """Initialize with rounds used for walk-forward evaluation."""
        if len(rounds) < 2:
            msg = "rounds must contain at least 2 items"
            raise ValueError(msg)
        if eval_window < 1:
            msg = "eval_window must be at least 1"
            raise ValueError(msg)
        self.rounds = sorted(rounds, key=lambda item: item.round_number)
        self.eval_window = eval_window
        self._weights: dict[str, EnsembleWeight] = {}

    def calculate_weights(self) -> dict[str, EnsembleWeight]:
        """Backtest strategies and convert accuracies into weights."""
        start_index = max(1, len(self.rounds) - self.eval_window)
        metrics = {
            strategy: {"hits": 0, "positions": 0, "round_scores": []}
            for strategy in self._STRATEGIES
        }

        for index in range(start_index, len(self.rounds)):
            actual = self.rounds[index]
            predictor = LotteryPredictor(self.rounds[:index])
            for strategy in self._STRATEGIES:
                prediction = predictor._build_result(strategy)
                hits = self._count_hits(prediction.numbers, actual.numbers)
                hits += self._count_hits(prediction.bonus_numbers, actual.bonus_numbers)
                metrics[strategy]["hits"] += hits
                metrics[strategy]["positions"] += 12
                metrics[strategy]["round_scores"].append(hits / 12)

        blended_scores: dict[str, float] = {}
        for strategy in self._STRATEGIES:
            total_positions = metrics[strategy]["positions"]
            backtest_accuracy = metrics[strategy]["hits"] / total_positions if total_positions else 0.0
            recent_scores = metrics[strategy]["round_scores"][-30:]
            recent_accuracy = sum(recent_scores) / len(recent_scores) if recent_scores else 0.0
            blended_scores[strategy] = (backtest_accuracy * 0.6) + (recent_accuracy * 0.4)
            self._weights[strategy] = EnsembleWeight(
                strategy_name=strategy,
                weight=0.0,
                backtest_accuracy=backtest_accuracy,
                recent_accuracy=recent_accuracy,
            )

        normalized = self._softmax(blended_scores, temperature=5.0)
        for strategy in self._STRATEGIES:
            self._weights[strategy].weight = normalized[strategy]
        return self._weights

    def get_weights(self) -> dict[str, float]:
        """Return strategy-to-weight mapping."""
        if not self._weights:
            self.calculate_weights()
        return {strategy: self._weights[strategy].weight for strategy in self._STRATEGIES}

    def weighted_predict(self) -> tuple[int, list[int], list[int], float]:
        """Predict group, main digits, bonus digits, and confidence."""
        if not self._weights:
            self.calculate_weights()

        predictor = LotteryPredictor(self.rounds)
        predictions = {strategy: predictor._build_result(strategy) for strategy in self._STRATEGIES}
        group, group_conf = self._weighted_vote({
            strategy: prediction.group for strategy, prediction in predictions.items()
        })
        numbers: list[int] = []
        bonus_numbers: list[int] = []
        confidence_parts = [group_conf]
        for position in range(6):
            digit, confidence = self._weighted_vote(
                {strategy: prediction.numbers[position] for strategy, prediction in predictions.items()}
            )
            numbers.append(digit)
            confidence_parts.append(confidence)
        for position in range(6):
            digit, confidence = self._weighted_vote(
                {
                    strategy: prediction.bonus_numbers[position]
                    for strategy, prediction in predictions.items()
                }
            )
            bonus_numbers.append(digit)
            confidence_parts.append(confidence)
        return group, numbers, bonus_numbers, sum(confidence_parts) / len(confidence_parts)

    def print_weights(self) -> str:
        """Format learned strategy weights in Korean."""
        if not self._weights:
            self.calculate_weights()
        lines = [
            "[동적 앙상블 가중치]",
            "전략            | 가중치 | 전체 적중률 | 최근 적중률",
        ]
        for strategy in self._STRATEGIES:
            weight = self._weights[strategy]
            name = LotteryPredictor._STRATEGY_META[strategy][0]
            lines.append(
                f"{name:<15} | {weight.weight:>4.2f}   | "
                f"{weight.backtest_accuracy:>8.1%} | {weight.recent_accuracy:>8.1%}"
            )
        return "\n".join(lines)

    def _weighted_vote(self, values: dict[str, int]) -> tuple[int, float]:
        votes: dict[int, float] = {}
        for strategy, value in values.items():
            votes[value] = votes.get(value, 0.0) + self._weights[strategy].weight
        best = max(votes.values())
        chosen = min(value for value, score in votes.items() if score == best)
        total = sum(votes.values())
        return chosen, best / total if total > 0 else 0.0

    @staticmethod
    def _softmax(scores: dict[str, float], temperature: float) -> dict[str, float]:
        scaled = {name: math.exp(score * temperature) for name, score in scores.items()}
        total = sum(scaled.values())
        return {name: value / total for name, value in scaled.items()} if total else scores

    @staticmethod
    def _count_hits(predicted: list[int], actual: list[int]) -> int:
        return sum(1 for predicted_digit, actual_digit in zip(predicted, actual) if predicted_digit == actual_digit)
