"""Backtesting engine to evaluate prediction strategies."""

from __future__ import annotations

from dataclasses import dataclass

from ..models.lottery import PensionRound
from .markov import MarkovChainPredictor  # pyright: ignore[reportMissingImports]
from .monte_carlo import MonteCarloSimulator  # pyright: ignore[reportMissingImports]
from .predictor import LotteryPredictor, PredictionResult


@dataclass
class BacktestResult:
    """Aggregated accuracy metrics for one strategy."""

    strategy_name: str
    total_rounds_tested: int
    exact_match_count: int
    position_hit_rates: list[float]
    group_hit_rate: float
    average_digits_correct: float
    bonus_position_hit_rates: list[float]
    bonus_avg_correct: float


class LotteryBacktester:
    """Evaluate prediction accuracy using walk-forward testing."""

    _STRATEGIES = {
        "frequency": "빈도 기반",
        "hot": "핫넘버",
        "cold": "콜드넘버",
        "gap": "갭 분석",
        "weighted": "최근 가중치",
        "markov": "마코프 체인",
        "monte_carlo": "몬테카를로",
    }

    def __init__(self, rounds: list[PensionRound], min_train_size: int = 50) -> None:
        """Initialize the backtester.

        Args:
            rounds: Historical Pension Lottery rounds.
            min_train_size: Minimum number of rounds before testing starts.

        Raises:
            ValueError: If inputs do not allow at least one test round.
        """
        if not rounds:
            msg = "rounds must not be empty"
            raise ValueError(msg)
        if min_train_size < 1:
            msg = "min_train_size must be at least 1"
            raise ValueError(msg)

        self.rounds = sorted(rounds, key=lambda item: item.round_number)
        if len(self.rounds) <= min_train_size:
            msg = "rounds must contain more items than min_train_size"
            raise ValueError(msg)
        self.min_train_size = min_train_size

    def run_all(self) -> list[BacktestResult]:
        """Run backtest for all built-in strategies and new models.

        Returns:
            Backtest result for each supported strategy.
        """
        return [self.run_single(strategy_name) for strategy_name in self._STRATEGIES]

    def run_single(self, strategy_name: str) -> BacktestResult:
        """Run backtest for one specific strategy.

        Args:
            strategy_name: Internal or display strategy name.

        Returns:
            Aggregated walk-forward backtest result.
        """
        strategy_key = self._normalize_strategy_name(strategy_name)
        total_rounds = len(self.rounds) - self.min_train_size
        position_hits = [0] * 6
        bonus_hits = [0] * 6
        group_hits = 0
        exact_matches = 0
        total_main_hits = 0
        total_bonus_hits = 0

        for index in range(self.min_train_size, len(self.rounds)):
            training_rounds = self.rounds[:index]
            actual_round = self.rounds[index]
            prediction = self._build_prediction(training_rounds, strategy_key)
            main_hits = self._count_hits(prediction.numbers, actual_round.numbers, position_hits)
            bonus_main_hits = self._count_hits(
                prediction.bonus_numbers,
                actual_round.bonus_numbers,
                bonus_hits,
            )
            total_main_hits += main_hits
            total_bonus_hits += bonus_main_hits
            if prediction.group == actual_round.group:
                group_hits += 1
            if main_hits == 6:
                exact_matches += 1

        return BacktestResult(
            strategy_name=self._STRATEGIES[strategy_key],
            total_rounds_tested=total_rounds,
            exact_match_count=exact_matches,
            position_hit_rates=[count / total_rounds for count in position_hits],
            group_hit_rate=group_hits / total_rounds,
            average_digits_correct=total_main_hits / total_rounds,
            bonus_position_hit_rates=[count / total_rounds for count in bonus_hits],
            bonus_avg_correct=total_bonus_hits / total_rounds,
        )

    def print_report(self, results: list[BacktestResult]) -> str:
        """Format backtest results as Korean text table.

        Args:
            results: Backtest results to display.

        Returns:
            Multi-line backtest report.
        """
        if not results:
            return "백테스트 결과가 없습니다."

        start_round = self.rounds[self.min_train_size].round_number
        end_round = self.rounds[-1].round_number
        lines = [
            "══════════════════════════════════════",
            "연금복권720+ 백테스트 결과",
            "══════════════════════════════════════",
            f"테스트 구간: {start_round}회 ~ {end_round}회 ({results[0].total_rounds_tested}회 테스트)",
            "",
            "[메인 번호]",
            "전략            | 그룹 | P1   | P2   | P3   | P4   | P5   | P6   | 평균 | 완전일치",
        ]
        for result in results:
            lines.append(self._format_main_row(result))
        lines.extend([
            "",
            "[보너스 번호]",
            "전략            | B1   | B2   | B3   | B4   | B5   | B6   | 평균",
        ])
        for result in results:
            lines.append(self._format_bonus_row(result))
        return "\n".join(lines)

    def _build_prediction(
        self,
        training_rounds: list[PensionRound],
        strategy_name: str,
    ) -> PredictionResult:
        if strategy_name in LotteryPredictor._STRATEGY_META:
            return LotteryPredictor(training_rounds)._build_result(strategy_name)
        if strategy_name == "markov":
            group, numbers, bonus_numbers = MarkovChainPredictor(training_rounds).predict_all()
            return PredictionResult(
                strategy_name=self._STRATEGIES[strategy_name],
                group=group,
                numbers=numbers,
                bonus_numbers=bonus_numbers,
                confidence=0.0,
                reasoning="최근 회차 전이 확률을 기준으로 다음 숫자를 예측했습니다.",
            )

        simulation = MonteCarloSimulator(
            training_rounds,
            n_simulations=max(5_000, len(training_rounds) * 25),
        ).simulate()
        return PredictionResult(
            strategy_name=self._STRATEGIES[strategy_name],
            group=simulation.most_likely_group,
            numbers=simulation.most_likely_numbers,
            bonus_numbers=simulation.most_likely_bonus,
            confidence=0.0,
            reasoning="관측 빈도 분포를 반복 샘플링해 가장 가능성이 높은 조합을 선택했습니다.",
        )

    @staticmethod
    def _count_hits(predicted: list[int], actual: list[int], bucket: list[int]) -> int:
        hits = 0
        for position, (predicted_digit, actual_digit) in enumerate(zip(predicted, actual)):
            if predicted_digit == actual_digit:
                bucket[position] += 1
                hits += 1
        return hits

    def _normalize_strategy_name(self, strategy_name: str) -> str:
        normalized = strategy_name.strip().lower().replace(" ", "_")
        aliases = {key: key for key in self._STRATEGIES}
        aliases.update({value: key for key, value in self._STRATEGIES.items()})
        aliases["montecarlo"] = "monte_carlo"
        aliases["markov_chain"] = "markov"
        if strategy_name in aliases:
            return aliases[strategy_name]
        if normalized in aliases:
            return aliases[normalized]
        msg = f"unsupported strategy: {strategy_name}"
        raise ValueError(msg)

    def _format_main_row(self, result: BacktestResult) -> str:
        rates = " | ".join(f"{rate:>4.0%}" for rate in result.position_hit_rates)
        return (
            f"{result.strategy_name:<15} | {result.group_hit_rate:>4.0%} | {rates} | "
            f"{result.average_digits_correct:>4.2f} | {result.exact_match_count:>4d}회"
        )

    def _format_bonus_row(self, result: BacktestResult) -> str:
        rates = " | ".join(f"{rate:>4.0%}" for rate in result.bonus_position_hit_rates)
        return f"{result.strategy_name:<15} | {rates} | {result.bonus_avg_correct:>4.2f}"
