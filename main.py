"""Main entry point for Pension Lottery 720+ collection and prediction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.collector.fetcher import PensionFetcher, FetchError
from src.collector.parser import LotteryParser
from src.storage.database import LotteryDatabase
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

DATA_DIR = Path(__file__).parent / "data"
EXPORT_PATH = DATA_DIR / "exports" / "lottery_data.json"


def collect_data(db: LotteryDatabase) -> int:
    """Fetch all rounds from API and store in database.

    Args:
        db: Active database connection.

    Returns:
        Number of newly inserted rounds.
    """
    fetcher = PensionFetcher()
    try:
        logger.info("Fetching all rounds from API...")
        raw_json = fetcher.fetch_all_rounds()
        rounds = LotteryParser.parse_round_list(raw_json)
        logger.info("Parsed %d rounds from API", len(rounds))

        if not rounds:
            logger.warning("No rounds parsed from API response")
            return 0

        inserted = db.insert_rounds(rounds)
        latest = max(r.round_number for r in rounds)
        db.save_progress(latest)
        logger.info(
            "Inserted %d new rounds (total in DB: %d, latest: %d)",
            inserted,
            db.get_round_count(),
            latest,
        )
        return inserted
    except FetchError as error:
        logger.error("Data collection failed: %s", error)
        return 0
    finally:
        fetcher.close()


def run_analysis(db: LotteryDatabase) -> None:
    """Run statistical analysis and print summary.

    Args:
        db: Active database connection with collected data.
    """
    from src.analysis.statistics import LotteryStatistics

    rounds = db.get_all_rounds()
    if not rounds:
        logger.warning("No data in database. Run 'collect' first.")
        return

    stats = LotteryStatistics(rounds)
    print(stats.print_summary())


def run_prediction(db: LotteryDatabase) -> None:
    """Run prediction engine and display results.

    Args:
        db: Active database connection with collected data.
    """
    from src.analysis.predictor import LotteryPredictor

    rounds = db.get_all_rounds()
    if len(rounds) < 10:
        logger.warning("Need at least 10 rounds for prediction. Have %d.", len(rounds))
        return

    predictor = LotteryPredictor(rounds)
    prediction = predictor.predict()
    print(predictor.print_prediction(prediction))


def run_backtest(db: LotteryDatabase) -> None:
    """Run backtesting across all strategies.

    Args:
        db: Active database connection with collected data.
    """
    from src.analysis.backtester import LotteryBacktester

    rounds = db.get_all_rounds()
    if len(rounds) < 60:
        logger.warning("Need at least 60 rounds for backtest. Have %d.", len(rounds))
        return

    logger.info("Running backtest on %d rounds...", len(rounds))
    bt = LotteryBacktester(rounds)
    results = bt.run_all()
    print(bt.print_report(results))


def run_markov(db: LotteryDatabase) -> None:
    """Run Markov Chain prediction.

    Args:
        db: Active database connection with collected data.
    """
    from src.analysis.markov import MarkovChainPredictor

    rounds = db.get_all_rounds()
    if len(rounds) < 10:
        logger.warning("Need at least 10 rounds. Have %d.", len(rounds))
        return

    mc = MarkovChainPredictor(rounds)
    print(mc.print_summary())


def run_montecarlo(db: LotteryDatabase) -> None:
    """Run Monte Carlo simulation.

    Args:
        db: Active database connection with collected data.
    """
    from src.analysis.monte_carlo import MonteCarloSimulator

    rounds = db.get_all_rounds()
    if not rounds:
        logger.warning("No data in database. Run 'collect' first.")
        return

    sim = MonteCarloSimulator(rounds, n_simulations=100_000)
    result = sim.simulate()
    print(sim.print_report(result))


def run_neural(db: LotteryDatabase) -> None:
    """Train and run neural network prediction.

    Args:
        db: Active database connection with collected data.
    """
    from src.analysis.lstm_predictor import NeuralPredictor

    rounds = db.get_all_rounds()
    if len(rounds) < 30:
        logger.warning("Need at least 30 rounds for neural prediction. Have %d.", len(rounds))
        return

    logger.info("Training neural models on %d rounds...", len(rounds))
    predictor = NeuralPredictor(rounds)
    accuracy = predictor.train()
    for key, val in accuracy.items():
        logger.info("  %s accuracy: %.2f%%", key, val * 100)
    result = predictor.predict()
    print(f"\n[Neural Network 예측]")
    print(f"조: {result.group}조")
    print(f"1등 번호: {' '.join(str(d) for d in result.numbers)}")
    print(f"보너스:   {' '.join(str(d) for d in result.bonus_numbers)}")
    print(f"신뢰도: {result.confidence:.1%}")


def export_data(db: LotteryDatabase) -> None:
    """Export all data to JSON file.

    Args:
        db: Active database connection.
    """
    count = db.export_to_json(EXPORT_PATH)
    logger.info("Exported %d rounds to %s", count, EXPORT_PATH)


COMMANDS = [
    "collect", "analyze", "predict", "backtest",
    "markov", "montecarlo", "neural", "all", "export", "dashboard",
]


def main() -> None:
    """Parse CLI arguments and execute requested command."""
    parser = argparse.ArgumentParser(
        description="연금복권720+ 데이터 수집 및 예측 시스템",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  python main.py collect       데이터 수집
  python main.py analyze       통계 분석
  python main.py predict       앙상블 예측
  python main.py backtest      전략 백테스트
  python main.py markov        마르코프 체인 예측
  python main.py montecarlo    몬테카를로 시뮬레이션
  python main.py neural        신경망 예측
  python main.py all           수집 + 분석 + 예측
  python main.py export        JSON 내보내기
  python main.py dashboard     Streamlit 대시보드 실행
        """,
    )
    parser.add_argument("command", choices=COMMANDS, help="실행할 명령")
    args = parser.parse_args()

    if args.command == "dashboard":
        import subprocess
        subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard.py"])
        return

    db = LotteryDatabase()
    try:
        if args.command in ("collect", "all"):
            collect_data(db)

        if args.command in ("analyze", "all"):
            run_analysis(db)

        if args.command in ("predict", "all"):
            run_prediction(db)

        if args.command == "backtest":
            run_backtest(db)

        if args.command == "markov":
            run_markov(db)

        if args.command == "montecarlo":
            run_montecarlo(db)

        if args.command == "neural":
            run_neural(db)

        if args.command == "export":
            export_data(db)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
