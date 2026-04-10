"""
Backtest V3 — Core Engine

每日循環：
  1. advance_day()
  2. 更新持倉 mark-to-market（close price）
  3. 檢查出場（保守路徑 open→low→high→close）
  4. 產生 signals → filter expired → decisions → orders
  5. 執行 orders（T+1 open fill）
  6. 記錄 equity curve
  7. KillSwitch check

Spec: docs/MULTI_STRATEGY_DESIGN.md v3.1 / docs/USER_STORIES.md
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional, Callable, Awaitable

from .models import (
    Signal, Decision, Order, Position, Portfolio,
    SizingModel, ExecutionModel, KillSwitch,
)
from .provider import DataProvider, HistoricalProvider
from .strategy import BaseStrategy

logger = logging.getLogger(__name__)

ProgressCb = Optional[Callable[[str, float], Awaitable[None]]]


class BacktestEngine:
    """通用回測引擎 — 不綁任何策略"""

    def __init__(
        self,
        strategies: list[BaseStrategy],
        provider: HistoricalProvider,
        initial_capital: float = 100_000,
        sizing: Optional[SizingModel] = None,
        execution: Optional[ExecutionModel] = None,
        kill_switch: Optional[KillSwitch] = None,
    ):
        self.strategies = strategies
        self.provider = provider
        self.sizing = sizing or SizingModel()
        self.execution = execution or ExecutionModel()
        self.kill_switch = kill_switch or KillSwitch()

        self.portfolio = Portfolio(
            initial_capital=initial_capital,
            cash=initial_capital,
        )

        # 待執行的 orders（Day T 產生，Day T+1 執行）
        self._pending_orders: list[Order] = []
        # 當天產生的 signals（debug 用）
        self._all_signals: list[Signal] = []

    async def run(self, progress_cb: ProgressCb = None) -> dict:
        """主回測循環"""
        day_count = 0
        prev_equity = self.portfolio.initial_capital

        while True:
            current = self.provider.advance_day()
            if current is None:
                break
            day_count += 1

            # ── Step 1: 檢查持倉出場（保守路徑 open→low→high→close）──
            # 必須在 pending orders 之前！先出場釋放資金，再進場
            self._process_exits(current)

            # ── Step 2: 執行昨天的 pending orders（T+1 open fill）──
            self._execute_pending_orders(current)

            # ── Step 3: 更新持倉 valuation（用 close price）──
            self._mark_to_market(current)

            # ── Step 4: 記錄 equity curve ──
            self.portfolio.record_equity(current)
            self.portfolio.assert_balance()

            # ── Step 5: KillSwitch check ──
            daily_return = 0.0
            if prev_equity > 0:
                daily_return = (self.portfolio.equity - prev_equity) / prev_equity * 100
            prev_equity = self.portfolio.equity

            if not self.portfolio.kill_switch_triggered:
                reason = self.kill_switch.check(self.portfolio, daily_return)
                if reason:
                    self.portfolio.kill_switch_triggered = True
                    self.portfolio.kill_switch_reason = reason
                    self.portfolio.kill_switch_date = current
                    logger.warning(f"KillSwitch triggered on {current}: {reason}")

            # ── Step 6: 產生新 signals → decisions → orders ──
            if not self.portfolio.kill_switch_triggered:
                signals = self._generate_signals(current)
                decisions = self._signals_to_decisions(signals, current)
                orders = self._decisions_to_orders(decisions, current)
                self._pending_orders = orders  # 明天執行
            else:
                self._pending_orders = []

            # Progress callback
            if progress_cb and day_count % 20 == 0:
                await progress_cb(
                    f"Day {day_count}: {current}",
                    self.provider.progress_pct,
                )

        return self._build_result()

    # ── Step 1: Execute pending orders ──────────────────────────────

    def _execute_pending_orders(self, current_date: date):
        """執行昨天產生的 orders — T+1 open fill"""
        if not self._pending_orders:
            return

        # 鐵律 4: close orders 先（釋放資金），open orders 按 confidence 降序
        close_orders = [o for o in self._pending_orders if o.action == "close"]
        open_orders = [o for o in self._pending_orders if o.action == "open"]

        for order in close_orders + open_orders:
            self._try_fill_order(order, current_date)
            self.portfolio.orders_history.append(order)

        self._pending_orders = []

    def _try_fill_order(self, order: Order, current_date: date):
        """嘗試成交一個 order"""
        bar = self.provider.get_bar(order.ticker, current_date)
        if bar is None:
            order.cancel("no_data")
            return

        open_price = bar["Open"]

        # 如果是平倉 order — 不需要 gap check，直接 fill
        existing_pos = self.portfolio.get_position(order.ticker)
        if order.action == "close" and existing_pos:
            # close order: fill at open
            fill_price = self.execution.apply_slippage(open_price, direction="sell")
            slippage = self.execution.slippage_cost(open_price, order.requested_shares)
            commission = self.execution.commission_per_trade
            order.fill(fill_price, order.requested_shares, current_date)
            existing_pos.close(fill_price, current_date, "signal_reversal",
                               commission=commission, slippage=slippage)
            self.portfolio.close_position(existing_pos)
            return

        # 開倉 order: gap 進場保護
        prev_close = self._get_prev_close(order.ticker, current_date)
        if prev_close and prev_close > 0:
            gap_pct = abs(open_price - prev_close) / prev_close * 100
            if gap_pct > self.execution.gap_threshold_pct:
                order.cancel("gap")
                return

        # 計算最終股數（考慮資金+risk cap）
        entry = order.entry_price or open_price
        stop = order.stop_price
        if stop is None or stop >= entry:
            order.cancel("invalid_stop")
            return

        shares = self.sizing.calculate_shares(
            equity=self.portfolio.equity,
            entry=entry,
            stop=stop,
            current_portfolio_risk=self.portfolio.total_risk,
        )

        # 檢查是否超過 max_positions
        if self.portfolio.open_position_count >= self.sizing.max_positions:
            order.cancel("max_positions")
            return

        # 檢查 exposure cap
        current_exposure = self.portfolio.exposure_pct
        new_exposure = (entry * shares) / self.portfolio.equity * 100 if self.portfolio.equity > 0 else 0
        if current_exposure + new_exposure > self.sizing.max_exposure_pct:
            # 縮小到可用空間
            remaining = (self.sizing.max_exposure_pct - current_exposure) / 100 * self.portfolio.equity
            shares = int(remaining / entry)

        # 資金不足時縮小（鐵律 4）
        max_affordable = int(self.portfolio.cash * 0.95 / entry) if entry > 0 else 0
        shares = min(shares, max_affordable)

        # 最低門檻
        if shares <= 0 or entry * shares < self.execution.min_trade_value:
            order.cancel("below_minimum")
            return

        # Fill!
        fill_price = self.execution.apply_slippage(open_price, direction="buy")
        slippage = self.execution.slippage_cost(open_price, shares)
        commission = self.execution.commission_per_trade

        order.fill(fill_price, shares, current_date)

        position = Position(
            position_id=Position.create_id(),
            ticker=order.ticker,
            side=order.side,
            size=shares,
            entry_price=fill_price,
            entry_date=current_date,
            stop_price=order.stop_price,
            target_price=order.target_price,
            strategy_name=order.strategy_name,
            linked_signal_id=order.linked_signal_ids[0] if order.linked_signal_ids else "",
            capital_pool=order.capital_pool,
            entry_commission=commission,
            entry_slippage=slippage,
        )
        self.portfolio.add_position(position)

    def _get_prev_close(self, ticker: str, current_date: date) -> Optional[float]:
        """取前一個交易日的 close"""
        df = self.provider.get_ohlcv(ticker, lookback=2)
        if len(df) < 2:
            return None
        # 最後一行可能是 current_date 或之前
        # 取倒數第二行的 close
        return float(df.iloc[-2]["Close"]) if len(df) >= 2 else None

    # ── Step 2: Process exits ───────────────────────────────────────

    def _process_exits(self, current_date: date):
        """
        檢查所有持倉的出場條件。
        鐵律 2: 保守路徑 Open→Low→High→Close
        鐵律 3: Gap stop → exit at open price
        """
        positions_to_close = []

        for pos in self.portfolio.positions:
            bar = self.provider.get_bar(pos.ticker, current_date)
            if bar is None:
                continue

            open_price = bar["Open"]
            low_price = bar["Low"]
            high_price = bar["High"]

            exit_price = None
            exit_reason = None
            commission = self.execution.commission_per_trade
            slippage = 0.0

            # ── Step 1: 開盤 gap check ──
            if pos.stop_price and open_price < pos.stop_price:
                # Gap down stop: exit at open（不是 stop_price！）
                exit_price = self.execution.apply_slippage(open_price, direction="sell")
                slippage = self.execution.slippage_cost(open_price, pos.size)
                exit_reason = "gap_stop"

            elif pos.target_price and open_price > pos.target_price:
                # Gap up profit: exit at open
                exit_price = self.execution.apply_slippage(open_price, direction="sell")
                slippage = self.execution.slippage_cost(open_price, pos.size)
                exit_reason = "gap_profit"

            # ── Step 2: 日內 check（保守路徑 open→low→high→close）──
            elif pos.stop_price and low_price <= pos.stop_price:
                # 先到 low → 觸發 stop
                exit_price = self.execution.apply_slippage(pos.stop_price, direction="sell")
                slippage = self.execution.slippage_cost(pos.stop_price, pos.size)
                exit_reason = "stop"

            elif pos.target_price and high_price >= pos.target_price:
                # 再到 high → 觸發 target
                exit_price = self.execution.apply_slippage(pos.target_price, direction="sell")
                slippage = self.execution.slippage_cost(pos.target_price, pos.size)
                exit_reason = "target"

            if exit_price is not None:
                positions_to_close.append((pos, exit_price, exit_reason, commission, slippage, current_date))

        # 執行平倉（不能在迴圈中修改 list）
        for pos, price, reason, comm, slip, dt in positions_to_close:
            pos.close(price, dt, reason, commission=comm, slippage=slip)
            self.portfolio.close_position(pos)

    # ── Step 3: Mark-to-market ──────────────────────────────────────

    def _mark_to_market(self, current_date: date):
        """用 close price 更新持倉估值"""
        for pos in self.portfolio.positions:
            bar = self.provider.get_bar(pos.ticker, current_date)
            if bar is None:
                continue
            pos.update_market_data(
                price=bar["Close"],
                low=bar["Low"],
                high=bar["High"],
            )

    # ── Step 6: Generate signals → decisions → orders ───────────────

    def _generate_signals(self, current_date: date) -> list[Signal]:
        """對 universe 中每個 ticker 跑所有策略，收集 signals"""
        all_signals = []
        universe = self.provider.get_universe()

        for strategy in self.strategies:
            for ticker in universe:
                # 已經持有的 ticker，不重複開倉
                if self.portfolio.get_position(ticker):
                    continue
                try:
                    signals = strategy.generate_signals(ticker, self.provider)
                    for s in signals:
                        errors = s.validate()
                        if errors:
                            logger.warning(f"Invalid signal for {ticker}: {errors}")
                            continue
                        # 過期 filter
                        if s.is_expired(current_date):
                            continue
                        all_signals.append(s)
                except Exception as e:
                    logger.error(f"Strategy {strategy.strategy_name} error on {ticker}: {e}")

        self._all_signals.extend(all_signals)
        return all_signals

    def _signals_to_decisions(self, signals: list[Signal], current_date: date) -> list[Decision]:
        """
        Phase 1A: 單策略直通模式 — 每個 buy signal 直接轉 decision。
        同 ticker 只取 confidence 最高的。
        """
        # 只處理 buy signals（有 entry + stop）
        buy_signals = [s for s in signals if s.action == "buy" and s.has_entry()]

        # 同 ticker 取 confidence 最高
        best_by_ticker: dict[str, Signal] = {}
        for s in buy_signals:
            existing = best_by_ticker.get(s.ticker)
            if existing is None or s.confidence > existing.confidence:
                best_by_ticker[s.ticker] = s

        decisions = []
        for s in best_by_ticker.values():
            d = Decision(
                decision_id=Decision.create_id(),
                ticker=s.ticker,
                action="open",
                side=s.side,
                strategy_name=s.strategy_name,
                capital_pool="default",
                reason=f"{s.strategy_name} buy signal, confidence={s.confidence:.2f}",
                linked_signal_ids=[s.signal_id],
                confidence=s.confidence,
                entry_price=s.price_hint["entry"],
                stop_price=s.price_hint["stop"],
                target_price=s.price_hint.get("target"),
            )
            decisions.append(d)

        # 按 confidence 降序排列
        decisions.sort(key=lambda d: d.confidence, reverse=True)
        return decisions

    def _decisions_to_orders(self, decisions: list[Decision], current_date: date) -> list[Order]:
        """Decision → Order（1:1）"""
        orders = []
        for d in decisions:
            order = Order(
                order_id=Order.create_id(),
                ticker=d.ticker,
                side=d.side,
                order_type="market",
                requested_shares=0,  # Execution 階段算
                status="pending",
                created_date=current_date,
                linked_decision_id=d.decision_id,
                linked_signal_ids=d.linked_signal_ids,
                capital_pool=d.capital_pool,
                entry_price=d.entry_price,
                stop_price=d.stop_price,
                target_price=d.target_price,
                strategy_name=d.strategy_name,
            )
            orders.append(order)
        return orders

    # ── Build result ────────────────────────────────────────────────

    def _build_result(self) -> dict:
        """回測結果 — 三層報表的原始數據"""
        trades = [p.to_trade_record() for p in self.portfolio.closed_trades]

        # 未平倉也記錄（但標記 open）
        open_positions = [{
            "ticker": p.ticker,
            "strategy_name": p.strategy_name,
            "entry_date": str(p.entry_date),
            "entry_price": p.entry_price,
            "current_price": p.current_price,
            "unrealized_pnl_pct": round(p.unrealized_pnl_pct, 2),
            "size": p.size,
            "holding_days": p.holding_days,
        } for p in self.portfolio.positions]

        # Order 統計
        total_orders = len(self.portfolio.orders_history)
        filled = sum(1 for o in self.portfolio.orders_history if o.status == "filled")
        cancelled = sum(1 for o in self.portfolio.orders_history if o.status == "cancelled")
        cancel_reasons = {}
        for o in self.portfolio.orders_history:
            if o.cancel_reason:
                cancel_reasons[o.cancel_reason] = cancel_reasons.get(o.cancel_reason, 0) + 1

        return {
            "trades": trades,
            "open_positions": open_positions,
            "equity_curve": self.portfolio.equity_curve,
            "initial_capital": self.portfolio.initial_capital,
            "final_equity": round(self.portfolio.equity, 2),
            "total_trades": len(trades),
            "order_stats": {
                "total": total_orders,
                "filled": filled,
                "cancelled": cancelled,
                "cancel_reasons": cancel_reasons,
            },
            "kill_switch": {
                "triggered": self.portfolio.kill_switch_triggered,
                "reason": self.portfolio.kill_switch_reason,
                "date": str(self.portfolio.kill_switch_date) if self.portfolio.kill_switch_date else None,
            },
        }
