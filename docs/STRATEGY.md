# Money Printer 交易策略規格書

> 版本：v5.0 (Production Ready) | 2026-04-08
> 核心：**SMC 定點位 + 情緒定時機**
> 層級：工程規格（每條規則可直接落成程式碼，無歧義）
> 審查人回饋已整合：花蓮王（SMC）、GPT（量化工程）、Gemini（系統架構）

---

## 策略哲學

**SMC 負責回答「在哪裡買賣」**（價位）
**情緒/LLM 負責回答「現在該不該動手」**（時機）

兩者缺一不可：
- 光有 SMC 點位但情緒極差 → 暫緩進場
- 光有利多新聞但 SMC 沒有好的進場結構 → 不追

**不使用任何傳統滯後性技術指標**（RSI、MACD、MA、布林通道等）作為核心決策依據。

---

## 第一層：SMC 結構分析（方向 + 點位）

### 1. 市場結構 → 決定方向

先看結構，結構錯就不做，不管消息多好。

#### 1.1 Swing Point 偵測

```
演算法：
  tolerance = max(ATR * 0.05, tick_size * 3)

  其中 tick_size：
    美股 > $1:   tick = $0.01
    美股 < $1:   tick = $0.0001
    台股:        tick = 依價格級距（例如 $100+ 的 tick = $0.5）

  volatility regime 調整：
    if ATR / close > 0.04:   # 高波動（> 4% 日均振幅）
      tolerance *= 1.5
    if ATR / close < 0.01:   # 低波動（< 1%）
      tolerance *= 0.7

  Swing High: high[i] >= max(high[i-N:i], high[i+1:i+N+1]) - tolerance
    且 high[i] 是該窗口內的最大值（多根相同取最中間那根）
  Swing Low:  low[i]  <= min(low[i-N:i], low[i+1:i+N+1]) + tolerance
    且 low[i] 是該窗口內的最小值

  Flat top/bottom 處理：
    如果連續 M 根的 high 差距 < tolerance → 視為同一個 Swing High
    取中間那根的 index，取 max(high) 作為 price

參數（按時間框架）：
  日線:  N = 3
  週線:  N = 5
  月線:  N = 3

最小間距（防止過密 noise）：
  兩個同類型 Swing Point 之間至少間隔 N 根 K 棒
  即：如果 swing_high[i] 和 swing_high[j] 的 index 差 < N → 只保留 price 更高的
  同理 swing_low 只保留 price 更低的
```

#### 1.2 趨勢判斷（硬規則，非模糊多數決）

```
輸入：最近 4 組 Swing High + 最近 4 組 Swing Low（共 8 個點）

上升趨勢，必須同時滿足：
  1. 最近 4 個 Swing High 中，至少 3 個是 HH（後一個 > 前一個）
  2. 最近 4 個 Swing Low  中，至少 3 個是 HL（後一個 > 前一個）
  3. 最近一個結構事件是 Bullish BOS
  4. 最新收盤價 > 最近的 HL（未跌破最近支撐）

下降趨勢，必須同時滿足：
  1. 最近 4 個 Swing High 中，至少 3 個是 LH
  2. 最近 4 個 Swing Low  中，至少 3 個是 LL
  3. 最近一個結構事件是 Bearish BOS
  4. 最新收盤價 < 最近的 LH

弱上升趨勢（Weak Uptrend）：
  不滿足完整上升條件，但同時滿足：
  1. HL 持續上升（至少 3/4 是 HL）
  2. HH 不足（可能只有 2/4，延遲突破型）
  3. 最新收盤未跌破最近 HL
  4. 無 Bearish CHoCH/MSS
  → 標記為「弱上升」，最多允許探索倉位（5%）

弱下降趨勢（Weak Downtrend）：對稱邏輯
  LL 持續下降但 LH 不足 → 仍視為偏空，不做多

盤整：不滿足上升/下降/弱上升/弱下降的任一條件組

不足 4 組 Swing Point → 標記為「資料不足」，不給方向判斷
```

**鐵律：下降結構 = 不買。不管基本面多好、新聞多利多。**

#### 1.3 結構事件（BOS / CHoCH / MSS）— 明確定義，無歧義

**內部標準（固定，不隨流派變動）：**

```
BOS（Break of Structure）= 順勢延續
  定義：收盤價突破同方向的前一個 Swing Point
  - 上升趨勢中，收盤 > 前 Swing High = Bullish BOS
  - 下降趨勢中，收盤 < 前 Swing Low  = Bearish BOS
  要求：收盤價確認（影線穿越不算）

CHoCH（Change of Character）= 反向突破，無 displacement
  定義：收盤價反向突破關鍵 Swing Point，但沒有強勢位移
  - 上升趨勢中，收盤 < 最近 HL = Bearish CHoCH
  - 下降趨勢中，收盤 > 最近 LH = Bullish CHoCH
  要求：收盤確認，但 break candle body ≤ 1.5 ATR
  意義：⚠️ 第一個警告信號，不保證反轉

MSS（Market Structure Shift）= CHoCH + displacement 確認
  定義：CHoCH 發生後，在確認窗口內出現 displacement + FVG
  具體條件（全部必須滿足）：
    1. CHoCH 已觸發（收盤反向突破 Swing Point）
    2. 確認窗口內，至少 1 根 K 棒的 body > 1.5 ATR
    3. 該 displacement 過程留下 FVG
  意義：🚨 結構反轉確認信號

  確認窗口（adaptive，按時間框架）：
    日線:  5 根（一週交易日）
    週線:  3 根（三週）
    月線:  3 根（三個月）
    公式:  window = max(3, min(5, round(avg_swing_length * 0.3)))
    其中 avg_swing_length = 最近 3 段 swing leg 的平均 K 棒數

層級關係（時間順序，非重要性）：
  CHoCH 先發生 → MSS 在之後確認（或不確認）→ BOS 延續新方向
  CHoCH 沒有跟上 MSS = 可能是假信號 / 洗盤
  MSS 確認後的第一個同方向突破 = 新趨勢的第一個 BOS

互斥規則：
  同一個 Swing Point 的突破，只能被標記為一種事件
  先判定是否為 BOS（順勢），不是才看 CHoCH，CHoCH 後看是否升級為 MSS
```

#### 1.4 多時間框架決策矩陣（硬規則）

