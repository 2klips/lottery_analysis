"""Markov Chain transition model for digit prediction."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from ..models.lottery import PensionRound


@dataclass
class MarkovPrediction:
    """Prediction payload for one digit position."""

    position: int
    is_bonus: bool
    transition_probs: dict[int, float]
    predicted_digit: int
    confidence: float


class MarkovChainPredictor:
    """First-order Markov chain: P(next_digit | current_digit) per position."""

    def __init__(self, rounds: list[PensionRound], order: int = 1) -> None:
        """Build transition matrices from historical data.

        Args:
            rounds: Historical Pension Lottery rounds.
            order: Markov chain order. Only first-order is supported.

        Raises:
            ValueError: If rounds are empty or order is unsupported.
        """
        if not rounds:
            msg = "rounds must not be empty"
            raise ValueError(msg)
        if order != 1:
            msg = "only first-order Markov chains are supported"
            raise ValueError(msg)

        self.rounds = sorted(rounds, key=lambda item: item.round_number)
        self.order = order
        self._transitions: list[dict[bool, defaultdict[int, Counter[int]]]] = [
            {False: defaultdict(Counter), True: defaultdict(Counter)} for _ in range(6)
        ]
        self._group_transitions: defaultdict[int, Counter[int]] = defaultdict(Counter)
        self._base_distributions = {
            False: [self._position_distribution(position) for position in range(6)],
            True: [self._position_distribution(position, is_bonus=True) for position in range(6)],
        }
        self._group_distribution = self._normalize_counts(
            Counter(item.group for item in self.rounds),
            range(1, 6),
        )
        self._build_transitions()

    def predict_position(
        self,
        position: int,
        current_digit: int,
        is_bonus: bool = False,
    ) -> MarkovPrediction:
        """Predict next digit given current digit at a position.

        Args:
            position: Zero-based digit position from 0 to 5.
            current_digit: Current digit from 0 to 9.
            is_bonus: Whether to use bonus-digit transitions.

        Returns:
            Markov prediction result for the requested position.
        """
        self._validate_position(position)
        self._validate_digit(current_digit)
        transition_probs = self._row_probabilities(position, current_digit, is_bonus)
        predicted_digit, confidence = self._pick_best(transition_probs)
        return MarkovPrediction(
            position=position,
            is_bonus=is_bonus,
            transition_probs=transition_probs,
            predicted_digit=predicted_digit,
            confidence=confidence,
        )

    def predict_all(self) -> tuple[int, list[int], list[int]]:
        """Predict group + 6 main digits + 6 bonus digits.

        Returns:
            Tuple of predicted group, main digits, and bonus digits.
        """
        latest_round = self.rounds[-1]
        group = self._predict_group(latest_round.group)
        numbers = [
            self.predict_position(position, latest_round.numbers[position]).predicted_digit
            for position in range(6)
        ]
        bonus_numbers = [
            self.predict_position(position, latest_round.bonus_numbers[position], is_bonus=True).predicted_digit
            for position in range(6)
        ]
        return group, numbers, bonus_numbers

    def get_transition_matrix(
        self,
        position: int,
        is_bonus: bool = False,
    ) -> dict[int, dict[int, float]]:
        """Get the full 10x10 transition probability matrix for a position.

        Args:
            position: Zero-based digit position from 0 to 5.
            is_bonus: Whether to use bonus-digit transitions.

        Returns:
            Transition matrix keyed by current digit and next digit.
        """
        self._validate_position(position)
        return {
            current_digit: self._row_probabilities(position, current_digit, is_bonus)
            for current_digit in range(10)
        }

    def print_summary(self) -> str:
        """Print transition summaries and predictions in Korean.

        Returns:
            Multi-line Markov analysis summary.
        """
        latest_round = self.rounds[-1]
        group, numbers, bonus_numbers = self.predict_all()
        lines = [
            "연금복권720+ 마코프 체인 요약",
            f"- 기준 회차: {latest_round.round_number}회",
            f"- 예측 조: {group}조",
            f"- 예측 번호: {' '.join(str(value) for value in numbers)}",
            f"- 예측 보너스: {' '.join(str(value) for value in bonus_numbers)}",
            "",
            "[현재 숫자 기준 전이 확률]",
        ]
        for position in range(6):
            main_prediction = self.predict_position(position, latest_round.numbers[position])
            bonus_prediction = self.predict_position(
                position,
                latest_round.bonus_numbers[position],
                is_bonus=True,
            )
            lines.append(
                f"- 메인 P{position + 1} ({latest_round.numbers[position]}→): "
                f"{self._format_probs(main_prediction.transition_probs)}"
            )
            lines.append(
                f"- 보너스 B{position + 1} ({latest_round.bonus_numbers[position]}→): "
                f"{self._format_probs(bonus_prediction.transition_probs)}"
            )
        return "\n".join(lines)

    def _build_transitions(self) -> None:
        for previous_round, current_round in zip(self.rounds, self.rounds[1:]):
            self._group_transitions[previous_round.group][current_round.group] += 1
            for position in range(6):
                self._transitions[position][False][previous_round.numbers[position]][
                    current_round.numbers[position]
                ] += 1
                self._transitions[position][True][previous_round.bonus_numbers[position]][
                    current_round.bonus_numbers[position]
                ] += 1

    def _position_distribution(self, position: int, is_bonus: bool = False) -> dict[int, float]:
        counts = Counter(
            (item.bonus_numbers if is_bonus else item.numbers)[position] for item in self.rounds
        )
        return self._normalize_counts(counts, range(10))

    def _predict_group(self, current_group: int) -> int:
        row = self._group_transitions.get(current_group)
        if not row:
            return self._pick_best(self._group_distribution)[0]
        return self._pick_best(self._normalize_counts(row, range(1, 6)))[0]

    def _row_probabilities(
        self,
        position: int,
        current_digit: int,
        is_bonus: bool,
    ) -> dict[int, float]:
        row = self._transitions[position][is_bonus].get(current_digit)
        if not row:
            return self._base_distributions[is_bonus][position]
        return self._normalize_counts(row, range(10))

    @staticmethod
    def _normalize_counts(counts: Counter[int], domain: range) -> dict[int, float]:
        total = sum(counts.values())
        if total == 0:
            return {value: 0.0 for value in domain}
        return {value: counts.get(value, 0) / total for value in domain}

    @staticmethod
    def _pick_best(probabilities: dict[int, float]) -> tuple[int, float]:
        best = max(probabilities.values())
        chosen = min(value for value, probability in probabilities.items() if probability == best)
        return chosen, best

    @staticmethod
    def _format_probs(probabilities: dict[int, float]) -> str:
        top_values = sorted(probabilities.items(), key=lambda item: (-item[1], item[0]))[:3]
        return ", ".join(f"{digit}:{probability:.0%}" for digit, probability in top_values)

    @staticmethod
    def _validate_digit(digit: int) -> None:
        if not 0 <= digit <= 9:
            msg = "digit must be between 0 and 9"
            raise ValueError(msg)

    @staticmethod
    def _validate_position(position: int) -> None:
        if not 0 <= position <= 5:
            msg = "position must be between 0 and 5"
            raise ValueError(msg)
