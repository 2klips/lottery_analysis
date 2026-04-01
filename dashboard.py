"""Streamlit web dashboard for Pension Lottery 720+ analysis."""

from __future__ import annotations

from collections import Counter
from importlib import import_module

import pandas as pd
import streamlit as st

from src.analysis.predictor import LotteryPredictor
from src.analysis.statistics import LotteryStatistics
from src.models.lottery import PensionRound
from src.storage.database import LotteryDatabase


def main() -> None:
    """Run the Streamlit application entrypoint."""
    st.set_page_config(page_title="연금복권720+ 분석", layout="wide")
    st.title("🎰 연금복권720+ 분석 & 예측")

    db = LotteryDatabase()
    try:
        rounds = db.get_all_rounds()
        if not rounds:
            st.warning("저장된 회차 데이터가 없습니다. 먼저 수집을 실행해주세요.")
            return

        st.sidebar.header("메뉴")
        page = st.sidebar.selectbox("페이지", ["대시보드", "통계 분석", "예측", "백테스트"])

        if page == "대시보드":
            show_dashboard(rounds)
        elif page == "통계 분석":
            show_statistics(rounds)
        elif page == "예측":
            show_prediction(rounds)
        else:
            show_backtest(rounds)
    finally:
        db.close()


def show_dashboard(rounds: list[PensionRound]) -> None:
    """Render the main dashboard with core metrics and recent rounds."""
    st.header("📊 대시보드")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("총 회차", f"{len(rounds)}회")
    col2.metric("데이터 기간", f"{rounds[0].draw_date} ~ {rounds[-1].draw_date}")

    latest = rounds[-1]
    latest_number = "".join(str(digit) for digit in latest.numbers)
    col3.metric("최신 회차", f"{latest.round_number}회")
    col4.metric("최신 당첨번호", f"{latest.group}조 {latest_number}")

    st.subheader("조 분포")
    group_counts = Counter(round_item.group for round_item in rounds)
    st.bar_chart({f"{group}조": count for group, count in sorted(group_counts.items())})

    st.subheader("최근 10회차")
    recent = rounds[-10:][::-1]
    df = pd.DataFrame(
        [
            {
                "회차": round_item.round_number,
                "추첨일": str(round_item.draw_date),
                "조": f"{round_item.group}조",
                "당첨번호": " ".join(str(digit) for digit in round_item.numbers),
                "보너스": " ".join(str(digit) for digit in round_item.bonus_numbers),
            }
            for round_item in recent
        ]
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


def show_statistics(rounds: list[PensionRound]) -> None:
    """Render statistical analysis for digit frequency and trends."""
    st.header("📈 통계 분석")
    stats = LotteryStatistics(rounds)
    analysis = stats.analyze()

    st.subheader("포지션별 숫자 빈도")
    for label, pos_stats in [
        ("메인 번호", analysis.position_stats),
        ("보너스 번호", analysis.bonus_position_stats),
    ]:
        st.write(f"**{label}**")
        data = {f"P{position.position + 1}": position.frequency for position in pos_stats}
        df = pd.DataFrame(data)
        df.index.name = "숫자"
        st.dataframe(df.style.background_gradient(cmap="YlOrRd", axis=None), use_container_width=True)

    st.subheader("핫/콜드 숫자")
    cols = st.columns(6)
    for idx, pos_stat in enumerate(analysis.position_stats):
        with cols[idx]:
            st.write(f"**P{idx + 1}**")
            st.write(f"🔥 {pos_stat.hot_digits}")
            st.write(f"❄️ {pos_stat.cold_digits}")

    st.subheader("자릿수 합 분포")
    st.bar_chart(analysis.digit_sum_distribution)


def show_prediction(rounds: list[PensionRound]) -> None:
    """Render ensemble prediction results by strategy."""
    st.header("🔮 다음 회차 예측")
    predictor = LotteryPredictor(rounds)
    pred = predictor.predict()

    st.success(
        f"**앙상블 최종 예측: {pred.final_group}조  "
        f"{'  '.join(str(digit) for digit in pred.final_numbers)}**"
    )
    st.info(
        "보너스: "
        f"{'  '.join(str(digit) for digit in pred.final_bonus_numbers)}"
        f"  |  신뢰도: {pred.overall_confidence:.1%}"
    )

    st.subheader("전략별 결과")
    rows = [
        {
            "전략": item.strategy_name,
            "조": f"{item.group}조",
            "번호": " ".join(str(digit) for digit in item.numbers),
            "보너스": " ".join(str(digit) for digit in item.bonus_numbers),
            "신뢰도": f"{item.confidence:.1%}",
        }
        for item in pred.predictions
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def show_backtest(rounds: list[PensionRound]) -> None:
    """Render backtest results if backtester module is available."""
    st.header("🧪 백테스트 결과")
    try:
        backtester_module = import_module("src.analysis.backtester")
        backtester_cls = getattr(backtester_module, "LotteryBacktester")

        with st.spinner("백테스트 실행 중... (약 30초 소요)"):
            backtester = backtester_cls(rounds)
            results = backtester.run_all()

        rows = [
            {
                "전략": result.strategy_name,
                "그룹 적중률": f"{result.group_hit_rate:.1%}",
                **{f"P{i + 1}": f"{rate:.1%}" for i, rate in enumerate(result.position_hit_rates)},
                "평균 적중": f"{result.average_digits_correct:.2f}/6",
            }
            for result in results
        ]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    except ImportError:
        st.warning("백테스트 모듈이 아직 설치되지 않았습니다.")


if __name__ == "__main__":
    main()
