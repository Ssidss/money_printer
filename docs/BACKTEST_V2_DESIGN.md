# 回測引擎 v2 設計文件

> 版本：Draft v2.0 | 2026-04-08
> 目的：將回測引擎從 v1（技術分加權）升級為 v2（SMC 分層決策），使回測結果反映真實策略表現
> v2.0 變更：修正 12 項回測偏誤風險（成交模型、時點規則、成本模型等）

---

## 一、為什麼要升級

現在回測跑的是 v1 邏輯，但你實際看盤用的是 v2 策略。兩套規則完全不同：

| | v1 回測（現在） | v2 策略（你在用的） |
|--|---------------|-------------------|
| **買入依據** | 技術分 ≥ 60 | SMC 結構 + 條件計數 ≥ 2 |
| **進場價** | 當天收盤價 | OB 上緣 / FVG CE / Swing Low |
| **停損** | 固定 -7% | OB 底部 - ATR buffer |
| **停利** | 追蹤停損 5% | Bearish OB / BSL / Swing High |
| **倉位** | 固定 10% | 動態 3-20%（依條件數） |
| **SMC 角色** | 只當過濾器（下降不買） | 核心決策（定方向 + 定價位） |
| **情緒** | 不參與 | 反指標模型，影響倉位升降級 |
| **多時間框架** | 無 | 月→週→日 層級過濾 |
| **成本模型** | 無 | 手續費 + 稅 + 滑價 |

**結論**：v1 回測結果無法代表 v2 策略的真實績效，必須升級。

---

## 二、交易時點與成交模型（鐵律）

> 這是回測最容易作弊的地方。以下規則不可違反。

### 2.1 時點規則：T 日算，T+1 才能成交

```
鐵律：EOD（End-of-Day）回測模式

  T 日收盤後：
    1. 用 T 日（含）以前的所有 K 棒計算 SMC
    2. 生成 EntryPlan（entry_price / stop / target）
    3. 決定「明天要不要掛單」

  T+1 日：
    4. 用 T+1 日的 OHLC 判斷是否成交
    5. 成交價依「成交模型」決定（見 2.2）

  絕對禁止：
    ✗ 用 T 日收盤資料生成信號，又用 T 日收盤價成交（look-ahead bias）
    ✗ 用 T 日盤中數據做決策（日線回測無盤中資料）
```

### 2.2 成交模型：限價單模型（預設，Phase 1）

回測支援三種成交模型，Phase 1 預設使用**限價單模型**：

```
模型 A：限價單模型（預設 — 中性偏保守）
  ────────────────────────────────────────
  買入成交條件：T+1 日 low <= entry_price
  買入成交價格：entry_price（假設限價單掛在 entry_price 被觸發）
  
  賣出停損條件：T+1 日 low <= stop_price
  賣出停損價格：min(open, stop_price)
    （如果開盤就跳空跌破停損，用開盤價成交，不用理想價）
  
  賣出停利條件：T+1 日 high >= target_price
  賣出停利價格：max(open, target_price)
    （如果開盤就跳空突破目標，用開盤價成交）

  特殊：gap 穿越
    如果 T+1 open 直接低於 entry_price → 成交價 = open（不是 entry_price）
    如果 T+1 open 直接低於 stop_price → 成交價 = open（滑價真實反映）


模型 B：保守模型（可選 — 最不會自欺）
  ────────────────────────────────────────
  買入成交條件：同模型 A
  買入成交價格：entry_price + slippage（多付一點）
  賣出停損價格：stop_price - slippage（少拿一點）
  賣出停利價格：target_price - slippage（少拿一點）
  
  slippage = max(ATR * 0.02, price * 0.001)


模型 C：收盤價模型（可選 — 最簡單，有偏誤）
  ────────────────────────────────────────
  買入成交條件：T+1 close 在 entry_zone 範圍內
  買入成交價格：T+1 close
  （注意：此模型偏樂觀，不建議作為主要模型）
```

### 2.3 同日多事件衝突：保守假設（鐵律）