```
我們系統的時間框架層級：
  HTF = 週線/月線（大方向）
  MTF = 日線（主要分析框架）
  LTF = 4H/1H（如有資料，用於精確進場；目前系統以日線為主）

決策矩陣（做多）：

  月線  │ 週線  │ 日線  │ 決策                    │ 最大倉位
  ──────┼───────┼───────┼─────────────────────────┼─────────
  上升  │ 上升  │ 上升  │ ✅ 正常做多              │ 核心 20%
  上升  │ 上升  │ 盤整  │ ✅ 等日線 BOS 確認再進    │ 標準 12%
  上升  │ 盤整  │ 上升  │ ⚠️ 降級倉位              │ 標準 12%
  上升  │ 盤整  │ 盤整  │ ⚠️ 等週線突破             │ 探索 5%
  上升  │ 下降  │ 任何  │ ❌ 禁止做多（週線反轉中）  │ 0%
  盤整  │ 上升  │ 上升  │ ⚠️ 可做但降級             │ 標準 12%
  盤整  │ 盤整  │ 上升  │ ⚠️ 最多探索倉            │ 探索 5%
  下降  │ 任何  │ 任何  │ ❌ 禁止做多               │ 0%

  簡化規則（做多）：
  - 月線下降 → 全面禁止做多
  - 週線下降 → 禁止做多（即使月線和日線都是上升）
  - 只有日線上升，HTF 不明 → 最多探索倉 5%
  - HTF 全部上升 → 才允許核心持倉

決策矩陣（做空 / 防禦 / 對沖）：

  月線  │ 週線  │ 日線  │ 決策                         │ 操作
  ──────┼───────┼───────┼──────────────────────────────┼──────────
  下降  │ 下降  │ 下降  │ ⭐ 全面防禦                    │ 清倉多頭 + 可做空
  下降  │ 下降  │ 盤整  │ ⚠️ 不開新多頭                  │ 持有現金
  下降  │ 盤整  │ 上升  │ ⚠️ 可能是熊市反彈               │ 禁止 swing long
  盤整  │ 下降  │ 下降  │ ⚠️ 減倉現有多頭                 │ 多頭倉位砍半
  上升  │ 下降  │ 下降  │ ⚠️ 週線回調中                   │ 不開新倉，觀望
  任何  │ 任何  │ CHoCH │ ⚠️ 日線出現反轉警告              │ 現有多頭至少減半

  簡化規則（做空/防禦）：
  - 月線+週線都下降 → 清倉多頭，進入防禦模式
  - 月線下降+日線反彈 → 熊市反彈，不做 swing long
  - 目前系統以做多為主，做空功能為未來擴展預留

LTF Entry Integration（進階，需 1H/4H 數據）：

  目前系統以日線 OB/FVG 做為直接進場點。
  進階版可加入 LTF 精確進場觸發：

  流程：
    1. 日線標記 Demand Zone（OB/FVG 在 Discount 區）
    2. 當日線價格進入 Demand Zone 時，切到 1H/4H
    3. 在 1H/4H 等待 MSS 或 CHoCH 確認（反轉信號）
    4. 1H/4H MSS 確認後才進場 → 更精確的 entry → 更窄 stop → 更高 R:R

  限制：
    - 需要 intraday 數據（目前系統以 EOD 為主）
    - 標記為 P2 優先級，日線版本已可用
    - 如果無 LTF 數據，fallback 到日線 OB 進場（現有邏輯）
```

---

### 2. Fibonacci → 決定區域（在哪裡找機會）

確認結構方向後，用 Fibonacci 劃分「值得進場的區域」和「不值得的區域」。

#### 2.1 Swing Leg 選擇規則

```
Fibonacci 畫在哪一段 swing leg 上，直接影響所有水位計算。

候選收集：
  1. 找所有有 displacement（body > 1.5 ATR）的主升段
  2. 每段的 Swing Low = 升段起點，Swing High = 升段終點
  3. 排除已被完全回撤的（現價 < swing_low）

候選評分（取最高分的那段）：
  leg_score = displacement_strength * 0.4    （位移力度，ATR 倍數）
            + recency * 0.4                  （時間近度，1.0 = 最近，按天數衰減）
            + range_quality * 0.2            （range / ATR，越大越好，cap 10）

  recency = max(0, 1 - days_since_leg_end / 120)

  選 leg_score 最高的那段畫 Fibonacci

驗證：
  - range = swing_high - swing_low
  - 如果 range < 5 * ATR → 太小，不畫 Fibonacci（波段太短）
  - 如果最新收盤已跌破 swing_low → 該 leg 失效，重新找
```

#### 2.2 關鍵水位

```
Swing High ──── 1.0   （起點）
                0.786  ← OTE 上緣（做多回撤的深水區）
                0.705  ← OTE 甜蜜點（最佳進場）
                0.618  ← OTE 下緣
           ──── 0.5   ← 均衡線（Equilibrium）
                0.382
                0.236
Swing Low  ──── 0.0   （終點）

計算公式（做多）：
  level = swing_low + range * fib_ratio
  例：OTE 甜蜜點 = swing_low + range * (1 - 0.705)
  注意：Fibonacci 在 SMC 中是從高往低量的回撤
```

#### 2.3 Premium / Discount 規則

| 區域 | 範圍 | 規則 |
|------|------|------|
| **Deep Discount** | < 0.236 | ✅ 極度便宜（但可能結構已壞，需確認） |
| **Discount** | 0.236 ~ 0.5 | ✅ 在這裡找做多機會 |
| **Equilibrium** | ≈ 0.5 (±2%) | ⚠️ 中性區，可以但不理想 |
| **Premium** | 0.5 ~ 0.764 | 🚫 不在這裡做多 |
| **Deep Premium** | > 0.764 | 🚫 絕對不追 |
| **OTE** | 0.618 ~ 0.786 | ⭐ 最佳進場區（在 Discount 內的黃金地帶） |

**只在 Discount 區做多，只在 Premium 區做空。**

#### 2.4 延伸目標（Fibonacci Extension）

| 水位 | 用途 |
|------|------|
| **-0.272** | 第一獲利目標（部分平倉） |
| **-0.618** | 第二獲利目標（主要獲利） |
| **-1.0** | 完整測量目標（激進） |

---

### 3. Order Block → 精確進場價位

在 Fibonacci 確定的「區域」內，找有效的 OB 作為精確進場價。

#### 3.1 有效 OB 的 5 項驗證

| # | 條件 | 必須? | 說明 | 參數 |
|---|------|:-----:|------|------|
| 1 | **Displacement** | ✅ 必須 | OB 後的推動 K 棒 body > K ATR | 日線 K=1.5, 週線 K=1.3 |
| 2 | **FVG 確認** | ✅ 必須 | 位移過程留下 FVG | 在 OB 後 5 根內 |
| 3 | **結構突破** | ✅ 必須 | 位移過程有 BOS 或 MSS | 在 OB 後 10 根內 |
| 4 | **流動性掃蕩** | 加分 | OB 前 1-3 根掃蕩了前方停損 | 影線穿越+收盤未過 |
| 5 | **HTF 共振** | 加分 | 與週線/月線 OB 重疊 | 價格範圍有交集 |

