"""
Backtest V3 — 驗證腳本

用 SMCStrategy 在新引擎跑回測，支援 Train/Validation/Test split。

Usage:
  python -m backend.run_backtest_v3                    # default: validation
  python -m backend.run_backtest_v3 --split train
  python -m backend.run_backtest_v3 --split validation
  python -m backend.run_backtest_v3 --split test
  python -m backend.run_backtest_v3 --start 2023-06-01 --end 2024-06-30  # custom range
"""
import argparse
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


def parse_args():
    parser = argparse.ArgumentParser(description="Backtest V3 runner")
    parser.add_argument("--split", type=str, default="validation",
                        choices=["train", "validation", "test"],
                        help="Data split preset (default: validation)")
    parser.add_argument("--start", type=str, default=None,
                        help="Custom start date (YYYY-MM-DD), overrides --split")
    parser.add_argument("--end", type=str, default=None,
                        help="Custom end date (YYYY-MM-DD), overrides --split")
    parser.add_argument("--capital", type=float, default=100_000,
                        help="Initial capital (default: 100000)")
    parser.add_argument("--min-conditions", type=int, default=3,
                        help="Min conditions for SMC (default: 3)")
    parser.add_argument("--min-rr", type=float, default=2.0,
                        help="Min R:R ratio (default: 2.0)")
    parser.add_argument("--max-positions", type=int, default=8,
                        help="Max concurrent positions (default: 8)")
    parser.add_argument("--strategies", type=str, default="smc_v2",
                        help="Comma-separated strategy names: smc_v2,momentum_breakout,explosion_scanner")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON (for API/pipeline)")
    return parser.parse_args()


async def main():
    args = parse_args()

    from backend.app.database import AsyncSessionLocal
    from backend.app.services.backtester_v2 import load_all_price_data
    from backend.app.services.backtest_v3 import (
        BacktestEngine, HistoricalProvider,
        SMCStrategy, MomentumBreakoutStrategy, ExplosionScannerStrategy,
        SizingModel, ExecutionModel, KillSwitch,
        calculate_metrics,
    )
    from backend.app.services.backtest_v3.provider import get_split_dates

    # Resolve dates
    if args.start and args.end:
        start = date.fromisoformat(args.start)
        end = date.fromisoformat(args.end)
        split_name = "custom"
    else:
        start, end = get_split_dates(args.split)
        split_name = args.split

    if not args.json:
        print("=" * 60)
        print(f"Backtest V3 — {split_name.upper()} split")
        print("=" * 60)

    # Load data from DB
    if not args.json:
        print("\n[1/4] Loading price data from DB...")
    t0 = time.time()
    async with AsyncSessionLocal() as db:
        stocks_info, price_data = await load_all_price_data(db, market_filter="US")
    if not args.json:
        print(f"  Loaded {len(price_data)} stocks in {time.time()-t0:.1f}s")

    # Setup
    provider = HistoricalProvider(
        price_data=price_data,
        stocks_info=stocks_info,
        start_date=start,
        end_date=end,
    )

    # Build strategy list
    STRATEGY_MAP = {
        "smc_v2": lambda: SMCStrategy(min_conditions=args.min_conditions, min_rr=args.min_rr),
        "momentum_breakout": lambda: MomentumBreakoutStrategy(min_rr=args.min_rr),
        "explosion_scanner": lambda: ExplosionScannerStrategy(),
    }
    strategy_names = [s.strip() for s in args.strategies.split(",")]
    strategies = []
    for sn in strategy_names:
        builder = STRATEGY_MAP.get(sn)
        if builder:
            strategies.append(builder())
        else:
            print(f"  Warning: unknown strategy '{sn}', skipping")
    if not strategies:
        strategies = [SMCStrategy(min_conditions=args.min_conditions, min_rr=args.min_rr)]

    sizing = SizingModel(
        risk_per_trade_pct=1.0,
        max_position_pct=20.0,
        max_positions=args.max_positions,
    )

    execution = ExecutionModel(
        fill_type="next_open",
        slippage_pct=0.05,
        gap_threshold_pct=5.0,
    )

    kill_switch = KillSwitch(enabled=True, max_daily_loss_pct=8.0)

    engine = BacktestEngine(
        strategies=strategies,
        provider=provider,
        initial_capital=args.capital,
        sizing=sizing,
        execution=execution,
        kill_switch=kill_switch,
    )

    if not args.json:
        print(f"  Strategies: {', '.join(s.strategy_name for s in strategies)}")
        print(f"  Trading days: {provider.total_days}")
        print(f"  Period: {start} → {end}")

    # Run
    if not args.json:
        print("\n[2/4] Running backtest...")
    t0 = time.time()

    async def progress(msg, pct):
        if not args.json:
            print(f"  [{pct:.0f}%] {msg}")

    result = await engine.run(progress_cb=progress)
    duration = time.time() - t0

    if not args.json:
        print(f"  Done in {duration:.1f}s")

    # Calculate metrics
    if not args.json:
        print("\n[3/4] Calculating metrics...")
    report = calculate_metrics(result)

    # Add metadata
    report["metadata"] = {
        "split": split_name,
        "start_date": str(start),
        "end_date": str(end),
        "initial_capital": args.capital,
        "min_conditions": args.min_conditions,
        "min_rr": args.min_rr,
        "max_positions": args.max_positions,
        "duration_seconds": round(duration, 1),
    }

    # JSON output mode
    if args.json:
        # Serialize for JSON (remove non-serializable)
        print(json.dumps(report, default=str, indent=2))
        return

    # Pretty print
    summary = report["portfolio_summary"]
    print("\n[4/4] Results")
    print("=" * 60)
    print(f"  Split:            {split_name.upper()}")
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

    # Tier breakdown
    if report["strategy_breakdown"].get("by_tier"):
        print("\n  Position Tier Breakdown:")
        for tier, data in report["strategy_breakdown"]["by_tier"].items():
            print(f"    {tier}: {data['total_trades']} trades, WR={data['win_rate_pct']:.1f}%, "
                  f"PF={data['profit_factor']:.2f}, avg={data['avg_pnl_pct']:+.2f}%, "
                  f"total=${data['total_pnl']:,.0f}")

    # Strategy correlation
    corr = report.get("strategy_correlation", {})
    if corr.get("matrix"):
        print("\n  Strategy Correlation:")
        for pair, val in corr["matrix"].items():
            flag = " ⚠️" if abs(val) > 0.7 else ""
            print(f"    {pair}: {val:+.3f}{flag}")
        for w in corr.get("warnings", []):
            print(f"    Warning: {w}")

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


if __name__ == "__main__":
    asyncio.run(main())