```
問題：T+1 日同時觸發停損和停利（high >= target 且 low <= stop）
日線資料無法判斷先後順序。

鐵律：對 long 倉位，同日衝突一律先算停損。

理由：
  1. 保守假設不會讓回測過度樂觀
  2. 真實交易中，停損通常掛的是 stop-market，會先被觸發
  3. 如果回測在保守假設下仍然賺錢，才是真正可信的策略

完整優先順序（由高到低）：
  1. 停損（low <= stop_price）
  2. 結構反轉出場（MSS 確認）
  3. 停利（high >= target_price）
  4. 保本停損升級（不出場，只調停損價）
  5. 繼續持有

例外：如果 open > target_price（開盤直接跳空突破目標），先算停利。
      因為開盤就高於目標，停損不可能先觸發。
```

### 2.4 進場區間定義

```
EntryPlan 產生的 entry_price 是「理想進場點」（單一價格）。
回測中用 entry_zone 判斷是否可進場：

  entry_zone_top = entry_price × (1 + entry_tolerance)
  entry_zone_bottom = stop_price
  
  entry_tolerance 預設 = 0.5 ATR（ATR-based，非固定 %）
    （低波動股容忍小，高波動股容忍大）

  成交判斷：
    if T+1_low <= entry_zone_top:
      成交價 = min(T+1_open, entry_price)  # 不會買比理想價更貴
      （開盤就在區間內 → 用開盤價；盤中跌到 → 用 entry_price）

  不成交情況：
    T+1 全天最低都高於 entry_zone_top → 沒機會買到，跳過
    T+1 open < stop_price → 已經跌破停損，不接刀
```

---

## 三、v2 回測核心邏輯

### 3.1 每日決策流程

```
時間軸：
  T 日收盤 → 計算 SMC + EntryPlan → 生成信號
  T+1 日   → 執行信號（用 T+1 OHLC 判斷成交）

每個交易日 T+1，執行順序：

  Phase A：持倉管理（先賣後買）
  ──────────────────────────────────
  for each position:
    1. 檢查停損（最高優先）
    2. 檢查結構反轉
    3. 檢查停利
    4. 檢查保本停損升級
    5. 更新 MAE/MFE

  Phase B：新倉進場
  ──────────────────────────────────
  for each pending signal (T 日生成的):
    1. 檢查是否仍有空位（max_positions）
    2. 檢查現金是否足夠
    3. 檢查 portfolio heat
    4. 用 T+1 OHLC 判斷成交（見 2.2 成交模型）
    5. 倉位排序：核心 > 標準 > 探索（優先買入高信心的）
```

### 3.2 買入條件

```python
def generate_signal(entry_plan, portfolio_state):
    """T 日收盤後：決定是否在 T+1 掛單（信號生成，不是成交）"""

    # 1. 推薦等級 ≥ 觀察（conditions_met ≥ min_conditions）
    if entry_plan.recommendation == "不推薦":
        return None

    # 2. R:R ≥ min_rr
    if entry_plan.rr_ratio < min_rr:
        return None

    # 3. MTF 沒有禁止
    if entry_plan.mtf_gate.max_tier == "none":
        return None

    # 4. Portfolio 限制
    if portfolio_state.open_positions >= max_positions:
        return None
    if portfolio_state.total_heat >= max_heat:
        return None

    return PendingSignal(
        entry_price=entry_plan.entry_price,
        stop_price=entry_plan.stop_price,
        target_price=entry_plan.target_price,
        position_size=calc_position_size(entry_plan, portfolio_state),
    )


def try_fill(signal, t1_ohlc, fill_model="limit"):
    """T+1 日：用實際價格判斷是否成交"""

    if fill_model == "limit":
        entry_zone_top = signal.entry_price * (1 + entry_tolerance_atr)

        # 開盤就跌破停損 → 不買
        if t1_ohlc.open < signal.stop_price:
            return None

        # 盤中有到過進場區間
        if t1_ohlc.low <= entry_zone_top:
            fill_price = min(t1_ohlc.open, signal.entry_price)
            return Fill(price=fill_price)

        # 全天都高於進場區間 → 沒機會
        return None
```

### 3.3 賣出條件