**評分：連續型 0.0 ~ 10.0（保留更多資訊，避免離散化損失）**

```
OB score 計算公式：

  base_score = 0
  if displacement:  base_score += min(3.0, displacement_strength / ATR - 0.5)  # 0~3.0 連續
  if has_fvg:       base_score += 2.0
  if has_bos:       base_score += 2.0
  if has_sweep:     base_score += min(1.5, sweep_wick_ratio * 3)               # 0~1.5 連續
  if htf_confluence: base_score += 1.5

  volume_bonus = min(1.0, (vol_ratio - 1.0) * 0.5)  # vol_ratio = candle_vol / SMA20_vol
  base_score += volume_bonus

  最低門檻：base_score < 4.0 → 不做為進場依據（等同原本的 3/5）
  理想門檻：base_score ≥ 7.0 → 高品質 OB
```

#### 3.2 OB 去重與管理規則（防止過度標記）

```
規則 1: 同一 impulsive leg 保留主 OB + 最多 1 個 nested OB
  - 主 OB = score 最高的（若 score 相同，取最近的）
  - Nested OB = 完全包含在主 OB 範圍內的更小 OB（refinement entry）
    - 只有當 nested OB 的 score ≥ 3 且 range < 主 OB range * 0.5 才保留
    - Nested OB 用途：更精確的進場點（更窄 stop → 更高 R:R）
  - 如果有其他 OB 既不是主 OB 也不是 nested → 丟棄

規則 2: 重疊合併（非包含關係的重疊）
  - 兩個 OB 的價格範圍重疊 > 50% 且非包含關係 → 合併為一個
  - 合併後 score = max(score_a, score_b)
  - 合併後 top/bottom = 包含兩者的範圍

規則 3: 回測衰減
  - 每次回測（價格觸及 OB zone 後離開）→ score -= 0.5
  - score 降到 < 2 → 自動標記為「耗盡」，不再做為進場

規則 4: 時間衰減（Freshness Decay）
  - OB 形成後的天數 d
  - 日線 OB: d > 60 天 → score -= 1
  - 週線 OB: d > 26 週 → score -= 1
  - 月線 OB: 不衰減

規則 5: 單張圖最多顯示
  - 未 mitigated 的 Bullish OB: 最多 3 個（score 最高的）
  - 未 mitigated 的 Bearish OB: 最多 3 個
```

#### 3.3 OB 失效（Mitigated）判定

```
Bullish OB 失效：
  收盤價 < OB.bottom → 完全失效，標記 mitigated = True

Bearish OB 失效：
  收盤價 > OB.top → 完全失效

注意：影線穿越不算失效（可能是 sweep）
```

#### 3.4 進場位置
- **Bullish OB**：限價單在 OB 上緣（等價格回測到 OB）
- 不追價 — 價格沒回到 OB 就不進

---

### 4. Fair Value Gap (FVG) → 替代進場點

當 OB 不在好的位置時，FVG 可以作為進場依據。

#### 4.1 有效 FVG

```
Bullish FVG: K1.High < K3.Low（三根 K 棒中間留空白）
Bearish FVG: K1.Low > K3.High

K2 displacement 門檻（分級）：
  A 級 FVG: K2 body > 1.5 ATR（強位移）
  B 級 FVG: K2 body > 1.2 ATR（中等位移）
  C 級 FVG: K2 body > 1.0 ATR（最低門檻）
  < 1.0 ATR → 不標記為 FVG

CE = (top + bottom) / 2（Consequent Encroachment，50% 中線）
```

#### 4.2 FVG 狀態追蹤（5 級，非 2 級）

```
判定順序（從上到下，第一個命中即停）：

1. Active:       價格尚未回測到 FVG 範圍內
2. CE Touched:   最低價觸及 CE 但收盤仍在 CE 之上 → 觀察中
3. Respected:    價格回到 FVG 後在 CE 之上反彈 → ✅ 有效支撐
4. Deeply Filled: 收盤穿越 CE 但未穿越 FVG.bottom → ⚠️ 力量減弱，降級
5. Fully Filled:  收盤穿越 FVG.bottom → 失效
6. Inverted:     Fully Filled 後價格反向使用 → 極性翻轉（多頭→空頭）

進場只用 Active / CE Touched / Respected 的 FVG
Deeply Filled 的 FVG 只做觀察，不做為新進場依據

FVG Freshness Decay（與 OB 對稱）：
  日線 FVG: 形成後 > 40 天 → 降級一個狀態（Active→CE Touched 等）
  週線 FVG: 形成後 > 20 週 → 降級
  月線 FVG: 不衰減
  衰減邏輯：
    fvg_age = today - fvg_date
    if fvg_age > decay_threshold:
      Active → CE Touched → Respected → Deeply Filled（不再做進場依據）
```

#### 4.3 進場位置
- **Bullish FVG**：進場在 CE 中線（非 FVG 底部，更保守）
- 停損在 FVG.bottom 外側 + ATR buffer

---

### 5. 流動性 (Liquidity) → 決定目標

流動性是 SMC 最核心的概念之一：價格會被「磁鐵般」吸引到停損密集的地方。

#### 5.1 流動性類型

| 類型 | 位置 | 構成 | 意義 |
|------|------|------|------|
| **BSL（買方流動性）** | 價格上方 | 空頭停損 + 追漲單 | 做多的目標 |
| **SSL（賣方流動性）** | 價格下方 | 多頭停損 + 追跌單 | 做空的目標 |

#### 5.2 EQH/EQL 偵測（ATR 自適應容差）

```
固定百分比容差跨股票會失真（0.3% 對 ETF 太寬，對高波動股太窄）

自適應容差公式：
  tolerance = max(0.3%, 0.15 * ATR / close * 100)

  即：取 0.3% 和 0.15 倍 ATR% 中的較大值

  - 低波動股（ATR% 小）→ 使用 0.3% 底線
  - 高波動股（ATR% 大）→ 自動放寬容差

EQH 偵測：
  遍歷所有 Swing High，兩個 SH 價差 ≤ tolerance → 歸為同一 cluster
  cluster.size ≥ 2 → 標記為 BSL
  cluster.price = 所有成員的平均價

EQL 偵測：對稱邏輯

去重：兩個 cluster 的 price 差距 ≤ tolerance → 合併

流動性強度評分（Liquidity Weight）：
  liq_score = touches * 0.4                  # 觸及次數（越多越強）
            + time_spread * 0.3              # 時間分散度（跨越越久越強）
            + dwell_ratio * 0.3              # 停留密度

  touches = cluster.size                     # 2, 3, 4...
  time_spread = (last_touch_idx - first_touch_idx) / total_bars  # 0~1
  dwell_ratio = bars_within_tolerance / (last_touch_idx - first_touch_idx)  # 價格在該區域停留的比例

  liq_score 越高 → 該流動性池被「拿走」的機率越高 → 做為目標更可靠
```

