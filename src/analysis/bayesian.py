"""Bayesian prediction using Dirichlet-Multinomial model."""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..models.lottery import PensionRound


@dataclass
class BayesianPositionResult:
    """Bayesian prediction for one position."""

    position: int
    is_bonus: bool
    posterior_probs: dict[int, float]
    predicted_digit: int
    confidence: float
    prior_type: str


@dataclass
class BayesianPrediction:
    """Full Bayesian prediction result."""

    group: int
    numbers: list[int]
    bonus_numbers: list[int]
    confidence: float
    position_results: list[BayesianPositionResult]
    group_probs: dict[int, float]


class BayesianPredictor:
    """Dirichlet-Multinomial Bayesian predictor.

    Uses one Dirichlet posterior per digit position and an additional posterior
    for group selection. Recent rounds can be emphasized with exponential decay.
    """

    def __init__(
        self,
        rounds: list[PensionRound],
        prior: str = "uniform",
        decay: float = 1.0,
    ) -> None:
        """Initialize and compute posteriors.

        Args:
            rounds: Historical lottery rounds.
            prior: Prior type - ``uniform`` or ``jeffreys``.
            decay: Exponential recency decay in the range ``0 < decay <= 1``.

        Raises:
            ValueError: If rounds are empty or parameters are invalid.
        """
        if not rounds:
            msg = "rounds must not be empty"
            raise ValueError(msg)
        if prior not in {"uniform", "jeffreys"}:
            msg = "prior must be 'uniform' or 'jeffreys'"
            raise ValueError(msg)
        if not 0 < decay <= 1.0:
            msg = "decay must be between 0 and 1"
            raise ValueError(msg)

        self.rounds = sorted(rounds, key=lambda item: item.round_number)
        self.prior = prior
        self.decay = decay

        base_alpha = 1.0 if prior == "uniform" else 0.5
        self._main_alpha = [[base_alpha] * 10 for _ in range(6)]
        self._bonus_alpha = [[base_alpha] * 10 for _ in range(6)]
        self._group_alpha = [base_alpha] * 5
        self._update_posteriors()

    def predict(self) -> BayesianPrediction:
        """Generate prediction using posterior predictive probabilities.

        Returns:
            Bayesian prediction for group, main digits, and bonus digits.
        """
        position_results: list[BayesianPositionResult] = []
        numbers: list[int] = []
        bonus_numbers: list[int] = []
        confidence_parts: list[float] = []

        for position in range(6):
            result = self._position_result(position)
            position_results.append(result)
            numbers.append(result.predicted_digit)
            confidence_parts.append(result.confidence)

        for position in range(6):
            result = self._position_result(position, is_bonus=True)
            position_results.append(result)
            bonus_numbers.append(result.predicted_digit)
            confidence_parts.append(result.confidence)

        group_probs = self._normalize(self._group_alpha, start=1)
        group = self._pick_best(group_probs)
        confidence_parts.append(group_probs[group])
        return BayesianPrediction(
            group=group,
            numbers=numbers,
            bonus_numbers=bonus_numbers,
            confidence=math.fsum(confidence_parts) / len(confidence_parts),
            position_results=position_results,
            group_probs=group_probs,
        )

    def get_position_probs(self, position: int, is_bonus: bool = False) -> dict[int, float]:
        """Get posterior probability distribution for a position.

        Args:
            position: Zero-based digit position from 0 to 5.
            is_bonus: Whether to use bonus digits.

        Returns:
            Mapping of digit to posterior predictive probability.
        """
        self._validate_position(position)
        alpha = self._bonus_alpha[position] if is_bonus else self._main_alpha[position]
        return self._normalize(alpha)

    def print_prediction(self, pred: BayesianPrediction) -> str:
        """Format prediction in Korean.

        Args:
            pred: Prediction payload returned by ``predict()``.

        Returns:
            Multi-line display text.
        """
        lines = [
            f"[베이지안 예측 (prior={self.prior}, decay={self.decay:.2f})]",
            f"조: {pred.group}조 (확률: {pred.group_probs[pred.group]:.1%})",
            f"1등 번호: {' '.join(str(value) for value in pred.numbers)}",
            f"보너스:   {' '.join(str(value) for value in pred.bonus_numbers)}",
            f"신뢰도: {pred.confidence:.1%}",
            "",
            "포지션별 확률 분포:",
        ]
        for result in pred.position_results:
            prefix = "B" if result.is_bonus else "P"
            distribution = " ".join(
                f"{digit}→{prob:.1%}" for digit, prob in result.posterior_probs.items()
            )
            lines.append(
                f"{prefix}{result.position + 1}: {distribution} "
                f"[예측: {result.predicted_digit} ({result.confidence:.1%})]"
            )
        return "\n".join(lines)

    def _update_posteriors(self) -> None:
        n_rounds = len(self.rounds)
        for index, round_item in enumerate(self.rounds):
            weight = self.decay ** (n_rounds - 1 - index)
            self._group_alpha[round_item.group - 1] += weight
            for position in range(6):
                self._main_alpha[position][round_item.numbers[position]] += weight
                self._bonus_alpha[position][round_item.bonus_numbers[position]] += weight

    def _position_result(self, position: int, is_bonus: bool = False) -> BayesianPositionResult:
        probs = self.get_position_probs(position, is_bonus)
        predicted_digit = self._pick_best(probs)
        return BayesianPositionResult(
            position=position,
            is_bonus=is_bonus,
            posterior_probs=probs,
            predicted_digit=predicted_digit,
            confidence=probs[predicted_digit],
            prior_type=self.prior,
        )

    @staticmethod
    def _normalize(alpha: list[float], start: int = 0) -> dict[int, float]:
        total = math.fsum(alpha)
        if total <= 0:
            return {index + start: 0.0 for index in range(len(alpha))}
        return {index + start: value / total for index, value in enumerate(alpha)}

    @staticmethod
    def _pick_best(probabilities: dict[int, float]) -> int:
        best = max(probabilities.values())
        return min(value for value, probability in probabilities.items() if probability == best)

    @staticmethod
    def _validate_position(position: int) -> None:
        if not 0 <= position <= 5:
            msg = "position must be between 0 and 5"
            raise ValueError(msg)
