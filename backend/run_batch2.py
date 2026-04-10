import sys; sys.path.insert(0, '.')
import asyncio, time
from datetime import date
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.strategy import StrategyProfile, BacktestResultV2, BacktestTrade, BacktestEquity
from app.services.backtester_v2 import run_backtest_v2

PROFILES = [8, 9, 10, 11]
START, END = date(2025, 6, 1), date(2026, 4, 1)

async def run_one(pid):
    async with AsyncSessionLocal() as db:
        p = (await db.execute(select(StrategyProfile).where(StrategyProfile.id == pid))).scalar_one_or_none()
        if not p:
            print(f'Profile {pid} not found')
            return
        print(f'\n=== {p.name} (id={pid}) ===', flush=True)
        print(f'  cond={p.params.get("min_conditions")}, rr={p.params.get("min_rr")}, buf={p.params.get("atr_buffer")}, fill={p.params.get("fill_model")}, max={p.params.get("max_positions")}', flush=True)
        t0 = time.time()
        result = await run_backtest_v2(
            db=db, params=p.params, overrides=p.overrides,
            stock_settings=p.stock_settings,
            start_date=START, end_date=END,
            initial_capital=1_000_000, market_filter='ALL'
        )
        elapsed = time.time() - t0
        if 'error' in result:
            print(f'  FAILED: {result["error"]}', flush=True)
            return
        m = result['metrics']
        print(f'  {elapsed:.0f}s | {m.get("total_trades",0)} trades | Return {m.get("total_return_pct",0):+.1f}% | Win {m.get("win_rate",0):.0f}% | Sharpe {m.get("sharpe_ratio",0):.2f} | DD {m.get("max_drawdown_pct",0):.1f}% | PF {m.get("profit_factor",0):.2f}', flush=True)

        bt = BacktestResultV2(
            profile_id=p.id, name=f'{p.name} batch',
            start_date=START, end_date=END, initial_capital=1_000_000,
            market_filter='ALL', params_snapshot=p.params,
            strategy_hash=result['strategy_hash'], run_hash=result['run_hash'],
            stock_universe=result['stock_universe'], data_hash=result.get('data_hash'),
            metrics=m, diagnosis=result.get('diagnosis'),
            duration_secs=result.get('duration_secs'),
            stock_count=result.get('stock_count'),
            trading_days=result.get('trading_days'), status='done'
        )
        db.add(bt)
        await db.flush()

        for t in result['trades']:
            db.add(BacktestTrade(
                backtest_id=bt.id, ticker=t['ticker'], market=t['market'],
                stock_group=t.get('stock_group'), signal_date=t['signal_date'],
                fill_date=t['fill_date'], fill_price=t['fill_price'],
                entry_source=t.get('entry_source'), position_tier=t.get('position_tier'),
                conditions_met=t.get('conditions_met'), position_size_pct=t.get('position_size_pct'),
                exit_date=t.get('exit_date'), exit_price=t.get('exit_price'),
                exit_reason=t.get('exit_reason'), stop_source=t.get('stop_source'),
                target_source=t.get('target_source'), planned_rr=t.get('planned_rr'),
                actual_rr=t.get('actual_rr'), pnl_pct=t.get('pnl_pct'),
                pnl_amount=t.get('pnl_amount'), trade_cost=t.get('trade_cost'),
                net_pnl=t.get('net_pnl'), holding_days=t.get('holding_days'),
                mae_pct=t.get('mae_pct'), mfe_pct=t.get('mfe_pct'),
                smc_trend_at_entry=t.get('smc_trend_at_entry'),
                smc_trend_at_exit=t.get('smc_trend_at_exit')
            ))

        for e in result['equity_curve']:
            db.add(BacktestEquity(
                backtest_id=bt.id, trade_date=e['trade_date'],
                equity=e['equity'], drawdown_pct=e.get('drawdown_pct'),
                cash=e.get('cash'), positions_value=e.get('positions_value'),
                open_positions=e.get('open_positions')
            ))

        p.latest_backtest_id = bt.id
        await db.commit()
        print(f'  Saved #{bt.id}', flush=True)

async def main():
    for pid in PROFILES:
        await run_one(pid)
    print('\nALL DONE', flush=True)

asyncio.run(main())