#### 5.3 Sweep vs Run

| | Sweep（掃蕩 = 假突破） | Run（延伸 = 真突破） |
|--|----------------------|-------------------|
| 定義 | High > liq_price AND Close < liq_price | Close > liq_price AND body > 0.5 ATR |
| 意義 | 機構收割停損後反轉 | 趨勢延續 |
| 操作 | ✅ 掃蕩後反向進場 | 跟隨方向 |

#### 5.4 做多時的目標設定（優先順序 + 選擇邏輯）

```
目標候選收集（所有 > close 的）：
  1. BSL（EQH cluster）
  2. Bearish OB 底部（未 mitigated，且 freshness 較高的優先）
  3. Swing High
  4. Fibonacci Extension -0.272 / -0.618

選擇邏輯：
  - 如果 BSL 和 Bearish OB 在相近位置（差距 < 2%）→ 取兩者的 min 做為更保守目標
  - 如果只有 Swing High → 用它
  - 如果所有候選都 < close * 1.03（獲利空間 < 3%）→ 不夠，不給建議
  - 如果完全找不到 → 不給建議（不硬塞百分比）
```

---

### 6. 成交量 → 驗證與確認

成交量不做為方向判斷，做為**驗證工具**：

| 場景 | 驗證規則 | 不通過的後果 |
|------|---------|------------|
| **OB Displacement** | vol[disp_candle] > SMA(vol, 20) * 1.5 | OB score -= 1 |
| **BOS/MSS 確認** | vol[break_candle] > SMA(vol, 20) * 1.2 | 標記「無量突破」，信任度降級 |
| **掃蕩確認** | vol[sweep_candle] > SMA(vol, 20) * 1.3 | 可能不是真掃蕩 |
| **Volume Profile** | POC / VA High / VA Low | 輔助標記，不做主要決策 |

---

### 7. 停損 → 結構性停損（不用固定百分比）

```
停損計算：

  依據 Order Block 進場:
    stop = OB.low - ATR * 0.15    （多頭）
    stop = OB.high + ATR * 0.15   （空頭）

  依據 FVG 進場:
    stop = FVG.bottom - ATR * 0.15 （多頭）

  依據 OTE Zone 進場:
    stop = fib_0.786_level - ATR * 0.15

  ATR buffer = 10-20%（取 15% 作為預設值）
```

**絕對不加寬停損** — 打到就是打到，前提失效就是失效。

---

### 8. R:R（風報比）門檻

| R:R | 決策 |
|-----|------|
| ≥ 3.0 | ⭐ 理想交易 |
| ≥ 2.0 | ✅ 合格交易 |
| 1.5 ~ 2.0 | ⚠️ 只有在 HTF 全部上升 + OB ≥ 4 分才考慮 |
| < 1.5 | ❌ 不交易，不管其他條件多好 |

```
R:R = (target - entry) / (entry - stop)

注意：R:R > 8 的 setup 需要人工確認
  - 通常代表 stop 太近或 target 太遠
  - 系統標記為「需確認」而非直接執行
  - 常見 R:R 分佈：2.0 ~ 5.0（健康範圍）
```

---

## 第二層：情緒分析（紅綠燈 + 反向指標）

SMC 給出了「$142 買入、$135 停損、$167 目標、R:R 3.8」，但**現在該不該執行？**
這是情緒層回答的問題。

### 核心原則：情緒是反向指標

SMC 的本質是**反散戶**。機構需要散戶的訂單做為對手盤：
- 散戶恐慌拋售（極度悲觀）→ 機構趁機收貨 → **反而是好的買點**
- 散戶瘋狂追漲（極度樂觀）→ 機構趁機派發 → **反而是該賣的時候**

因此，情緒不是「正面就買、負面就不買」這麼簡單。

### 1. 情緒分數的正確解讀

#### 做多時（價格在 Demand OB / Discount 區）

| 情緒狀態 | 分數 | SMC 解讀 | 操作 |
|---------|------|---------|------|
| 極度悲觀 → 轉向中性 | < 30 → 40-50 | **利空出盡**，散戶已拋售完畢，機構在收貨 | ⭐ 最佳買點，倉位升級 |
| 中性 | 40-60 | 正常市場環境 | ✅ 正常執行 SMC 信號 |
| 正面 | 60-75 | 有基本面支撐 | ✅ 正常執行 |
| 極度樂觀 | > 75 | ⚠️ 散戶正在瘋狂追漲，可能接近頂部 | ⚠️ 降級倉位，不追高 |

#### 減倉 / 出場時（價格在 Supply OB / Premium 區）

| 情緒狀態 | 分數 | SMC 解讀 | 操作 |
|---------|------|---------|------|
| 極度樂觀 | > 75 | 散戶在接盤，機構準備派發 | ⭐ 最佳賣點 |
| 正面 | 60-75 | 還有上行動力 | ⚠️ 部分減倉，觀察 |
| 極度悲觀 | < 30 | 恐慌殺跌中，不要跟著殺 | ⚠️ 等情緒穩定再決定 |

#### 「極度悲觀 = 好買點」的硬限制（防接飛刀）

```
❗ 極度悲觀只有在以下條件全部滿足時，才能視為反向利多：

  1. HTF 結構未破壞（週線/月線仍為上升或盤整，不是下降）
  2. 價格處於 Discount 區或 Demand Zone（OB/FVG 附近）
  3. 悲觀有開始回升的跡象（3 日 sentiment slope > 0）

  如果不滿足 → 極度悲觀 = 結構性風險，禁止抄底

  特別是：
  - 極度悲觀 + HTF 結構下降 = ❌ 接飛刀，禁止
  - 極度悲觀 > 5 天 + 結構同步走壞 = ❌ 結構性問題，觸發 LLM 深度分析
```

#### 情緒趨勢量化（轉折 > 絕對值）