```python
def check_exit(position, t1_ohlc, smc_today):
    """T+1 日：用 T+1 OHLC 檢查是否出場
    
    smc_today = T 日收盤後算的 SMC（不用 T+1 資料，避免 look-ahead）
    """

    # ── 0. 開盤 gap 處理 ──
    if t1_ohlc.open <= position.stop_price:
        return Exit("停損", price=t1_ohlc.open, reason="開盤跳空跌破停損")
    if t1_ohlc.open >= position.target_price:
        return Exit("停利", price=t1_ohlc.open, reason="開盤跳空突破目標")

    # ── 1. 停損（最高優先） ──
    if t1_ohlc.low <= position.stop_price:
        return Exit("停損", price=position.stop_price)

    # ── 2. 結構反轉（MSS 確認才出） ──
    trend = smc_today.structure.trend
    has_mss = any(
        e.event_type == "MSS" and e.direction == "bearish"
        for e in smc_today.structure.events[-3:]
    )
    if trend in ("downtrend", "weak_downtrend") and has_mss:
        exit_price = t1_ohlc.open  # 反轉確認後，T+1 開盤出場
        return Exit("結構反轉", price=exit_price, reason="Bearish MSS 確認")

    # ── 3. 停利 ──
    if t1_ohlc.high >= position.target_price:
        return Exit("停利", price=position.target_price)

    # ── 4. 保本停損升級（不出場，只調價） ──
    #    條件：新的 Bullish BOS 成立 → 停損拉到最新 HL 下方
    #    或簡化版：達到 1R 利潤 → 停損拉到進場價
    one_r = position.entry_price + (position.entry_price - position.original_stop)
    if t1_ohlc.high >= one_r and position.stop_price < position.entry_price:
        # 結構型保本：找最新 HL
        latest_hl = smc_today.structure.swing_lows[-1].price if smc_today.structure.swing_lows else None
        if latest_hl and latest_hl > position.entry_price:
            position.stop_price = latest_hl - position.atr_buffer
        else:
            position.stop_price = position.entry_price  # fallback: 拉到進場價

    # ── 5. 更新 MAE/MFE ──
    position.mae = min(position.mae, (t1_ohlc.low - position.entry_price) / position.entry_price)
    position.mfe = max(position.mfe, (t1_ohlc.high - position.entry_price) / position.entry_price)

    return None  # 繼續持有
```

### 3.4 倉位計算（完整版）

```python
def calc_position_size(entry_plan, portfolio_state):
    """計算最終倉位，受多重約束"""

    total_equity = portfolio_state.total_equity  # 現金 + 持倉市值

    # ── 1. 策略倉位（tier-based） ──
    tier_pct = entry_plan.max_position_pct / 100  # 4%/10%/18%
    tier_size = total_equity * tier_pct

    # ── 2. MTF 限制 ──
    mtf_pct = entry_plan.mtf_gate.max_position_pct / 100
    mtf_size = total_equity * mtf_pct

    # ── 3. 單筆風險上限（最重要的限制） ──
    #    每筆交易最多虧 total_equity 的 risk_per_trade_pct
    risk_per_trade_pct = 0.02  # 預設 2%
    risk_per_share = entry_plan.entry_price - entry_plan.stop_price
    if risk_per_share <= 0:
        return 0  # 停損在進場上方，不合理
    max_shares_by_risk = (total_equity * risk_per_trade_pct) / risk_per_share
    risk_budget_size = max_shares_by_risk * entry_plan.entry_price

    # ── 4. 現金可用 ──
    cash_size = portfolio_state.available_cash

    # ── 5. Portfolio Heat（總風險敞口） ──
    #    所有持倉的 unrealized risk 合計不超過 max_heat
    max_heat = 0.10  # 總投資組合最多承受 10% 風險
    current_heat = sum(
        pos.shares * (pos.entry_price - pos.stop_price) / total_equity
        for pos in portfolio_state.positions
    )
    remaining_heat = max(0, max_heat - current_heat)
    heat_size = (remaining_heat * total_equity) / risk_per_share * entry_plan.entry_price if risk_per_share > 0 else 0

    # ── 6. 市場別限制 ──
    #    US 持倉不超過 70%，TW 持倉不超過 50%
    market = entry_plan.market
    market_limit = {"US": 0.70, "TW": 0.50}.get(market, 0.60)
    current_market_exposure = sum(
        pos.market_value for pos in portfolio_state.positions
        if pos.market == market
    ) / total_equity
    market_remaining = max(0, market_limit - current_market_exposure) * total_equity

    # ── 最終倉位 = 所有限制的最小值 ──
    final_size = min(
        tier_size,
        mtf_size,
        risk_budget_size,
        cash_size,
        heat_size,
        market_remaining,
    )

    return max(0, final_size)
```

---

## 四、成本模型（Phase 1 就要有）

> 不帶成本的回測結果會偏樂觀，尤其對台股和頻繁交易。

