"""Neural network predictor using sklearn MLPClassifier."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from ..models.lottery import PensionRound


@dataclass
class LSTMPredictionResult:
    """Prediction payload for the next lottery round."""

    group: int
    numbers: list[int]
    bonus_numbers: list[int]
    confidence: float
    position_probabilities: list[dict[int, float]]


class NeuralPredictor:
    """MLP-based predictor that learns digit patterns from sequential features."""

    def __init__(self, rounds: list[PensionRound], sequence_length: int = 10) -> None:
        """Build feature vectors from sequential round data.

        Args:
            rounds: Historical Pension Lottery rounds.
            sequence_length: Number of previous rounds used as sequence input.

        Raises:
            ValueError: If rounds are empty or sequence length is too small.
        """
        if not rounds:
            msg = "rounds must not be empty"
            raise ValueError(msg)
        if sequence_length < 2:
            msg = "sequence_length must be at least 2"
            raise ValueError(msg)

        self.rounds = sorted(rounds, key=lambda item: item.round_number)
        self.sequence_length = sequence_length
        self._models: dict[str, Pipeline] = {}
        self._is_trained = False

        self._feature_position = 0
        self._feature_is_bonus = False

    def train(self) -> dict[str, float]:
        """Train one MLPClassifier per position and group.

        Returns:
            Mapping of model key to training accuracy.

        Raises:
            ValueError: If there is not enough data to train.
        """
        if len(self.rounds) <= self.sequence_length:
            msg = "not enough rounds for training"
            raise ValueError(msg)

        accuracies: dict[str, float] = {}

        for position in range(6):
            x_main, y_main = self._build_dataset(position, is_bonus=False)
            key_main = f"main_{position}"
            model_main = self._create_model()
            model_main.fit(x_main, y_main)
            self._models[key_main] = model_main
            accuracies[key_main] = float(model_main.score(x_main, y_main))

            x_bonus, y_bonus = self._build_dataset(position, is_bonus=True)
            key_bonus = f"bonus_{position}"
            model_bonus = self._create_model()
            model_bonus.fit(x_bonus, y_bonus)
            self._models[key_bonus] = model_bonus
            accuracies[key_bonus] = float(model_bonus.score(x_bonus, y_bonus))

        x_group, y_group = self._build_group_dataset()
        model_group = self._create_model()
        model_group.fit(x_group, y_group)
        self._models["group"] = model_group
        accuracies["group"] = float(model_group.score(x_group, y_group))

        self._is_trained = True
        return accuracies

    def predict(self) -> LSTMPredictionResult:
        """Predict next round's group, main digits, and bonus digits.

        Returns:
            Structured prediction result.

        Raises:
            RuntimeError: If train() was not called first.
        """
        if not self._is_trained:
            msg = "models are not trained; call train() first"
            raise RuntimeError(msg)

        round_index = len(self.rounds)
        numbers: list[int] = []
        bonus_numbers: list[int] = []
        position_probabilities: list[dict[int, float]] = []
        confidence_parts: list[float] = []

        for position in range(6):
            self._feature_position = position
            self._feature_is_bonus = False
            feature = [self._build_features(round_index)]
            main_model = self._models[f"main_{position}"]
            main_digit = int(main_model.predict(feature)[0])
            numbers.append(main_digit)

            main_probs = self._extract_probabilities(main_model, feature)
            position_probabilities.append(main_probs)
            confidence_parts.append(main_probs.get(main_digit, 0.0))

            self._feature_is_bonus = True
            bonus_feature = [self._build_features(round_index)]
            bonus_model = self._models[f"bonus_{position}"]
            bonus_digit = int(bonus_model.predict(bonus_feature)[0])
            bonus_numbers.append(bonus_digit)

            bonus_probs = self._extract_probabilities(bonus_model, bonus_feature)
            confidence_parts.append(bonus_probs.get(bonus_digit, 0.0))

        self._feature_position = 0
        self._feature_is_bonus = False
        group_feature = [self._build_features(round_index)]
        group_model = self._models["group"]
        group = int(group_model.predict(group_feature)[0])
        group_probs = self._extract_probabilities(group_model, group_feature)
        confidence_parts.append(group_probs.get(group, 0.0))

        return LSTMPredictionResult(
            group=group,
            numbers=numbers,
            bonus_numbers=bonus_numbers,
            confidence=sum(confidence_parts) / len(confidence_parts),
            position_probabilities=position_probabilities,
        )

    def _build_features(self, round_index: int) -> list[float]:
        """Build feature vector for a round index.

        Features include sequence digits, digit gaps, and temporal context.

        Args:
            round_index: Target round index in sorted history.

        Returns:
            Flat numeric feature vector.
        """
        start_index = max(0, round_index - self.sequence_length)
        history = self.rounds[start_index:round_index]

        features: list[float] = []
        for position in range(6):
            series = [round_item.numbers[position] for round_item in history]
            padding = [0] * (self.sequence_length - len(series))
            features.extend([*padding, *series])

        values_by_round = [
            (round_item.bonus_numbers if self._feature_is_bonus else round_item.numbers)[self._feature_position]
            for round_item in history
        ]
        for digit in range(10):
            gap = 0
            for back_index, value in enumerate(reversed(values_by_round), start=1):
                if value == digit:
                    gap = back_index
                    break
            features.append(float(gap if gap else len(values_by_round) + 1))

        target_date = self._infer_target_date(round_index)
        features.append(float(target_date.weekday()))
        features.append(float(target_date.month))
        return features

    def _build_dataset(self, position: int, is_bonus: bool = False) -> tuple[list[list[float]], list[int]]:
        """Build feature matrix and labels for one digit position.

        Args:
            position: Zero-based position (0-5).
            is_bonus: Use bonus digits when ``True``.

        Returns:
            Feature matrix ``X`` and target vector ``y``.
        """
        x_data: list[list[float]] = []
        y_data: list[int] = []

        self._feature_position = position
        self._feature_is_bonus = is_bonus
        for round_index in range(self.sequence_length, len(self.rounds)):
            x_data.append(self._build_features(round_index))
            round_item = self.rounds[round_index]
            target_values = round_item.bonus_numbers if is_bonus else round_item.numbers
            y_data.append(target_values[position])
        return x_data, y_data

    def _build_group_dataset(self) -> tuple[list[list[float]], list[int]]:
        """Build feature matrix and labels for group prediction model."""
        x_data: list[list[float]] = []
        y_data: list[int] = []

        self._feature_position = 0
        self._feature_is_bonus = False
        for round_index in range(self.sequence_length, len(self.rounds)):
            x_data.append(self._build_features(round_index))
            y_data.append(self.rounds[round_index].group)
        return x_data, y_data

    def _infer_target_date(self, round_index: int):
        """Infer draw date for feature generation at any index."""
        if round_index < len(self.rounds):
            return self.rounds[round_index].draw_date
        return self.rounds[-1].draw_date + timedelta(days=7)

    @staticmethod
    def _create_model() -> Pipeline:
        """Create a standardized MLP classification pipeline."""
        return Pipeline(
            [
                ("scaler", StandardScaler()),
                (
                    "mlp",
                    MLPClassifier(
                        hidden_layer_sizes=(64, 32),
                        max_iter=500,
                        random_state=42,
                    ),
                ),
            ]
        )

    @staticmethod
    def _extract_probabilities(model: Pipeline, features: list[list[float]]) -> dict[int, float]:
        """Extract class probabilities from a trained classifier pipeline."""
        classifier = model.named_steps["mlp"]
        probs = model.predict_proba(features)[0]
        classes = classifier.classes_
        return {int(label): float(prob) for label, prob in zip(classes, probs, strict=False)}