```
計��方式（EMA slope，抗噪音）：
  sent_ema3 = EMA(sentiment, span=3)   （短期）
  sent_ema7 = EMA(sentiment, span=7)   （中期）
  slope = sent_ema3 - sent_ema7         （短期 vs 中期的差值）

  slope > +8   → 「快速回升」→ 利多信號
  slope ∈ [-5, +8] → 「穩定」→ 中性
  slope < -8   → 「快速惡化」→ 利空信號

  為什麼用 EMA 而不是線性差值：
  - 線性差值 (today - 3d_ago) / 3 對單日 spike 極度敏感
  - EMA 自動平滑噪音，同時保留趨勢方向
  - EMA3 vs EMA7 的交叉比絕對值更穩定

  連續 sent_ema3 > 75 超過 3 天 → 「過熱」→ 警戒
  連續 sent_ema3 < 30 超過 5 天 → 「持續悲觀」→ 觸發 LLM 分析
```

### 2. 情緒做為 CHoCH/MSS 的驗證器

```
結構事件可靠度評級：

  BOS + 有新聞     → 可靠度不變（BOS 本身就是延續，不太需要新聞）
  BOS + 無新聞     → 可靠度不變

  CHoCH + 重大新聞 → 可靠度 ↑（基本面驅動反轉，更可信）
  CHoCH + 無新聞   → 可靠度 ↓（可能是洗盤，倉位降一級）

  MSS + 重大新聞   → 可靠度 ↑↑（結構 + 基本面共振）
  MSS + 無新聞     → 可靠度正常（MSS 本身已有 displacement 確認，但額外小心）

  「重大新聞」定義：sentiment 單日變動 > 15 分 的事件
```

### 3. LLM 綜合判斷

LLM 在以下場景介入分析（讀取系統數據 + 外部情報）：

| 分析維度 | 具體內容 |
|---------|---------|
| **大盤環境** | SPY/QQQ 的 SMC 結構（大盤下降趨勢 → 全部降級） |
| **國際情勢** | 地緣政治、利率決議、FOMC、關稅政策 |
| **產業連動** | 同產業其他股票的走勢是否支持 |
| **財報/事件** | 即將到來的財報日、除息日、重大發布會 |
| **催化劑時效** | 利多是一次性的還是結構性的 |
| **情緒背離偵測** | 股價創新高但情緒走低 = 頂部警告；股價創新低但情緒回升 = 底部信號 |

**LLM 啟動條件（不是每次都跑，有條件觸發）：**
```
自動觸發：
  - 情緒持續 < 30 超過 5 天 + 結構出現 CHoCH
  - 情緒與價格背離（新高 + 情緒下滑，或新低 + 情緒回升）
  - 重大事件日（FOMC、CPI、財報日前 2 天）

不觸發（節省成本）：
  - 結構穩定 + 情緒中性 + 無事件 → 純跑 SMC 引擎
```

### 4. 情緒層的邊界（不做的事）
- ❌ 不改變 SMC 計算出的進場/停損/目標價位
- ❌ 不推翻結構方向判斷（下降結構 + 利多新聞 ≠ 可以做多）
- ❌ 不使用 RSI/MACD/MA 等傳統技術指標
- ❌ 情緒分數不直接參與進場價計算

---

## 第三層：綜合決策矩陣

### 決策流程圖

```
Step 1: MTF 結構方向
  ├── 月線或週線下降 → ❌ 不做多（結束，不管新聞多好）
  ├── 查 MTF 決策矩陣 → 確定最大倉位上限
  └── 日線上升 + HTF 支持 → ✅ 繼續

Step 2: 價格區域（Fibonacci）
  ├── Premium 區（> 0.5）→ ❌ 不追高，等回調（結束）
  ├── Equilibrium 附近    → ⚠️ 可以，但不理想
  └── Discount 區（< 0.5）→ ✅ 好的區域
      └── OTE 區 (0.618-0.786) → ⭐ 最佳區域

Step 3: 找進場點
  ├── 有 OB（≥3分）在好區域 → ✅ 用 OB 進場
  ├── 有 FVG（Active/CE Touched/Respected）在好區域 → ✅ 用 FVG 進場
  └── 都沒有 → ❌ 沒有好的進場結構（結束）

Step 4: 計算 R:R
  ├── R:R ≥ 2.0 → ✅ 合格
  ├── R:R 1.5-2.0 + HTF 全上升 + OB≥4 → ⚠️ 勉強可以
  └── R:R < 1.5 → ❌ 不值得（結束）

Step 5: 情緒紅綠燈（反向指標邏輯）
  ├── 做多場景：
  │   ├── 悲觀→中性（slope > 0）+ HTF 未破 → ⭐ 最佳，升級倉位
  │   ├── 中性 (40-60) → ✅ 正常執行
  │   ├── 正面 (60-75) → ✅ 有支撐
  │   ├── 極度樂觀 (>75) → ⚠️ 過熱，降級倉位
  │   └── 極度悲觀 + HTF 下降 → ❌ 接飛刀，禁止
  │
  └── 減倉場景：
      ├── 極度樂觀 + Premium → ⭐ 最佳減倉時機
      └── 極度悲觀 + 恐慌殺跌 → ⚠️ 不跟著殺，等穩定

Step 6: CHoCH/MSS 情緒驗證
  ├── 結構轉變 + 重大新聞（sentiment Δ > 15）→ ⭐ 高可靠度
  └── 結構轉變 + 無新聞 → ⚠️ 降級信任，倉位 -1 級

Step 7: 大盤 / LLM 確認
  ├── 大盤上升 + 無重大風險 → ✅ 執行
  ├── 大盤盤整 → ⚠️ 倉位降級
  └── 大盤下降 + 重大風險 → 🚫 暫緩
```

### 倉位等級

| 等級 | 佔總資金 | 條件 |
|------|---------|------|
| **核心持倉** | 15-20% | HTF 全上升 + OTE 區 OB(≥4分) + R:R≥3.0 + 情緒利空出盡或中性 + 大盤上升 |
| **標準倉位** | 8-12% | HTF 多數上升 + Discount 區 OB(≥3分) + R:R≥2.0 + 情緒中性以上 |
| **探索倉位** | 3-5% | 日線上升但 HTF 盤整 或 Equilibrium 區 或 情緒過熱需降級 |
| **不建倉** | 0% | HTF 下降 / Premium 區 / R:R<1.5 / 結構性利空 + HTF 破壞 |

---

## 具體操作範例

### 範例：假設分析 MRVL

> ⚠️ 以下數字為示意，非實際推薦。真實 R:R 通常在 2.0-5.0 之間。

**Step 1 — MTF 結構：**
```
月線：上升（HH+HL 連續 3 組 ✅）
週線：上升（最近 Bullish BOS ✅）
日線：上升（4 組中 3 組 HH+HL ✅，最新收盤 > 最近 HL ✅）
→ MTF 矩陣：月↑週↑日↑ → 核心倉位上限 20%
```

