"""Comprehensive prediction report combining all analysis results."""
from __future__ import annotations

from dataclasses import dataclass

from ..models.lottery import PensionRound
from .predictor import EnsemblePrediction, LotteryPredictor, PredictionResult
from .statistics import LotteryStatistics


@dataclass
class StrategyExplanation:
    """Detailed explanation of a prediction strategy."""
    name: str
    method_description: str
    reasoning: str
    group: int
    numbers: list[int]
    bonus_numbers: list[int]
    confidence: float


@dataclass
class BonusAnalysis:
    """Bonus number probability analysis."""
    position_probs: list[dict[int, float]]
    predicted_bonus: list[int]
    top3_per_position: list[list[tuple[int, float]]]


@dataclass
class BacktestSummary:
    """Summary of backtest results per strategy."""
    strategy_name: str
    group_accuracy: float
    position_accuracies: list[float]
    avg_digits_correct: float
    bonus_avg_correct: float


@dataclass
class ComprehensiveReport:
    """Full prediction report with all analysis."""
    next_round: int
    strategies: list[StrategyExplanation]
    ensemble_group: int
    ensemble_numbers: list[int]
    ensemble_bonus: list[int]
    ensemble_confidence: float
    bonus_analysis: BonusAnalysis
    backtest_results: list[BacktestSummary]
    data_summary: str


