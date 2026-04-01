"""Unit tests for lottery prediction engine."""

from datetime import date, timedelta

import pytest

from src.analysis.predictor import (
    EnsemblePrediction,
    LotteryPredictor,
    PredictionResult,
)
from src.models.lottery import PensionRound


def _make_rounds(count: int = 50) -> list[PensionRound]:
    """Create N rounds with predictable data."""
    return [
        PensionRound(
            round_number=i,
            draw_date=date(2020, 5, 7) + timedelta(weeks=i - 1),
            group=(i % 5) + 1,
            numbers=[i % 10, (i + 1) % 10, (i + 2) % 10,
                     (i + 3) % 10, (i + 4) % 10, (i + 5) % 10],
            bonus_numbers=[(i + 6) % 10, (i + 7) % 10, (i + 8) % 10,
                           (i + 9) % 10, (i + 0) % 10, (i + 1) % 10],
        )
        for i in range(1, count + 1)
    ]


class TestLotteryPredictor:
    """Test LotteryPredictor strategies and ensemble."""

    def test_predict_returns_ensemble(self) -> None:
        """predict() returns an EnsemblePrediction with 5 strategies."""
        predictor = LotteryPredictor(_make_rounds())
        result = predictor.predict()
        assert isinstance(result, EnsemblePrediction)
        assert len(result.predictions) == 5

    def test_ensemble_has_valid_group(self) -> None:
        """Final group is between 1 and 5."""
        predictor = LotteryPredictor(_make_rounds())
        result = predictor.predict()
        assert 1 <= result.final_group <= 5

    def test_ensemble_has_valid_numbers(self) -> None:
        """Final numbers are 6 digits, each 0-9."""
        predictor = LotteryPredictor(_make_rounds())
        result = predictor.predict()
        assert len(result.final_numbers) == 6
        assert all(0 <= d <= 9 for d in result.final_numbers)
        assert len(result.final_bonus_numbers) == 6
        assert all(0 <= d <= 9 for d in result.final_bonus_numbers)

    def test_confidence_in_range(self) -> None:
        """Overall confidence is between 0 and 1."""
        predictor = LotteryPredictor(_make_rounds())
        result = predictor.predict()
        assert 0.0 <= result.overall_confidence <= 1.0

    def test_each_strategy_produces_result(self) -> None:
        """Each strategy produces a PredictionResult with valid fields."""
        predictor = LotteryPredictor(_make_rounds())
        result = predictor.predict()
        for pred in result.predictions:
            assert isinstance(pred, PredictionResult)
            assert 1 <= pred.group <= 5
            assert len(pred.numbers) == 6
            assert len(pred.bonus_numbers) == 6
            assert 0.0 <= pred.confidence <= 1.0
            assert pred.strategy_name != ""
            assert pred.reasoning != ""

    def test_print_prediction_returns_string(self) -> None:
        """print_prediction returns Korean-formatted text."""
        predictor = LotteryPredictor(_make_rounds())
        result = predictor.predict()
        output = predictor.print_prediction(result)
        assert isinstance(output, str)
        assert "연금복권720+" in output
        assert "앙상블" in output

    def test_empty_rounds_raises(self) -> None:
        """Empty rounds raises ValueError."""
        with pytest.raises(ValueError, match="empty"):
            LotteryPredictor([])

    def test_minimal_rounds(self) -> None:
        """Works with minimum number of rounds."""
        predictor = LotteryPredictor(_make_rounds(10))
        result = predictor.predict()
        assert isinstance(result, EnsemblePrediction)