**Step 2 — Fibonacci 區域：**
```
主升段：$95 (Swing Low) → $125 (Swing High)
Range = $30，> 5 * ATR($3.2) = $16 ✅ 有效

Equilibrium (0.5) = $110.00
OTE 下緣 (0.618) = $106.46
OTE 甜蜜點 (0.705) = $103.85
OTE 上緣 (0.786) = $101.42

現價：$108.65
位置：Discount 區（< Equilibrium $110）
→ ✅ 好的區域
```

**Step 3 — 進場點：**
```
Bullish OB @ $103.50-$105.20（在 OTE 區域內 ⭐）
  - Displacement: 2.1x ATR ✅ (1分)
  - FVG 確認 ✅ (1分)
  - BOS 確認 ✅ (1分)
  - 流動性掃蕩：掃了 $102.80 的 SSL ✅ (1分)
  - Volume: displacement candle vol > SMA20 * 1.5 ✅
  - 回測次數：1 次（score 未衰減）
  - 評分：4/5 ⭐

→ 進場價：$105.20（OB 上緣）
→ 停損：$103.10（OB Low $103.50 - ATR*0.15 ≈ $0.48）
```

**Step 4 — 目標 + R:R：**
```
目標候選：
  1. BSL @ $128.50（EQH，3 次觸及，容差 = max(0.3%, 0.15*3.2/125*100) = 0.38%）
  2. Bearish OB @ $132.00
  3. Fib Extension -0.272 = $133.15

選擇：BSL $128.50（最近且最可靠）
備用：Bearish OB $132.00

R:R = ($128.50 - $105.20) / ($105.20 - $103.10) = 11.1

⚠️ R:R > 8 → 系統標記「需確認」
原因：stop 很近（$2.10），target 很遠（$23.30）
人工判斷：stop 在 OB 底部是結構性的，合理。Target 是 EQH，也合理。→ 確認通過
（注：大部分 setup 的 R:R 在 2.0-5.0，此例因 OB 窄 + target 遠而偏高）
```

**Step 5 — 情緒紅綠燈：**
```
新聞情緒：62（AI 需求正面，但非極度樂觀）
sentiment_slope = (62 - 45) / 3 = +5.7/天 → 「快速回升」
→ ✅ 情緒正在回升，利空消化中，有利進場
→ 不是過熱（< 75），不需要降級
```

**Step 6 — CHoCH/MSS 驗證：**
```
最近有 Bullish BOS（非 CHoCH，不需要特別驗證）
BOS 伴隨正面新聞 → 正常可靠度
→ ✅ 通過
```

**Step 7 — 大盤 + LLM：**
```
SPY：上升結構，BOS 確認
無重大風險事件（FOMC 已過，下次財報 5 月）
LLM 未觸發（結構穩定+情緒中性+無事件）
→ ✅ 通過
```

**最終決策：**
```
📊 MRVL 交易計畫
├── 方向：做多
├── 倉位：核心持倉（15%）
│   理由：MTF全↑ + OTE區OB(4分) + R:R確認 + 情緒回升
├── 進場：$105.20（等回測 OB，不追價）
├── 停損：$103.10（OB 底部 - ATR buffer，結構性停損）
├── 目標 1：$128.50（BSL / EQH）→ 部分獲利 + 停損移到保本
├── 目標 2：$132.00（Bearish OB）
├── R:R：11.1（已人工確認）
└── 有效期：OB 未被 mitigated 且 score ≥ 3 期間

⚡ 現價 $108.65 不回到 $105.20？
→ 不追。等新的進場結構形成。

⚡ 情緒飆到 85+？
→ 降級倉位到標準（8-12%），散戶追漲 = 機構可能在派發

⚡ 暴漲 20% 到 $130？
→ 接近 BSL $128.50，SMC 重新計算全部水位
→ 如果此時情緒極度樂觀 → 考慮減倉
```

---

## 持倉管理（SMC 風格）

### 日常監控
SMC 結構是**動態的** — 每天收盤後重新計算：
- 新的 Swing Point 是否形成？
- 結構事件（BOS/CHoCH/MSS）是否發生？
- 進場後的 OB/FVG 是否被 mitigated？
- 流動性目標是否被 swept？

### 加倉條件
```
必須同時滿足：
1. 持倉已盈利（現價 > 進場價）
2. 出現新的 Bullish BOS（結構延續確認）
3. 價格回調到新的 OB/FVG（不追漲）
4. 新的進場點 R:R ≥ 2.0
5. 加倉後總倉位不超過該股上限
```

### 減倉 / 出場條件
```
部分減倉（賣一半）：
- 到達第一獲利目標（BSL 或 Fib -0.272）
- 移動停損到保本價

全部出場：
- ❌ 收盤跌破停損 → 立刻出場，不猶豫
- ❌ CHoCH 出現（結構反轉警告）→ 至少減半
- ❌ MSS 確認（結構轉換）→ 全部出場
- ✅ 到達第二獲利目標 → 獲利了結
```

### 風控規則
| 規則 | 限制 |
|------|------|
| 單筆風險 | 帳戶 1-2%（進場到停損的金額） |
| 單股上限 | 總資金 20% |
| 同時持倉 | 最多 8-10 支 |
| 同產業 | 不超過 40% |
| 總持倉 | 不超過總資金 80%（留 20% 現金） |

---

## Backtest & 上線前驗證指標

### 必要指標（上 production 前必須跑）

```
1. Win Rate（勝率）
   定義：達到目標 1 或 2 的交易比例
   計算：wins / total_trades
   健康範圍：40-55%（R:R ≥ 2.0 時，40% 勝率就能盈利）

2. Expectancy（期望值）
   定義：每筆交易的平均預期盈虧
   計算：(win_rate * avg_win) - (loss_rate * avg_loss)
   要求：> 0（正期望值才能上線）

3. Profit Factor
   定義：總盈利 / 總虧損
   計算：sum(wins) / abs(sum(losses))
   要求：> 1.5

4. Max Drawdown（最大回撤）
   定義：從峰值到谷底的最大虧損比例
   要求：< 15%（超過就需要調整倉位管理）

5. Sharpe Ratio
   定義：風險調整後報酬
   計算：(avg_return - risk_free) / std(returns)
   要求：> 1.0

6. R:R Distribution
   統計所有交易的實際 R:R 分佈
   預期：中位數 2.0-3.0，不應有大量 < 1.5 的交易

7. MAE / MFE（Maximum Adverse/Favorable Excursion）
   MAE：進場後的最大不利偏離（驗證停損是否合理）
   MFE：進場後的最大有利偏離（驗證目標是否合理）
```

### Backtest 流程