class PredictionReporter:
    """Generate comprehensive prediction reports."""

    _ORDER = ["frequency", "hot", "cold", "gap", "weighted"]
    _NAMES = {
        "frequency": "빈도 기반", "hot": "핫넘버", "cold": "콜드넘버",
        "gap": "갭 분석", "weighted": "최근 가중치", "ensemble": "앙상블",
    }

    def __init__(self, rounds: list[PensionRound]) -> None:
        self.rounds = sorted(rounds, key=lambda r: r.round_number)
        self.stats = LotteryStatistics(self.rounds)
        self.predictor = LotteryPredictor(self.rounds)

    def generate_report(self) -> ComprehensiveReport:
        """Generate full report with predictions, reasoning, and backtest."""
        ensemble = self.predictor.predict()
        return ComprehensiveReport(
            next_round=self.rounds[-1].round_number + 1,
            strategies=self._build_strategy_explanations(ensemble),
            ensemble_group=ensemble.final_group,
            ensemble_numbers=ensemble.final_numbers,
            ensemble_bonus=ensemble.final_bonus_numbers,
            ensemble_confidence=ensemble.overall_confidence,
            bonus_analysis=self._analyze_bonus(),
            backtest_results=self._run_backtest(50),
            data_summary=f"{len(self.rounds)}회 데이터 기반",
        )

    def _build_strategy_explanations(self, ensemble: EnsemblePrediction) -> list[StrategyExplanation]:
        """Build detailed explanation for each strategy."""
        by_name = {item.strategy_name: item for item in ensemble.predictions}
        return [
            self._explain_frequency(by_name["빈도 기반"]),
            self._explain_hot(by_name["핫넘버"]),
            self._explain_cold(by_name["콜드넘버"]),
            self._explain_gap(by_name["갭 분석"]),
            self._explain_weighted(by_name["최근 가중치"]),
        ]

    def _analyze_bonus(self) -> BonusAnalysis:
        """Analyze bonus number probability per position."""
        total = len(self.rounds)
        probs, top3, predicted = [], [], []
        for pos in range(6):
            freq = self.stats.get_position_frequency(pos, is_bonus=True)
            prob = {digit: (count / total if total else 0.0) for digit, count in freq.items()}
            ranked = sorted(prob.items(), key=lambda item: (-item[1], item[0]))
            probs.append(prob)
            top3.append(ranked[:3])
            predicted.append(ranked[0][0])
        return BonusAnalysis(position_probs=probs, predicted_bonus=predicted, top3_per_position=top3)

    def _run_backtest(self, test_size: int = 50) -> list[BacktestSummary]:
        """Run lightweight walk-forward backtest for the recent rounds."""
        keys = self._ORDER + ["ensemble"]
        stats = {k: {"g": 0, "p": [0] * 6, "m": 0.0, "b": 0.0, "n": 0} for k in keys}
        for idx in range(max(10, len(self.rounds) - test_size), len(self.rounds)):
            predictor = LotteryPredictor(self.rounds[:idx])
            actual = self.rounds[idx]
            per = {k: predictor._build_result(k) for k in self._ORDER}
            ens = predictor.predict()
            for k in keys:
                if k == "ensemble":
                    group, nums, bonus = ens.final_group, ens.final_numbers, ens.final_bonus_numbers
                else:
                    pred = per[k]
                    group, nums, bonus = pred.group, pred.numbers, pred.bonus_numbers
                row = stats[k]
                row["n"] += 1
                row["g"] += int(group == actual.group)
                main_hits = sum(1 for pos in range(6) if nums[pos] == actual.numbers[pos])
                bonus_hits = sum(1 for pos in range(6) if bonus[pos] == actual.bonus_numbers[pos])
                for pos in range(6):
                    row["p"][pos] += int(nums[pos] == actual.numbers[pos])
                row["m"] += main_hits
                row["b"] += bonus_hits
        result: list[BacktestSummary] = []
        for key in keys:
            row = stats[key]
            n = max(1, int(row["n"]))
            result.append(
                BacktestSummary(
                    strategy_name=self._NAMES[key],
                    group_accuracy=float(row["g"]) / n,
                    position_accuracies=[float(v) / n for v in row["p"]],
                    avg_digits_correct=float(row["m"]) / n,
                    bonus_avg_correct=float(row["b"]) / n,
                )
            )
        return result

    def print_report(self, report: ComprehensiveReport) -> str:
        """Format the comprehensive report in Korean."""
        date_range = self.stats.analyze().date_range
        lines = [
            "══════════════════════════════════════════════════════",
            f" 연금복권720+ 제{report.next_round}회 예측 리포트",
            "══════════════════════════════════════════════════════",
            f"분석 데이터: {len(self.rounds)}회 기반 ({date_range[0]} ~ {date_range[1]})",
            "",
            "┌─────────────────────────────────────────────────┐",
            "│  최종 예측 (앙상블)                               │",
            "│                                                  │",
            f"│  조: {report.ensemble_group}조                                   │",
            f"│  번호: {' '.join(str(d) for d in report.ensemble_numbers)}            │",
            f"│  보너스: {' '.join(str(d) for d in report.ensemble_bonus)}          │",
            f"│  종합 신뢰도: {report.ensemble_confidence:.1%}                    │",
            "└─────────────────────────────────────────────────┘",
            "",
            "── 전략별 예측 상세 ──────────────────────────────────",
            "",
        ]
        for idx, item in enumerate(report.strategies, start=1):
            lines += [
                f"[{idx}] {item.name} 전략",
                f"방식: {item.method_description}",
                f"예측: {item.group}조 {' '.join(str(d) for d in item.numbers)}",
                "근거:",
                item.reasoning,
                "",
            ]
        lines += ["── 보너스 번호 확률 분석 ──────────────────────────────", ""]
        lines.append(f"예측 보너스: {' '.join(str(d) for d in report.bonus_analysis.predicted_bonus)}")
        lines += ["", "자리별 상위 3개 숫자:"]
        for pos, top in enumerate(report.bonus_analysis.top3_per_position, start=1):
            lines.append(f"B{pos}: {top[0][0]}({top[0][1]:.1%}) > {top[1][0]}({top[1][1]:.1%}) > {top[2][0]}({top[2][1]:.1%})")
        lines += ["", "── 백테스트 결과 (최근 50회 검증) ─────────────────────", ""]
        lines.append("전략           | 조 적중 | P1   P2   P3   P4   P5   P6 | 평균적중")
        for row in report.backtest_results:
            pos = " ".join(f"{v:.0%}".rjust(3) for v in row.position_accuracies)
            lines.append(f"{row.strategy_name:<13}| {row.group_accuracy:>5.1%} | {pos}    | {row.avg_digits_correct:.2f}/6")
        lines += [
            "",
            "※ 완전 랜덤 기준: 조 20%, 자리당 10%, 평균 0.60/6",
            "※ 랜덤보다 높은 수치는 통계적 편향이 존재함을 의미합니다",
            "",
            "══════════════════════════════════════════════════════",
        ]
        return "\n".join(lines)

    def _explain_frequency(self, pred: PredictionResult) -> StrategyExplanation:
        """Build frequency-based reasoning with real counts."""
        total = len(self.rounds)
        rows = [
            f"  P{pos + 1}: 숫자 {d}가 {self.stats.get_position_frequency(pos)[d]}회"
            f"({self.stats.get_position_frequency(pos)[d] / total:.1%}) 최다 출현"
            for pos, d in enumerate(pred.numbers)
        ]
        return StrategyExplanation("빈도 기반", f"전체 {total}회 데이터에서 각 자리별 최다 출현 숫자 선택", "\n".join(rows), pred.group, pred.numbers, pred.bonus_numbers, pred.confidence)

    def _explain_hot(self, pred: PredictionResult) -> StrategyExplanation:
        """Build hot-number reasoning using recent 30 rounds."""
        recent = self.rounds[-30:]
        rows = []
        for pos, digit in enumerate(pred.numbers):
            cnt = sum(1 for r in recent if r.numbers[pos] == digit)
            tag = " [핫🔥]" if digit in self.stats.get_hot_digits(pos, 30) else ""
            rows.append(f"  P{pos + 1}: 숫자 {digit}가 최근 30회 중 {cnt}회({cnt / 30:.1%}) 출현{tag}")
        return StrategyExplanation("핫넘버", "최근 30회에서 평균(10%) 이상 출현한 숫자 우선 선택", "\n".join(rows), pred.group, pred.numbers, pred.bonus_numbers, pred.confidence)

    def _explain_cold(self, pred: PredictionResult) -> StrategyExplanation:
        """Build cold-number reasoning with current and average gaps."""
        rows = []
        for pos, digit in enumerate(pred.numbers):
            gap = self.stats.get_gap_analysis(pos)[digit]
            rows.append(f"  P{pos + 1}: 숫자 {digit}가 {gap}회 연속 미출현 (평균 간격: {self._avg_gap(pos, digit):.1f}회)")
        return StrategyExplanation("콜드넘버", "오래 미출현한 숫자를 선택 (출현 예정 이론)", "\n".join(rows), pred.group, pred.numbers, pred.bonus_numbers, pred.confidence)

    def _explain_gap(self, pred: PredictionResult) -> StrategyExplanation:
        """Build gap-analysis reasoning with gap distance."""
        rows = []
        for pos, digit in enumerate(pred.numbers):
            cur = self.stats.get_gap_analysis(pos)[digit]
            avg = self._avg_gap(pos, digit)
            rows.append(f"  P{pos + 1}: 숫자 {digit}의 현재 갭={cur}, 평균 갭={avg:.1f} (차이 {abs(cur - avg):.1f})")
        return StrategyExplanation("갭 분석", "현재 미출현 간격이 평균 간격에 가장 근접한 숫자 선택", "\n".join(rows), pred.group, pred.numbers, pred.bonus_numbers, pred.confidence)

    def _explain_weighted(self, pred: PredictionResult) -> StrategyExplanation:
        """Build weighted-recent reasoning from real weighted scores."""
        rows = []
        for pos, digit in enumerate(pred.numbers):
            scores = self._weighted_scores([r.numbers[pos] for r in self.rounds])
            rows.append(f"  P{pos + 1}: 숫자 {digit}의 가중 점수 {scores[digit]:.2f} (1위)")
        return StrategyExplanation("최근 가중치", "최근 회차에 0.95^N 지수 가중치를 부여한 빈도 기반", "\n".join(rows), pred.group, pred.numbers, pred.bonus_numbers, pred.confidence)

    def _avg_gap(self, position: int, digit: int) -> float:
        rounds = [r.round_number for r in self.rounds if r.numbers[position] == digit]
        if len(rounds) < 2:
            return float(len(self.rounds))
        gaps = [cur - prev for prev, cur in zip(rounds, rounds[1:])]
        return sum(gaps) / len(gaps)

    @staticmethod
    def _weighted_scores(values: list[int]) -> dict[int, float]:
        scores = {d: 0.0 for d in range(10)}
        for rounds_ago, value in enumerate(reversed(values)):
            scores[value] += 0.95**rounds_ago
        return scores
