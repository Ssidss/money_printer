"""
Backtest V3 — 驗證腳本

用 SMCStrategy 在新引擎跑回測，對比 v2 baseline。
"""
import asyncio
import json
import logging
import sys
import time
from datetime import date

# Add project root to path
sys.path.insert(0, ".")

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


async def main():
    from backend.app.database import AsyncSessionLocal
    from backend.app.services.backtester_v2 import load_all_price_data
    from backend.app.services.backtest_v3 import (
        BacktestEngine, HistoricalProvider, SMCStrategy,
        SizingModel, ExecutionModel, KillSwitch,
        calculate_metrics,
    )

    print("=" * 60)
    print("Backtest V3 — Phase 1A Validation Run")
    print("=" * 60)

    # Load data from DB (same as v2)
    print("\n[1/4] Loading price data from DB...")
    t0 = time.time()
    async with AsyncSessionLocal() as db:
        stocks_info, price_data = await load_all_price_data(db, market_filter="US")
    print(f"  Loaded {len(price_data)} stocks in {time.time()-t0:.1f}s")

    # Setup
    start = date(2023, 1, 1)
    end = date(2024, 12, 31)  # Validation period

    provider = HistoricalProvider(
        price_data=price_data,
        stocks_info=stocks_info,
        start_date=start,
        end_date=end,
    )
    print(f"  Trading days: {provider.total_days}")

    strategy = SMCStrategy(
        min_conditions=3,  # Match v2 baseline
        min_rr=2.0,        # Match v2 baseline
    )

    sizing = SizingModel(
        risk_per_trade_pct=1.0,
        max_position_pct=20.0,
        max_positions=8,
    )

    execution = ExecutionModel(
        fill_type="next_open",
        slippage_pct=0.05,
        gap_threshold_pct=5.0,
    )

    kill_switch = KillSwitch(enabled=True, max_daily_loss_pct=8.0)  # 5% too sensitive for portfolio-level

    engine = BacktestEngine(
        strategies=[strategy],
        provider=provider,
        initial_capital=100_000,
        sizing=sizing,
        execution=execution,
        kill_switch=kill_switch,
    )

    # Run
    print("\n[2/4] Running backtest...")
    t0 = time.time()

    async def progress(msg, pct):
        print(f"  [{pct:.0f}%] {msg}")

    result = await engine.run(progress_cb=progress)
    duration = time.time() - t0
    print(f"  Done in {duration:.1f}s")

    # Calculate metrics
    print("\n[3/4] Calculating metrics...")
    report = calculate_metrics(result)
    summary = report["portfolio_summary"]

    # Print results
    print("\n[4/4] Results")
    print("=" * 60)
    print(f"  Period:           {start} → {end}")
    print(f"  Initial Capital:  ${summary['initial_capital']:,.0f}")
    print(f"  Final Equity:     ${summary['final_equity']:,.0f}")
    print(f"  Total Return:     {summary['total_return_pct']:+.2f}%")
    print(f"  CAGR:             {summary['cagr_pct']:+.2f}%")
    print(f"  Max Drawdown:     {summary['max_drawdown_pct']:.2f}%")
    print(f"  Sharpe Ratio:     {summary['sharpe_ratio']:.3f}")
    print(f"  Sortino Ratio:    {summary['sortino_ratio']:.3f}")
    print(f"  Calmar Ratio:     {summary['calmar_ratio']:.3f}")
    print(f"  Profit Factor:    {summary['profit_factor']:.2f}")
    print(f"  Win Rate:         {summary['win_rate_pct']:.1f}%")
    print(f"  Total Trades:     {summary['total_trades']}")
    print(f"  Avg Holding Days: {summary['avg_holding_days']:.1f}")
    print(f"  Expectancy:       {summary['expectancy']:.3f}")
    print(f"  Avg Exposure:     {summary['avg_exposure_pct']:.1f}%")
    print(f"  Max Consec Loss:  {summary['max_consecutive_losses']}")
    print(f"  Tail Risk CVaR5%: {summary['tail_risk_cvar_5pct']:.2f}%")
    print(f"  Trading Days:     {summary['trading_days']}")

    # Strategy breakdown
    print("\n  Strategy Breakdown:")
    for sn, data in report["strategy_breakdown"]["by_strategy"].items():
        print(f"    {sn}: {data['total_trades']} trades, WR={data['win_rate_pct']:.1f}%, PF={data['profit_factor']:.2f}")

    # Exit reason breakdown
    print("\n  Exit Reasons:")
    for er, data in report["strategy_breakdown"]["by_exit_reason"].items():
        print(f"    {er}: {data['count']} trades, avg={data['avg_pnl_pct']:+.2f}%")

    # Order stats
    os = result["order_stats"]
    print(f"\n  Orders: {os['total']} total, {os['filled']} filled, {os['cancelled']} cancelled")
    if os['cancel_reasons']:
        print(f"  Cancel reasons: {os['cancel_reasons']}")

    # Kill switch
    ks = result["kill_switch"]
    if ks["triggered"]:
        print(f"\n  ⚠️  Kill Switch triggered on {ks['date']}: {ks['reason']}")

    # Open positions at end
    if result["open_positions"]:
        print(f"\n  Open positions at end: {len(result['open_positions'])}")
        for op in result["open_positions"][:5]:
            print(f"    {op['ticker']}: entry={op['entry_price']:.2f}, current={op['current_price']:.2f}, pnl={op['unrealized_pnl_pct']:+.1f}%")

    print("\n" + "=" * 60)
    print("V2 Baseline (close fill, min_conditions=3):")
    print("  Total Return: +10.6%, Win Rate: 74%, MDD: -22%, PF: 2.76")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