### 4.1 美股成本

```python
US_COST = {
    "commission":    0,           # 多數券商零手續費
    "sec_fee_rate":  0.0000278,   # SEC fee (賣出時)
    "slippage_pct":  0.0005,      # 0.05% 滑價（中小型股可調高）
}

def us_trade_cost(price, shares, side):
    """計算美股單筆交易成本"""
    notional = price * shares
    cost = notional * US_COST["slippage_pct"]
    if side == "sell":
        cost += notional * US_COST["sec_fee_rate"]
    return cost
```

### 4.2 台股成本

```python
TW_COST = {
    "commission_rate": 0.001425,  # 手續費 0.1425%（買賣都收）
    "discount":        0.6,       # 電子下單折扣（通常 6 折）
    "tax_rate":        0.003,     # 證交稅 0.3%（僅賣出）
    "slippage_ticks":  1,         # 滑價 1 tick
}

def tw_trade_cost(price, shares, side):
    """計算台股單筆交易成本"""
    notional = price * shares
    commission = notional * TW_COST["commission_rate"] * TW_COST["discount"]
    tax = notional * TW_COST["tax_rate"] if side == "sell" else 0
    # 台股 1000 股 1 張，tick 依價格級距
    slippage = tw_tick_size(price) * TW_COST["slippage_ticks"] * shares
    return commission + tax + slippage
```

### 4.3 成本對績效的影響預估

```
假設：每筆持有 15 天，年交易 24 次
美股：0.05% × 2（買賣）× 24 = 年 2.4% 成本
台股：(0.085% + 0.3% + 0.085%) × 24 = 年 11.3% 成本

→ 台股的成本吃掉的報酬遠高於美股
→ 台股策略必須有更高的勝率或更大的 R:R 才能覆蓋成本
→ 不帶成本的台股回測基本上不可信
```

---

## 五、回測參數設計

### 5.1 基本參數（UI 必須有）

| 參數 | 預設 | 說明 |
|------|------|------|
| 回測期間 | 2024-01-01 ~ today | 起訖日期 |
| 初始資金 | 1,000,000 | TWD 或 USD |
| 最大同時持倉 | 8 | 同時持有幾支 |
| 市場 | US / TW / ALL | 回測範圍 |
| **回測模式** | smc_only | 見 5.5 |
| **成交模型** | 限價單 | 限價單 / 保守 / 收盤價 |
| **成本模型** | 開 | 開/關 |

### 5.2 策略參數（可調整）

| 參數 | 預設 | 範圍 | 說明 |
|------|------|------|------|
| 進場容許偏離 | 0.5 ATR | 0-2 ATR | ATR-based，非固定 % |
| 最低 R:R | 2.0 | 1.0-5.0 | 風報比門檻 |
| 最少條件數 | 2 | 1-4 | conditions_met 最低要求 |
| 停損模式 | SMC 結構 | SMC結構 / 固定% / ATR倍數 | 停損依據 |
| 固定停損% | 7% | 3-15% | 停損模式=固定%時使用 |
| 停利模式 | SMC 目標 | SMC目標 / 固定% / 追蹤停損 | 停利依據 |
| 結構反轉出場 | MSS 全出 | MSS全出 / CHoCH減半+MSS全出 / 關 |
| 保本停損模式 | 結構型 | 結構型(新HL) / 簡化型(1R) / 關 |

### 5.3 倉位與風控參數

| 參數 | 預設 | 說明 |
|------|------|------|
| 倉位模式 | v2 動態 | v2動態(3-20%) / 固定% |
| 固定倉位% | 10% | 倉位模式=固定%時使用 |
| 單筆風險上限 | 2% | 單筆最多虧 equity 的 N% |
| Portfolio Heat 上限 | 10% | 所有持倉總風險上限 |
| US 曝險上限 | 70% | 美股最大佔比 |
| TW 曝險上限 | 50% | 台股最大佔比 |
| 情緒影響 | 開 | 情緒分是否調整倉位 |
| MTF 過濾 | 開 | 多時間框架是否限制倉位 |

### 5.4 參數依賴矩陣

> 某些參數組合會互斥。UI 應根據此矩陣 disable 不相關的欄位。