```
Step 1: 歷史數據準備
  - 至少 2 年日線數據
  - 包含牛市 + 熊市 + 盤整行情

Step 2: 逐日模擬
  - 每天收盤後跑 SMC 引擎
  - 記錄所有 entry signal
  - 模擬進場/停損/目標觸發

Step 3: 統計上述 7 個指標

Step 4: Visual Debug
  - 把每筆交易的 OB/FVG/Sweep/Fib 標在 K 線圖上
  - 人工檢視虧損交易：是 SMC 判錯，還是被噪音洗出？
  - 用於調整參數（ATR 倍數、decay 速度等）

Step 5: Walk-forward Validation
  - 不要用全部數據調參
  - in-sample 70% + out-of-sample 30%
  - 確保參數不是 over-fit
```

---

## Execution Layer（執行層）

### 1. Slippage Model（滑價模型）

```
信號層計算的 entry/stop/target 是理論價位，實際執行會有偏差。

滑價估算：
  limit_order_slippage = 0      （限價單，不追價 → 無滑價，但可能不成交）
  stop_loss_slippage = ATR * 0.05  （停損市價單，預估滑價）
  market_order_slippage = ATR * 0.03  （主動市價進場，預估滑價）

實際 R:R 修正：
  real_entry = entry + slippage_entry
  real_stop  = stop - slippage_stop    （停損被滑更遠）
  real_rr = (target - real_entry) / (real_entry - real_stop)

  如果 real_rr < 1.8（滑價後 R:R 不足）→ 降級或放棄

建議執行方式：
  進場：限價單掛在 OB 上緣，耐心等成交（不追）
  停損：stop-limit order（stop 在停損價，limit 放寬 ATR*0.1）
  獲利：到達目標 1 後部分限價平倉，剩餘用 trailing stop
```

### 2. Execution Filters（執行過濾器）

```
信號正確但執行環境差 → 暫緩或放棄

Filter 1: Gap Open（跳空開盤）
  if abs(open - prev_close) > ATR * 1.0:
    → 暫緩進場，等價格穩定 30 分鐘（或等日線收盤確認）
    → 如果 gap 直接跳過 OB → 該 OB 視為 mitigated

Filter 2: News Spike（新聞造成的瞬間劇烈波動）
  if intraday_range > ATR * 3.0 within 1 hour:
    → 暫緩，等波動收斂
    → 避免在 spike 中被停損掃出

Filter 3: Low Liquidity（低流動性標的）
  if avg_daily_volume < $5M:
    → 最多探索倉（5%），滑價風險高
  if avg_daily_volume < $1M:
    → 不交易

Filter 4: 財報 / 重大事件日
  財報公布前 2 天 ~ 後 1 天：
    → 不開新倉（gap 風險太大）
    → 持有的倉位可保持，但不加倉
```

### 3. Order Management

```
掛單有效期：
  限價單掛出後，如果 5 個交易日未成交 → 自動取消
  每天收盤後重新計算 SMC → 如果 OB 被 mitigated 或 score 衰減 → 取消掛單

部分成交處理：
  如果限價單只成交了一部分 → 依成交量計算實際倉位
  不追加市價單補足

多筆信號衝突：
  同時有多支股票觸發信號 → 按 entry_quality 排序
  資金不足時只做最高品質的 setup
```

---

## Market Regime Detection（市場狀態分類）

```
一套規則不適合所有市場狀態。不同 regime 下調整參數。

Regime 分類（基於日線 ATR 和結構）：

  Trending（趨勢市）：
    條件：結構明確（上升或下降）+ BOS 頻率 ≥ 1 次/月
    調整：正常執行所有規則
    特徵：OB/FVG 進場效果最好

  Ranging（盤整市）：
    條件：結構為「盤整」+ 無 BOS 超過 20 天
    調整：
      - 最大倉位降級到探索（5%）
      - OB 門檻提高到 score ≥ 6.0
      - 只做 range 的上下邊界反轉（不追突破）
    特徵：假突破頻繁，OB 成功率降低

  High Volatility（高波動市）：
    條件：ATR / close > 0.04（日均振幅 > 4%）
    調整：
      - stop 加寬 ATR buffer 到 25%（原 15%）
      - 倉位自動縮小：position_size *= (0.02 / daily_vol)
      - R:R 門檻提高到 2.5（補償更寬的 stop）
    特徵：訊號多但噪音也多

  Low Volatility（低波動市）：
    條件：ATR / close < 0.01（日均振幅 < 1%）
    調整：
      - displacement 門檻降為 1.2 ATR（原 1.5，因為 ATR 本身就小）
      - FVG displacement 降為 0.8 ATR
      - 目標可能較近，接受 R:R 1.8
    特徵：訊號少，但精準度高

Regime 切換頻率：
  每日收盤後重新判定
  如果 regime 從 Trending → Ranging：現有持倉不動，但不開新倉
  如果 regime 從任何 → High Volatility：倉位自動 resize
```

---

## Portfolio Level Controls（投資組合層控制）

### 1. Correlation Control（相關性控制）

```
同產業 ≤ 40% 只是第一層。第二層用相關性矩陣。

相關性計算：
  corr_matrix = rolling_correlation(returns, window=60)  # 60 日滾動相關係數

相關性規則：
  if corr(stock_A, stock_B) > 0.75:
    視為「同一風險源」
    兩者合計倉位 ≤ 單股上限（20%）

  常見高相關群組（需定期更新）：
  - NVDA / AMD / TSM / MRVL（半導體）
  - AAPL / MSFT / GOOGL（大型科技，相關性中等）
  - SPY / QQQ（大盤 ETF）

  如果投資組合中有 3 支以上 corr > 0.7 的股票：
    → 觸發警告：「集中度風險」
    → 建議減倉到最多 2 支同群組
```

### 2. Portfolio Heat（整體風險溫度）

```
portfolio_heat = sum(每支持倉的 risk%)

  每支 risk% = position_size * (entry - stop) / entry

  portfolio_heat > 5% → ⚠️ 風險偏高，不開新倉
  portfolio_heat > 8% → 🚨 必須減倉

  目標：portfolio_heat 保持在 3-5%
```

### 3. Sector Exposure Dashboard

```
按產業分類追蹤曝險：
  半導體: XX%
  軟體:   XX%
  金融:   XX%
  其他:   XX%
  現金:   XX%

任何產業 > 40% → 警告
現金 < 20% → 警告
```

---

## 未來路線圖（Roadmap）

