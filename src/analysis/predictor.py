"""Multi-strategy prediction engine for Pension Lottery 720+."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from ..models.lottery import PensionRound
from .statistics import LotteryStatistics

@dataclass
class PredictionResult:
    """Result from a single prediction strategy."""

    strategy_name: str
    group: int
    numbers: list[int]
    bonus_numbers: list[int]
    confidence: float
    reasoning: str

@dataclass
class EnsemblePrediction:
    """Combined prediction from multiple strategies."""

    predictions: list[PredictionResult]
    final_group: int
    final_numbers: list[int]
    final_bonus_numbers: list[int]
    overall_confidence: float
    summary: str

class LotteryPredictor:
    """Multi-strategy lottery number predictor."""

    _STRATEGY_META = {
        "frequency": ("빈도 기반", "누적 빈도가 가장 높은 숫자를 자리별 기본값으로 선택했습니다."),
        "hot": ("핫넘버", "최근 30회에서 평균 이상으로 자주 나온 숫자를 우선 반영했습니다."),
        "cold": ("콜드넘버", "최근에 덜 보였고 현재 갭이 긴 숫자를 자리별로 골랐습니다."),
        "gap": ("갭 분석", "현재 갭이 각 숫자의 평균 출현 간격과 가장 비슷한 후보를 선택했습니다."),
        "weighted": ("최근 가중치", "최근 회차일수록 높은 가중치를 주는 지수 감쇠 빈도를 사용했습니다."),
    }

    def __init__(self, rounds: list[PensionRound]) -> None:
        """Initialize the predictor.

        Args:
            rounds: Historical Pension Lottery rounds.

        Raises:
            ValueError: If no rounds are provided.
        """
        if not rounds:
            msg = "rounds must not be empty"
            raise ValueError(msg)
        self.rounds = sorted(rounds, key=lambda item: item.round_number)
        self.stats = LotteryStatistics(self.rounds)
        self._analysis = self.stats.analyze()

    def predict(self) -> EnsemblePrediction:
        """Run all strategies and build an ensemble result.

        Returns:
            Ensemble prediction with per-strategy outputs.
        """
        predictions = [
            self._frequency_based(),
            self._hot_number_strategy(),
            self._cold_number_strategy(),
            self._gap_analysis_strategy(),
            self._weighted_recent_strategy(),
        ]
        return self._ensemble(predictions)

    def _frequency_based(self) -> PredictionResult:
        return self._build_result("frequency")

    def _hot_number_strategy(self) -> PredictionResult:
        return self._build_result("hot")

    def _cold_number_strategy(self) -> PredictionResult:
        return self._build_result("cold")

    def _gap_analysis_strategy(self) -> PredictionResult:
        return self._build_result("gap")

    def _weighted_recent_strategy(self) -> PredictionResult:
        return self._build_result("weighted")

    def _ensemble(self, predictions: list[PredictionResult]) -> EnsemblePrediction:
        """Combine predictions using majority voting.

        Args:
            predictions: Strategy-level prediction results.

        Returns:
            Final ensemble prediction.
        """
        total = len(predictions)
        final_group, group_votes = self._majority_vote(Counter(item.group for item in predictions))
        final_numbers, number_conf = self._ensemble_digits(predictions, is_bonus=False)
        final_bonus_numbers, bonus_conf = self._ensemble_digits(predictions, is_bonus=True)
        confidence_parts = [group_votes / total, *number_conf, *bonus_conf]
        return EnsemblePrediction(
            predictions=predictions,
            final_group=final_group,
            final_numbers=final_numbers,
            final_bonus_numbers=final_bonus_numbers,
            overall_confidence=sum(confidence_parts) / len(confidence_parts),
            summary=(
                f"{total}개 전략 중 최다 득표 조합은 {final_group}조 "
                f"{self._format_digits(final_numbers)} / 보너스 {self._format_digits(final_bonus_numbers)}"
            ),
        )

    def _predict_group(self, strategy: str) -> int:
        """Predict the group number for one named strategy.

        Args:
            strategy: Strategy method name from the public contract.

        Returns:
            Predicted group number from 1 to 5.
        """
        mapping = {
            "frequency_based": "frequency", "hot_number_strategy": "hot",
            "cold_number_strategy": "cold", "gap_analysis_strategy": "gap",
            "weighted_recent_strategy": "weighted",
        }
        group, _ = self._select_value(self._group_scores(mapping[strategy]))
        return group

    def print_prediction(self, pred: EnsemblePrediction) -> str:
        """Format prediction as Korean display text.

        Args:
            pred: Ensemble prediction to format.

        Returns:
            Multi-line display text.
        """
        hot_cold = " | ".join(
            f"P{item.position + 1} H{item.hot_digits} C{item.cold_digits}"
            for item in self._analysis.position_stats
        )
        group_dist = ", ".join(
            f"{group}조 {count}회" for group, count in self._analysis.group_distribution.items()
        )
        lines = [
            "═══════════════════════════════════════",
            "연금복권720+ 다음 회차 예측 결과",
            "═══════════════════════════════════════",
            "",
            "[앙상블 최종 예측]",
            f"조: {pred.final_group}조",
            f"1등 번호: {self._format_digits(pred.final_numbers)}",
            f"보너스:   {self._format_digits(pred.final_bonus_numbers)}",
            f"신뢰도: {pred.overall_confidence:.1%}",
            "",
            "[전략별 예측]",
        ]
        for index, item in enumerate(pred.predictions, start=1):
            lines.append(
                f"{index}. {item.strategy_name}: {item.group}조 "
                f"{self._format_digits(item.numbers)} / {self._format_digits(item.bonus_numbers)} "
                f"(신뢰도: {item.confidence:.1%})"
            )
        lines.extend([
            "",
            "[분석 근거]",
            f"- 포지션별 핫/콜드 숫자: {hot_cold}",
            f"- 그룹 분포: {group_dist}",
            f"- 요약: {pred.summary}",
        ])
        return "\n".join(lines)

    def _build_result(self, strategy: str) -> PredictionResult:
        name, reasoning = self._STRATEGY_META[strategy]
        numbers, number_conf = self._pick_digits(strategy)
        bonus_numbers, bonus_conf = self._pick_digits(strategy, is_bonus=True)
        group, group_conf = self._select_value(self._group_scores(strategy))
        return PredictionResult(
            strategy_name=name,
            group=group,
            numbers=numbers,
            bonus_numbers=bonus_numbers,
            confidence=self._combine_confidence(group_conf, number_conf, bonus_conf),
            reasoning=reasoning,
        )

    def _pick_digits(self, strategy: str, is_bonus: bool = False) -> tuple[list[int], list[float]]:
        digits: list[int] = []
        confidences: list[float] = []
        for position in range(6):
            digit, confidence = self._select_value(self._position_scores(strategy, position, is_bonus))
            digits.append(digit)
            confidences.append(confidence)
        return digits, confidences

    def _position_scores(self, strategy: str, position: int, is_bonus: bool) -> dict[int, float]:
        if strategy == "frequency":
            return {
                digit: float(count)
                for digit, count in self.stats.get_position_frequency(position, is_bonus).items()
            }
        if strategy == "hot":
            recent = self._recent_scores(position, 30, is_bonus)
            hot = set(self.stats.get_hot_digits(position, 30, is_bonus))
            filtered = {digit: score if digit in hot else 0.0 for digit, score in recent.items()}
            return filtered if any(filtered.values()) else recent
        if strategy == "cold":
            gaps = self.stats.get_gap_analysis(position, is_bonus)
            cold = set(self.stats.get_cold_digits(position, 30, is_bonus))
            base = {digit: float(gaps[digit] + 1) for digit in range(10)}
            filtered = {digit: score if digit in cold else 0.0 for digit, score in base.items()}
            return filtered if any(filtered.values()) else base
        values = self._position_values(position, is_bonus)
        if strategy == "gap":
            return {digit: self._rhythm_score(values, digit) for digit in range(10)}
        return self._weighted_scores(values, range(10))

    def _group_scores(self, strategy: str) -> dict[int, float]:
        groups = [item.group for item in self.rounds]
        if strategy == "frequency":
            return {group: float(count) for group, count in self._analysis.group_distribution.items()}
        if strategy == "hot":
            recent = groups[-30:]
            average = len(recent) / 5
            counts = Counter(recent)
            scores = {group: max(float(counts.get(group, 0)) - average, 0.0) for group in range(1, 6)}
            return scores if any(scores.values()) else {group: float(counts.get(group, 0)) for group in range(1, 6)}
        if strategy == "cold":
            return {group: float(self._current_gap(groups, group) + 1) for group in range(1, 6)}
        if strategy == "gap":
            return {group: self._rhythm_score(groups, group) for group in range(1, 6)}
        return self._weighted_scores(groups, range(1, 6))

    def _recent_scores(self, position: int, window: int, is_bonus: bool) -> dict[int, float]:
        scores = {digit: 0.0 for digit in range(10)}
        for item in self.rounds[-window:]:
            values = item.bonus_numbers if is_bonus else item.numbers
            scores[values[position]] += 1.0
        return scores

    def _position_values(self, position: int, is_bonus: bool) -> list[int]:
        return [(item.bonus_numbers if is_bonus else item.numbers)[position] for item in self.rounds]

    def _ensemble_digits(self, predictions: list[PredictionResult], is_bonus: bool) -> tuple[list[int], list[float]]:
        digits: list[int] = []
        confidences: list[float] = []
        total = len(predictions)
        for position in range(6):
            values = [(item.bonus_numbers if is_bonus else item.numbers)[position] for item in predictions]
            digit, votes = self._majority_vote(Counter(values))
            digits.append(digit)
            confidences.append(votes / total)
        return digits, confidences

    @staticmethod
    def _select_value(scores: dict[int, float]) -> tuple[int, float]:
        best = max(scores.values())
        chosen = min(value for value, score in scores.items() if score == best)
        total = sum(scores.values())
        return chosen, best / total if total > 0 else 0.0

    @staticmethod
    def _majority_vote(counter: Counter[int]) -> tuple[int, int]:
        votes = max(counter.values())
        return min(value for value, count in counter.items() if count == votes), votes

    @staticmethod
    def _combine_confidence(group_conf: float, number_conf: list[float], bonus_conf: list[float]) -> float:
        metrics = [group_conf, *number_conf, *bonus_conf]
        return sum(metrics) / len(metrics)

    @staticmethod
    def _current_gap(values: list[int], target: int) -> int:
        for offset, value in enumerate(reversed(values)):
            if value == target:
                return offset
        return len(values)

    def _rhythm_score(self, values: list[int], target: int) -> float:
        indices = [index for index, value in enumerate(values) if value == target]
        if len(indices) < 2:
            return 0.0
        average_gap = sum(curr - prev for prev, curr in zip(indices, indices[1:])) / (len(indices) - 1)
        return 1.0 / (1.0 + abs(self._current_gap(values, target) - average_gap))

    @staticmethod
    def _weighted_scores(values: list[int], candidates: range) -> dict[int, float]:
        scores = {candidate: 0.0 for candidate in candidates}
        for rounds_ago, value in enumerate(reversed(values)):
            scores[value] += 0.95**rounds_ago
        return scores

    @staticmethod
    def _format_digits(values: list[int]) -> str:
        return " ".join(str(value) for value in values)