```
停損模式 = "SMC 結構" 時：
  ✓ 保本停損模式 可選（結構型/簡化型/關）
  ✗ 固定停損% 無效（greyed out）

停損模式 = "固定%" 時：
  ✓ 固定停損% 啟用
  ✗ 保本停損模式 固定為「簡化型」或「關」（無結構可追蹤）

停利模式 = "SMC 目標" 時：
  ✓ 結構反轉出場 可選
  ✗ 追蹤停損% 無效

停利模式 = "追蹤停損" 時：
  ✓ 追蹤停損% 啟用（需新增此參數）
  ✗ 結構反轉出場 意義降低（但仍可開）

倉位模式 = "固定%" 時：
  ✓ 固定倉位% 啟用
  ✗ 情緒影響 無效（倉位不動態）
  ✗ MTF 過濾 無效（倉位不分級）
  ✗ 單筆風險上限 仍然有效（作為上限約束）

情緒影響 = "關" 時：
  → entry_plan 裡的 tier 用 conditions_met 原始計算
  → 不做情緒升降級
  → 條件計數最多 3/4（第 4 個條件是情緒，關掉就少一個）
```

### 5.5 回測模式（必須標示）

```
三種回測模式，報表上必須明確標示：

1. smc_only（預設）
   · 只用 SMC 結構 + MTF + R:R 做決策
   · 情緒 gate 不參與
   · 條件計數最多 3/4
   · 適用：Phase 1 / 無歷史情緒資料

2. smc_neutral_sentiment
   · SMC + 固定中性情緒（50 分）
   · 情緒 gate 永遠 neutral，不影響倉位
   · 條件計數可能 4/4（如果其他 3 條件都滿足）
   · 適用：想看「情緒永遠沒影響」的基線表現

3. smc_full（完整策略）
   · SMC + 歷史情緒分數（從 news DB 讀取）
   · 完整策略，含情緒升降級
   · 適用：有歷史新聞資料的回測

報表標示範例：
  ┌──────────────────────────────────┐
  │ 回測 #12 — 2024-01-01 ~ 2026-04-01       │
  │ 模式：smc_only │ 成交：限價單 │ 成本：開  │
  └──────────────────────────────────┘
```

---

## 六、SMC 參數（進階，預設不展開）

> 這些是 SmcConfig 裡的參數，一般不需要動。
> 只在「參數最佳化」模式下才需要調整。

| 參數 | 預設 | 說明 |
|------|------|------|
| OB 最低分 | 4.0 | Order Block 入選門檻 |
| OB 理想分 | 7.0 | 高品質 OB 門檻 |
| FVG A 級閥值 | 1.5 ATR | FVG 分級閥值 |
| Swing N (日) | 3 | 日線 Swing Point 窗口 |
| Swing N (週) | 5 | 週線 Swing Point 窗口 |
| 趨勢判斷組數 | 4 | 看最近幾組 Swing 判趨勢 |
| 進場 OB 最低分 | 3.0 | entry.py 裡 OB 進場門檻 |

---

## 七、結構反轉出場規則（一致化）

> 不使用「有賺才認反轉，虧損就忽略」的半主觀邏輯。
> 必須一致：同一個結構信號，不管損益狀態，處理方式相同。

### 三種可選模式

```
模式 A：MSS 全出（預設 — 推薦）
  ────────────────────────────────
  · CHoCH（初步反轉）→ 不出場，但標記警告
  · MSS（確認反轉）→ 全部出場，不管損益
  
  理由：MSS 要求 displacement + FVG 確認，假信號率低
  風險：偶爾會在 MSS 後反彈，但保護了大跌

模式 B：CHoCH 減半 + MSS 全出
  ────────────────────────────────
  · CHoCH → 減倉 50%
  · MSS → 剩餘全出
  
  理由：分兩步出場，降低單次判斷錯誤的成本
  風險：CHoCH 假信號率較高，可能提前減了不該減的

模式 C：關閉（純停損/停利）
  ────────────────────────────────
  · 不看結構反轉，完全靠停損和停利出場
  
  理由：回測 baseline，看「不用結構反轉」的策略表現
  風險：大跌時停損可能太慢
```

---

## 八、關於「個股參數調整」

### 結論：大部分參數不需要個股調整。先全域跑，再按群組微調。

### 8.1 不需要個股調整的（核心規則）