```
已完成：
  ✅ SMC 策略規格（v5.0）
  ✅ 情緒反向指標整合
  ✅ MTF 決策矩陣（做多+做空）
  ✅ Execution Layer 規格
  ✅ Market Regime Detection
  ✅ Portfolio Correlation Control
  ✅ Backtest 指標定義

下一步（按優先級）：

  P0 — 核心 Engine（必須）
  ├── structure.py  — Swing/Trend/BOS/CHoCH/MSS
  ├── ob.py         — Order Block（連續評分+去重+decay）
  ├── fvg.py        — Fair Value Gap（6級狀態+decay）
  ├── liquidity.py  — EQH/EQL/Sweep（自適應容差+liq_score）
  ├── fibonacci.py  — Premium/Discount/OTE（leg scoring）
  └── entry.py      — 進場建議（整合所有模組）

  P1 — Backtest Engine
  ├── 逐日模擬器
  ├── 7 項指標計算
  ├── Walk-forward validation
  └── 參數敏感度分析

  P2 — Visual Debug
  ├── K 線圖上標記 OB/FVG/Sweep/Fib
  ├── 交易覆盤視覺化
  └── regime 狀態顯示

  P3 — Advanced
  ├── LTF Entry Integration（1H MSS trigger）
  ├── ML ranking / adaptive parameter tuning
  ├── Execution Layer 實作（order management）
  └── Portfolio correlation dashboard
```

---

## 審查回饋整合紀錄

### Round 1（GPT 初審 → v4.0）

| # | 問題 | 修正 |
|---|------|------|
| 1 | Swing 60% 多數決不夠機器可執行 | 改為硬規則：4 組至少 3 組一致 + 最近事件方向 + 收盤未破 HL |
| 2 | MSS/CHoCH/BOS 層級混亂 | 固定內部標準：CHoCH 先 → MSS 確認 → BOS 延續 |
| 3 | OB 過度標記 | 新增去重規則：重疊合併、回測衰減、時間衰減、最多顯示 3 個 |
| 4 | FVG violated/inverted 太粗 | 從 4 級改為 6 級：Active / CE Touched / Respected / Deeply Filled / Fully Filled / Inverted |
| 5 | EQH/EQL 0.3% 跨股票失真 | 改為 ATR 自適應：max(0.3%, 0.15 * ATR%) |
| 6 | MTF 有概念無規則 | 新增完整決策矩陣（月×週×日 → 操作+最大倉位） |
| 7 | 極度悲觀=好買點的過度自信 | 加硬限制：HTF 未破+Discount 區+slope>0 才成立，否則禁止抄底 |
| 8 | R:R 11.1 範例過度理想化 | 加註「R:R>8 需人工確認」、標註常見分佈 2.0-5.0、範例加警示語 |

### Round 2（GPT 複審 → v4.1）

| # | 問題 | 修正 |
|---|------|------|
| 1 | Swing Point equal high / flat top 被排除 | 加 ATR*0.05 容差 + flat top 合併取中間根 + 最小間距 N 根 |
| 2 | Trend 判斷過 rigid，miss early trend | 新增「弱上升趨勢」：HL 持續上升但 HH 不足 → 允許探索倉 |
| 3 | MSS「3 根內」跨市場不適用 | 改為 adaptive window：max(3, min(5, avg_swing_length * 0.3))，按時間框架預設 |
| 4 | OB「同�� leg 只留 1 個」過度簡化 | 改為：主 OB + 最多 1 個 nested OB（refinement entry，更窄 stop → 更高 R:R） |
| 5 | Fibonacci leg 選擇有主觀性 | 改為加權評分：leg_score = displacement*0.4 + recency*0.4 + range_quality*0.2 |
| 6 | 只有做多矩陣，缺做空/防禦 | 新增做空/��禦決策矩陣（月↓週↓日↓ → 清倉多頭；熊市反彈 → 禁止 swing long） |
| 7 | 情緒 slope 線性差值對噪音敏感 | 改為 EMA slope：sent_ema3 vs sent_ema7 差值，自動平滑噪音 |

### Round 3（GPT 三審 → v4.2 Final）

| # | 問題 | 修正 |
|---|------|------|
| 1 | Swing tolerance 0.05 ATR 仍是 static | 改為 `max(ATR*0.05, tick_size*3)` + volatility regime 動態乘數（高波動 *1.5，低波動 *0.7） |
| 2 | OB scoring 離散 0-5 損失資訊 | 改為連續型 0.0-10.0，displacement/volume/sweep 都是 float 計算，門檻改為 4.0 |
| 3 | Liquidity cluster 只看 size≥2 | 新增 liq_score = touches*0.4 + time_spread*0.3 + dwell_ratio*0.3 |
| 4 | FVG 沒有 freshness decay | 新增：日線 >40 天降級一個狀態，週線 >20 週降級，與 OB 對稱 |
| 5 | MTF 缺 LTF entry integration | 新增 LTF Entry 概念：日線 OB → 1H MSS 觸發（P2 優先級，需 intraday 數據） |
| 6 | 缺 backtest / expectancy 指標 | 新增完整章節：Win Rate、Expectancy、Profit Factor、Max DD、Sharpe、MAE/MFE + backtest 流程 |

### Round 4（GPT 四審 → v5.0 Production Ready）

| # | 問題 | 修正 |
|---|------|------|
| 1 | 缺 Execution Layer（滑價/延遲/掛單管理） | 新增完整章節：Slippage Model + Execution Filters（gap/spike/低流動性/財報日）+ Order Management |
| 2 | 沒有 Market Regime Detection | 新增 4 種 regime：Trending / Ranging / High Vol / Low Vol，每種有具體參數調整規則 |
| 3 | Portfolio 只有產業限制，缺 correlation | 新增 rolling correlation matrix + corr > 0.75 視為同一風險源 + portfolio heat 計算 |
| 4 | 缺 execution filtering | 整合進 Execution Filters：gap open / news spike / illiquid / 財報日 → 暫緩或放棄 |
| 5 | 沒有 ML / adaptive tuning 路線 | 加入 Roadmap P3：ML ranking + parameter optimization（feature engineering 已就緒） |

### 審查總評

| 審查輪次 | 評分 | 主要提升 |
|---------|------|---------|
| Round 1 | 85/100 | 語義規則 → 演算法規則 |
| Round 2 | 92/100 | 邊界條件強化 |
| Round 3 | 95/100 | 連續型計算 + backtest |
| Round 4 | **97/100** | Execution + Regime + Portfolio |

**最終評語：**

> v5.0 已完整落實 SMC 核心策略（市場結構、BOS/CHoCH/MSS、Order Block、FVG、流動性、多時間框架與結構性停損），並將所有關鍵模組演算法化（含 swing 偵測、OB 連續評分、流動性權重、FVG 衰減與 LTF entry integration），成交量正確用於驗證層，補齊 backtest 指標、execution layer、market regime detection 與 portfolio correlation control；整體已達可回測、可優化、可部署的 production-ready 交易系統標準。
