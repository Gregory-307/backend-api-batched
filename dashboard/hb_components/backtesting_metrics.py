import streamlit as st


def render_backtesting_metrics(summary_results: dict, title: str = "Backtesting Metrics") -> None:
    net_pnl_quote = summary_results.get("net_pnl_quote", 0)
    max_dd_usd = summary_results.get("max_drawdown_usd", 0)
    max_dd_pct = summary_results.get("max_drawdown_pct", 0)
    total_volume = summary_results.get("total_volume", 0)
    sharpe = summary_results.get("sharpe_ratio", 0)
    profit_factor = summary_results.get("profit_factor", 0)

    st.write(f"### {title}")
    cols_top = st.columns(3)
    cols_bot = st.columns(3)

    cols_top[0].metric("Net PNL (Quote)", f"{net_pnl_quote:,.2f}")
    cols_top[1].metric("Max Drawdown (USD)", f"{max_dd_usd:,.2f}", delta=f"{max_dd_pct:.2%}")
    cols_top[2].metric("Total Volume (Quote)", f"{total_volume:,.2f}")

    cols_bot[0].metric("Sharpe Ratio", f"{sharpe:.2f}")
    cols_bot[1].metric("Profit Factor", f"{profit_factor:.2f}")
    cols_bot[2].metric("Executors w/ Position", summary_results.get("total_executors_with_position", 0))


def render_accuracy_metrics(summary_results: dict) -> None:
    st.write("#### Accuracy Metrics")
    accuracy = summary_results.get("accuracy", 0)
    col1, col2, col3 = st.columns(3)
    col1.metric("Global Accuracy", f"{accuracy:.2%}")
    col2.metric("Total Long", summary_results.get("total_long", 0))
    col3.metric("Total Short", summary_results.get("total_short", 0))


def render_close_types(summary_results: dict) -> None:
    st.write("#### Close Types")
    close_types = summary_results.get("close_types", {})
    labels = ["TAKE_PROFIT", "TRAILING_STOP", "STOP_LOSS", "TIME_LIMIT", "EARLY_STOP"]
    cols = st.columns(len(labels))
    for col, label in zip(cols, labels):
        col.metric(label.replace("_", " ").title(), close_types.get(label, 0)) 