| 規則 | 為什麼不用調 |
|------|------------|
| SMC 結構判斷 | HH/HL = 上升，LL/LH = 下降，定義通用 |
| OB/FVG 偵測 | 位移 + 結構突破的定義不因股票而異 |
| 條件計數決策 | 框架性的，不依賴個股特性 |
| MTF 層級過濾 | 月>週>日 的階層關係普遍適用 |
| R:R ≥ 2.0 門檻 | 數學計算，不因股票不同 |
| 下降趨勢不做多 | 鐵律 |

### 8.2 已經自動適應的（ATR-based，不用手動調）

| 機制 | 怎麼自適應 |
|------|-----------|
| **ATR buffer** | 停損 = OB底部 - ATR×0.15，波動大自動放寬 |
| **Swing tolerance** | 高波動(>4%) → ×1.5，低波動(<1%) → ×0.7 |
| **OB displacement** | ATR 倍數定義 |
| **FVG grading** | A/B/C 級都是 ATR 倍數 |
| **Fib leg selection** | 最低 5 ATR range |
| **流動性 tolerance** | max(0.3%, 0.15×ATR%) |
| **進場偏離** | 0.5 ATR（改掉了固定 3%） |

### 8.3 股票群組定義

> 不按個股調，按群組調。群組依「交易特性」分，不依產業。

```
群組劃分方式：依 ATR regime + 市場 + 流動性

群組 1：US 高波動成長股
  條件：ATR/close > 3%，US 市場，日均量 > 500 萬股
  代表：NVDA, AMD, MARA, COIN
  可能調整：ATR buffer 0.15 → 0.20（停損稍寬）

群組 2：US 穩定大型股
  條件：ATR/close 1-2%，US 市場，市值 > $100B
  代表：AAPL, MSFT, GOOGL, JPM
  可能調整：不調（ATR 自適應已夠）

群組 3：US 低波動防禦股
  條件：ATR/close < 1.5%，US 市場
  代表：KO, JNJ, PG
  可能調整：Swing N 可考慮從 3 調到 4（減少噪音）

群組 4：TW 權值股
  條件：TW 市場，市值 > 1000 億
  代表：2330, 2317, 2454
  可能調整：ATR buffer 0.20（台股跳空大）

群組 5：TW 中小型股
  條件：TW 市場，市值 < 500 億
  代表：3661, 6547
  可能調整：OB 門檻 4.0 → 5.0（小型股 OB 噪音多）

群組 6：ETF
  條件：ETF 類型
  代表：00919, VOO, QQQ
  可能調整：情緒權重調低（ETF 不太受個別新聞影響）

分群演算法（自動）：
  1. 計算每支股票的 ATR_pct = ATR(14) / close
  2. 用 market 分 US / TW
  3. 用 ATR_pct 分 高(>3%) / 中(1.5-3%) / 低(<1.5%)
  4. ETF 單獨一組
  → 最多 2 × 3 + 1 = 7 個群組
```

### 8.4 正確的調參流程

```
Phase 1: 用統一參數跑全部股票回測
         ↓
Phase 2: 自動分群，看每個群組的績效
         ↓
Phase 3: 找出表現差的群組，分析原因（診斷報告）：
         - 停損觸發率高？→ ATR buffer 太小
         - 進場後常被洗出？→ 進場偏離太小
         - 勝率低但 R:R 好？→ 可能 OK（趨勢追蹤本來就低勝率）
         - 勝率低且 R:R 差？→ 可能 OB 品質不足
         ↓
Phase 4: 對該群組微調 1-2 個參數
         ↓
Phase 5: 重跑回測，用 out-of-sample 驗證
         （例如：用 2024 調參，用 2025 驗證）
```

---

## 九、回測輸出

### 9.1 績效指標

| 指標 | 現有 | 新增 | 說明 |
|------|------|------|------|
| 總報酬率 | ✅ | | |
| 年化報酬率 | ✅ | | |
| 最大回撤 | ✅ | | |
| Sharpe Ratio | ✅ | | |
| 勝率 | ✅ | | |
| 平均獲利/虧損 | ✅ | | |
| **Profit Factor** | | ✅ | 總獲利 / 總虧損，>1.5 算好 |
| **平均 R:R 實現** | | ✅ | 實際獲利 / 實際風險 |
| **按出場原因分類** | | ✅ | 停損 / 停利 / 結構反轉 各佔幾% |
| **按倉位等級分類** | | ✅ | 核心/標準/探索 各自的勝率和報酬 |
| **按 SMC 趨勢分類** | | ✅ | 上升/弱上升/盤整 各自表現 |
| **按群組分類** | | ✅ | 每個群組的獨立績效 |
| **月度報酬曲線** | | ✅ | 每月報酬率 |
| **總交易成本** | | ✅ | 手續費+稅+滑價合計 |

