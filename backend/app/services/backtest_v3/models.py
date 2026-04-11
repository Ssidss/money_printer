"""
Backtest V3 — Core Data Models
Signal / Decision / Order / Position / Portfolio

Spec: docs/MULTI_STRATEGY_DESIGN.md v3.1
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


# ── Signal ──────────────────────────────────────────────────────────

@dataclass
class Signal:
    """策略的「意見」— 不是 trade，是 opinion"""

    # 必填
    signal_id: str
    ticker: str
    side: str                   # "long"
    action: str                 # "buy" | "sell" | "hold" | "watch"
    confidence: float           # 0.0 ~ 1.0
    strategy_name: str          # "smc_v2" | "momentum_breakout" | ...
    strategy_type: str          # "trend" | "breakout" | "mean_reversion" | "sentiment"
    timeframe: str              # "1d" | "1w" | "1h"
    timestamp: date             # 信號產生日期
    expiry: date                # 信號過期日期

    # 選填 — position_tier 從 price_hint 提出來方便追蹤
    position_tier: str = "標準"   # "核心" | "標準" | "探索"
    price_hint: Optional[dict] = None
    # {
    #     "entry": float,
    #     "stop": float,
    #     "target": float,
    #     "rr_ratio": float,
    #     "position_tier": str,  # "核心" | "標準" | "探索"
    # }

    meta: dict = field(default_factory=dict)

    @staticmethod
    def create_id() -> str:
        return str(uuid.uuid4())

    def is_expired(self, current_date: date) -> bool:
        return current_date > self.expiry

    def has_entry(self) -> bool:
        return (
            self.price_hint is not None
            and self.price_hint.get("entry") is not None
            and self.price_hint.get("stop") is not None
        )

    def validate(self) -> list[str]:
        errors = []
        if not 0.0 <= self.confidence <= 1.0:
            errors.append(f"confidence {self.confidence} not in [0, 1]")
        if self.strategy_type not in ("trend", "breakout", "mean_reversion", "sentiment"):
            errors.append(f"invalid strategy_type: {self.strategy_type}")
        if self.expiry <= self.timestamp:
            errors.append(f"expiry {self.expiry} <= timestamp {self.timestamp}")
        if self.action == "buy" and not self.has_entry():
            errors.append("buy signal must have price_hint with entry + stop")
        return errors


# ── Decision ────────────────────────────────────────────────────────

@dataclass
class Decision:
    """Signal 匯總後的「行動指令」— 一個 ticker 只有一個 decision"""

    decision_id: str
    ticker: str
    action: str                 # "open" | "close" | "reduce" | "hold"
    side: str = "long"
    size_pct: float = 0.0       # 佔資金池 %（意圖，Execution 算實際股數）
    size_shares: Optional[int] = None  # Execution 填入
    strategy_name: str = ""
    capital_pool: str = "default"
    position_tier: str = "標準"
    reason: str = ""
    linked_signal_ids: list[str] = field(default_factory=list)
    priority: int = 0           # close > open；同類按 confidence

    # Signal 的 price_hint 傳遞下來
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    confidence: float = 0.0

    @staticmethod
    def create_id() -> str:
        return str(uuid.uuid4())


# ── Order ───────────────────────────────────────────────────────────

@dataclass
class Order:
    """Decision 和 Position 之間的橋樑 — 追蹤成交狀態"""

    order_id: str
    ticker: str
    side: str = "long"
    action: str = "open"                # "open" | "close" — 明確標記意圖
    order_type: str = "market"          # v1 只做 market
    requested_shares: int = 0
    status: str = "pending"             # "pending" | "filled" | "cancelled"
    created_date: Optional[date] = None
    linked_decision_id: str = ""
    linked_signal_ids: list[str] = field(default_factory=list)
    capital_pool: str = "default"

    # 進場參考價（from Decision）
    entry_price: Optional[float] = None
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    strategy_name: str = ""
    position_tier: str = "標準"

    # 成交後填入
    fill_price: Optional[float] = None
    fill_date: Optional[date] = None
    fill_shares: Optional[int] = None
    cancel_reason: Optional[str] = None  # "gap" | "insufficient_funds" | "expired" | "below_minimum"

    @staticmethod
    def create_id() -> str:
        return str(uuid.uuid4())

    def fill(self, price: float, shares: int, fill_date: date):
        self.fill_price = price
        self.fill_shares = shares
        self.fill_date = fill_date
        self.status = "filled"

    def cancel(self, reason: str):
        self.cancel_reason = reason
        self.status = "cancelled"


# ── Position ────────────────────────────────────────────────────────

@dataclass
class Position:
    """一筆持倉 — open 時建立，close 時凍結（不可竄改）"""

    position_id: str
    ticker: str
    side: str
    size: int                   # 股數
    entry_price: float
    entry_date: date
    stop_price: Optional[float] = None
    target_price: Optional[float] = None
    strategy_name: str = ""
    linked_signal_id: str = ""
    capital_pool: str = "default"
    position_tier: str = "標準"   # "核心" | "標準" | "探索"

    # 動態更新（每天）
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    mae: float = 0.0            # Max Adverse Excursion（最大浮虧金額）
    mfe: float = 0.0            # Max Favorable Excursion（最大浮盈金額）
    holding_days: int = 0

    # 平倉後填入（鐵律 6：不可竄改）
    exit_price: Optional[float] = None
    exit_date: Optional[date] = None
    exit_reason: Optional[str] = None
    realized_pnl: Optional[float] = None
    realized_pnl_pct: Optional[float] = None

    # 成本追蹤
    entry_commission: float = 0.0
    entry_slippage: float = 0.0
    exit_commission: float = 0.0
    exit_slippage: float = 0.0

    @staticmethod
    def create_id() -> str:
        return str(uuid.uuid4())

    @property
    def is_open(self) -> bool:
        return self.exit_date is None

    @property
    def cost_basis(self) -> float:
        return self.entry_price * self.size

    @property
    def current_value(self) -> float:
        return self.current_price * self.size

    @property
    def gross_pnl(self) -> Optional[float]:
        if self.realized_pnl is None:
            return None
        return self.realized_pnl + self.total_cost

    @property
    def total_cost(self) -> float:
        return self.entry_commission + self.entry_slippage + self.exit_commission + self.exit_slippage

    @property
    def risk_amount(self) -> float:
        """當前風險金額：用於 portfolio risk cap"""
        if self.stop_price is None or self.stop_price >= self.entry_price:
            return 0.0
        return (self.entry_price - self.stop_price) * self.size

    def update_market_data(self, price: float, low: float, high: float):
        """每日更新 — mark-to-market 用 close price"""
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.size
        self.unrealized_pnl_pct = (price - self.entry_price) / self.entry_price * 100 if self.entry_price else 0
        self.holding_days += 1

        # MAE / MFE（用日內 low/high 的差距）
        adverse = (low - self.entry_price) * self.size
        favorable = (high - self.entry_price) * self.size
        self.mae = min(self.mae, adverse)
        self.mfe = max(self.mfe, favorable)

    def close(self, exit_price: float, exit_date: date, exit_reason: str,
              commission: float = 0.0, slippage: float = 0.0):
        """平倉 — 鐵律 6：一旦 close 不可再修改"""
        if not self.is_open:
            raise ValueError(f"Position {self.position_id} already closed")
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.exit_reason = exit_reason
        self.exit_commission = commission
        self.exit_slippage = slippage
        self.realized_pnl = (exit_price - self.entry_price) * self.size - self.total_cost
        self.realized_pnl_pct = (exit_price - self.entry_price) / self.entry_price * 100 if self.entry_price else 0

    def to_trade_record(self) -> dict:
        """輸出到 trade log"""
        return {
            "position_id": self.position_id,
            "ticker": self.ticker,
            "side": self.side,
            "strategy_name": self.strategy_name,
            "capital_pool": self.capital_pool,
            "entry_date": str(self.entry_date),
            "entry_price": self.entry_price,
            "exit_date": str(self.exit_date) if self.exit_date else None,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "size": self.size,
            "gross_pnl": self.gross_pnl,
            "commission": self.entry_commission + self.exit_commission,
            "slippage_cost": self.entry_slippage + self.exit_slippage,
            "net_pnl": self.realized_pnl,
            "pnl_pct": self.realized_pnl_pct,
            "mae": self.mae,
            "mfe": self.mfe,
            "holding_days": self.holding_days,
            "position_tier": self.position_tier,
            "confidence": 0.0,  # filled by caller
        }


# ── Portfolio ───────────────────────────────────────────────────────

@dataclass
class Portfolio:
    """回測中的虛擬帳戶"""

    initial_capital: float
    cash: float
    positions: list[Position] = field(default_factory=list)
    closed_trades: list[Position] = field(default_factory=list)
    orders_history: list[Order] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)

    # KillSwitch tracking
    consecutive_losses: int = 0
    peak_equity: float = 0.0
    kill_switch_triggered: bool = False
    kill_switch_reason: Optional[str] = None
    kill_switch_date: Optional[date] = None

    def __post_init__(self):
        if self.peak_equity == 0.0:
            self.peak_equity = self.initial_capital

    @property
    def equity(self) -> float:
        return self.cash + sum(p.current_value for p in self.positions)

    @property
    def exposure_pct(self) -> float:
        if self.equity <= 0:
            return 0.0
        return (self.equity - self.cash) / self.equity * 100

    @property
    def open_position_count(self) -> int:
        return len(self.positions)

    @property
    def current_drawdown_pct(self) -> float:
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.equity) / self.peak_equity * 100

    @property
    def total_risk(self) -> float:
        """所有持倉同時停損的總風險金額"""
        return sum(p.risk_amount for p in self.positions)

    @property
    def total_risk_pct(self) -> float:
        if self.equity <= 0:
            return 0.0
        return self.total_risk / self.equity * 100

    def get_position(self, ticker: str) -> Optional[Position]:
        for p in self.positions:
            if p.ticker == ticker:
                return p
        return None

    def add_position(self, position: Position):
        self.cash -= position.cost_basis + position.entry_commission + position.entry_slippage
        self.positions.append(position)

    def close_position(self, position: Position):
        """平倉：移到 closed_trades，回收現金"""
        self.cash += position.exit_price * position.size - position.exit_commission - position.exit_slippage
        self.positions.remove(position)
        self.closed_trades.append(position)

        # 更新連續虧損
        if position.realized_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def record_equity(self, current_date: date):
        """每日記錄 equity curve"""
        eq = self.equity
        self.peak_equity = max(self.peak_equity, eq)
        dd = self.current_drawdown_pct

        self.equity_curve.append({
            "date": str(current_date),
            "equity": round(eq, 2),
            "drawdown_pct": round(dd, 2),
            "cash": round(self.cash, 2),
            "positions_value": round(eq - self.cash, 2),
            "open_positions": self.open_position_count,
        })

    def assert_balance(self):
        """Equity 恆等式 — 每天必須通過"""
        expected = self.cash + sum(p.current_value for p in self.positions)
        actual = self.equity
        diff = abs(expected - actual)
        if diff > 0.01:
            raise AssertionError(
                f"Portfolio balance check failed: cash({self.cash:.2f}) + "
                f"positions({sum(p.current_value for p in self.positions):.2f}) = "
                f"{expected:.2f} != equity {actual:.2f}"
            )


# ── Config dataclasses ──────────────────────────────────────────────

@dataclass
class SizingModel:
    risk_per_trade_pct: float = 1.0
    max_position_pct: float = 20.0
    max_positions: int = 10
    max_exposure_pct: float = 100.0
    max_portfolio_risk_pct: float = 5.0

    def calculate_shares(
        self, equity: float, entry: float, stop: float,
        current_portfolio_risk: float = 0.0,
    ) -> int:
        if entry <= stop or entry <= 0 or equity <= 0:
            return 0

        risk_per_share = entry - stop
        risk_amount = equity * (self.risk_per_trade_pct / 100)
        shares = int(risk_amount / risk_per_share)

        # 單支最大倉位
        max_shares_by_position = int(equity * (self.max_position_pct / 100) / entry)
        shares = min(shares, max_shares_by_position)

        # Portfolio risk cap
        remaining_risk_budget = equity * (self.max_portfolio_risk_pct / 100) - current_portfolio_risk
        if remaining_risk_budget <= 0:
            return 0
        max_shares_by_risk_cap = int(remaining_risk_budget / risk_per_share)
        shares = min(shares, max_shares_by_risk_cap)

        return max(shares, 0)


@dataclass
class ExecutionModel:
    fill_type: str = "next_open"
    slippage_pct: float = 0.05          # 0.05%
    commission_per_trade: float = 0.0
    gap_threshold_pct: float = 5.0
    gap_stop_enabled: bool = True
    path_assumption: str = "conservative"  # open→low→high→close
    min_trade_value: float = 100.0

    def apply_slippage(self, price: float, side: str = "long", direction: str = "buy") -> float:
        """滑價：買入價上調，賣出價下調"""
        if direction == "buy":
            return price * (1 + self.slippage_pct / 100)
        else:
            return price * (1 - self.slippage_pct / 100)

    def slippage_cost(self, price: float, shares: int) -> float:
        return price * shares * (self.slippage_pct / 100)


@dataclass
class KillSwitch:
    max_drawdown_pct: float = 30.0
    max_consecutive_losses: int = 15
    max_daily_loss_pct: float = 5.0
    min_rolling_sharpe: float = 0.0
    enabled: bool = True

    def check(self, portfolio: Portfolio, daily_return_pct: float = 0.0) -> Optional[str]:
        if not self.enabled:
            return None
        if portfolio.current_drawdown_pct > self.max_drawdown_pct:
            return f"MDD {portfolio.current_drawdown_pct:.1f}% > {self.max_drawdown_pct}%"
        if portfolio.consecutive_losses > self.max_consecutive_losses:
            return f"consecutive losses {portfolio.consecutive_losses} > {self.max_consecutive_losses}"
        if daily_return_pct < -self.max_daily_loss_pct:
            return f"daily loss {daily_return_pct:.1f}% > {self.max_daily_loss_pct}%"
        return None