### 9.2 交易明細（每筆）

```
{
  ticker: "AMD",
  group: "US_高波動成長",   // 所屬群組
  
  // 進場
  signal_date: "2025-03-14",     // T 日：信號生成日
  fill_date: "2025-03-15",       // T+1 日：實際成交日
  fill_price: 170.68,            // 實際成交價
  entry_source: "OB(7.6)",       // 進場依據
  position_tier: "探索",
  conditions_met: 4,
  position_size_pct: 4.0,        // 實際倉位%
  
  // 出場
  exit_date: "2025-04-02",
  exit_price: 192.50,
  exit_reason: "停利",
  stop_source: "OB_bottom",
  target_source: "BSL",
  
  // 損益
  pnl_pct: 12.78,
  pnl_amount: 12780,
  trade_cost: 128.50,            // 交易成本
  net_pnl: 12651.50,             // 扣成本後淨損益
  holding_days: 18,
  
  // R:R
  planned_rr: 12.73,
  actual_rr: 2.88,
  
  // MAE/MFE（進場後極值偏移）
  mae_pct: -3.2,                 // 持有期間最大浮虧
  mfe_pct: 15.1,                 // 持有期間最大浮盈
  
  // 上下文
  smc_trend_at_entry: "weak_uptrend",
  smc_trend_at_exit: "uptrend",
  fill_model: "limit",           // 使用哪種成交模型
  backtest_mode: "smc_only",     // 回測模式
}
```

### 9.3 MAE/MFE 用途

```
MAE（Maximum Adverse Excursion）= 進場後最大浮虧
MFE（Maximum Favorable Excursion）= 進場後最大浮盈

用途：
  1. 調停損：如果大部分獲利交易的 MAE 都 < -2%
     → 說明停損設在 -2% 以外就夠了，不需要更寬
  
  2. 調停利：如果 MFE 常到 +15% 但最後只賺 +8%
     → 說明目標太遠或出場太早，可以調整
  
  3. 評估進場品質：MAE 越小 → 進場時機越好
     → 比較不同 entry_source（OB vs FVG vs Swing Low）的 MAE 分布

  4. 設保本停損：找到 MFE 分布的中位數
     → 用它來設「拉保本」的觸發點

範例分析：
  所有獲利交易 MAE 中位數 = -1.8%
  → ATR buffer 設在 2% 左右就不容易被洗出

  所有獲利交易 MFE 中位數 = +12%，但平均獲利只有 +7%
  → 可能 target 設太遠，改成在 MFE 70% 位置停利
```

### 9.4 策略診斷報告

回測完成後自動產生：

```
📊 策略診斷報告
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
回測模式：smc_only │ 成交：限價單 │ 成本：開

✅ 表現良好
  · 上升趨勢交易勝率 68%（高於目標 60%）
  · 核心持倉平均報酬 +15.2%
  · MAE 中位數 -1.5%（進場品質好）

⚠️ 需注意
  · 弱上升趨勢交易勝率僅 42%
    → 建議：弱上升時最多只用探索倉位
  · 停損觸發率 35%（偏高）
    → MAE 分析：80% 的停損交易 MAE < -3%
    → 建議：ATR buffer 從 0.15 調到 0.20
  · 盤整期間交易虧多贏少
    → 建議：盤整時 conditions_met 最低要求從 2 提高到 3

❌ 問題
  · 群組「US_高波動成長」停損觸發率 45%（高於全域 35%）
    → 原因：高波動 + OB 品質低（平均 4.2 分）
    → 建議：該群組 ATR buffer 調到 0.22
  · 群組「TW_權值」平均成本佔獲利 18%
    → 原因：台股交易稅 0.3% + 頻繁進出
    → 建議：台股提高 R:R 門檻到 2.5

💡 參數調整建議（自動生成）
  · 全域：ATR buffer 0.15 → 0.18
  · US_高波動成長：ATR buffer → 0.22
  · TW_權值：min R:R 2.0 → 2.5
  · 盤整市場：min_conditions 2 → 3
```

---

## 十、效能與快取

### 10.1 快取 Key 定義

```python
cache_key = (
    ticker,           # 股票代碼
    date,             # 交易日
    timeframe,        # "daily" / "weekly" / "monthly"
    strategy_hash,    # SmcConfig 的 hash（參數變了就失效）
    data_version,     # 價格資料版本（補資料後要失效）
)

# strategy_hash 來自 SmcConfig.strategy_hash()
# 任何 SMC 參數變更都會改變 hash，自動使舊快取失效
```

### 10.2 計算策略（Phase 1）

```
Phase 1：預計算 + 查表
  
  回測啟動時：
  1. 載入所有股票的完整價格 DataFrame
  2. 對每支股票，在每個交易日計算 SMC（滾動窗口）
     - 日線：每天算
     - 週線：每週五算，其餘沿用
     - 月線：每月底算，其餘沿用
  3. 結果存成 cache: dict[(ticker, date, timeframe)] → SmcResult
  4. 回測迴圈中直接查表

  快取層級：
  - L1: 記憶體 dict（單次回測內）
  - L2: 磁碟 pickle（跨回測，同參數可重用）
  - L2 key = f"{ticker}_{date}_{timeframe}_{strategy_hash}.pkl"

  失效條件：
  - SMC 參數變了 → strategy_hash 不同 → L2 miss
  - 補了新價格資料 → data_version 變 → L2 miss
  - 不同回測但參數和資料都一樣 → L2 hit（省大量時間）
```

### 10.3 預估耗時

```
首次跑（L2 miss）：
  66 股 × 500 日 × 0.05s = ~27 分鐘
  · 週線/月線不是每天算，實際約 × 0.7 = ~19 分鐘
  · Python multiprocessing 4 核 = ~5 分鐘

再次跑（同參數，L2 hit）：
  查表 only = < 30 秒
```

---

## 十一、實作計劃

### Phase 1：核心回測（先能跑、先可信）

```
檔案：backend/app/services/backtester_v2.py（新檔）

必須包含：
  ✅ T日算/T+1成交 的時點規則
  ✅ 限價單成交模型（含 gap 穿越處理）
  ✅ 同日衝突保守假設
  ✅ v2 SMC 分析（滾動窗口）
  ✅ EntryPlan 驅動進場
  ✅ 結構反轉出場（MSS 全出）
  ✅ 完整倉位計算（6 重約束）
  ✅ 成本模型（US + TW）
  ✅ MAE/MFE 追蹤
  ✅ 回測模式標示
  ✅ 基本績效指標 + 新增指標
  ✅ 交易明細含完整元數據

前端：
  ✅ BacktestForm 增加 v2 參數
  ✅ 參數依賴 UI（disable 互斥欄位）
  ✅ 結果頁標示回測模式/成交模型/成本
```

### Phase 2：診斷 + 群組

```
  ✅ 策略診斷報告
  ✅ 自動分群 + 群組績效
  ✅ MAE/MFE 分析圖表
  ✅ 按群組/趨勢/倉位等級的分類統計
  ✅ 月度報酬曲線
```

### Phase 3：效能 + 最佳化

```
  ✅ L2 磁碟快取
  ✅ 增量 SMC 計算
  ✅ 參數網格搜索
  ✅ 群組自訂參數 + out-of-sample 驗證
  ✅ 情緒數據回填
```

---

## 十二、FAQ

### Q: 為什麼預設用保守假設（同日停損優先）？
**A:** 回測的目的是「確認策略能賺錢」，不是「證明策略賺很多」。保守假設下還能賺錢的策略，實盤大概率也能賺。樂觀假設下賺錢的策略，實盤很可能翻車。

### Q: 為什麼不用每支股票一套參數？
**A:** 過度擬合。針對個股調到完美只代表完美解釋了過去。正確做法：按群組特性調，並用 out-of-sample 驗證。

### Q: 情緒數據怎麼處理？
**A:** Phase 1 用 `smc_only` 模式（不含情緒），報表上會明確標示。有歷史新聞資料後可切換 `smc_full` 模式。兩種模式的績效不可直接比較。

### Q: 回測需要跑多久？
**A:** 首次約 5-20 分鐘（視股票數量、回測期間、是否有快取）。同參數再跑 < 30 秒。

### Q: 成本模型會不會讓績效很難看？
**A:** 會，尤其台股。但這才是真實表現。不帶成本的回測就像體重計不算衣服重量——數字好看但沒用。
