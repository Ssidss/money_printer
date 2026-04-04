# Money Printer — 策略指令書（STRATEGY.md）

這份文件是給 AI（Claude）看的，用來理解目前的買賣決策模型，並提出優化建議。
每次修改策略前請先讀這份文件，再對照 `backend/app/` 的程式碼做調整。

---

## 一、整體架構

```
股價資料 (yfinance)  →  技術分析 (ta library)  →  技術評分 (0~100)
新聞資料 (RSS feed)  →  情緒分析 (關鍵字加權)  →  情緒評分 (0~100)
                                                           ↓
                                          綜合評分 = 技術×0.6 + 情緒×0.4
                                                           ↓
                                              每日 Top 3 推薦 + 買賣決策
```

---

## 二、技術評分模型（`backend/app/services/technical.py`）

### 指標權重
| 指標 | 權重 | 參數 |
|------|------|------|
| RSI  | 25%  | period=14, 超賣<35, 超買>65 |
| MACD | 30%  | fast=12, slow=26, signal=9 |
| 均線 (MA) | 25% | MA5, MA20, MA60 |
| 布林帶 (BB) | 10% | period=20, std=2 |
| 成交量 | 10% | MA20 |

### 各指標評分邏輯

**RSI 評分**
```
RSI ≤ 30 → 100 分（嚴重超賣，強買訊號）
RSI 30~40 → 80~100 分
RSI 40~50 → 50~80 分
RSI 50~60 → 50 分（中性）
RSI 60~70 → 30~50 分
RSI > 70  → 0~30 分（超買，高風險）
```

**MACD 評分**
```
金叉（MACD > Signal）+ MACD < 0（底部翻轉）+ 柱狀增加 → 95 分（最強買訊號）
金叉 + MACD < 0 + 柱狀縮小                            → 80 分
金叉 + MACD > 0 + 柱狀增加                            → 75 分
金叉 + MACD > 0 + 柱狀縮小                            → 60 分
死叉 + MACD > 0                                       → 35 分（弱空）
死叉 + MACD < 0                                       → 10 分（強空）
```

**均線排列評分**
```
收盤 > MA5 > MA20 > MA60 → 90 分（多頭排列，最強）
收盤 > MA20 > MA60       → 75 分
收盤 > MA60              → 60 分
收盤 < MA60              → 40 分
收盤 < MA20 < MA60       → 25 分
收盤 < MA5 < MA20 < MA60 → 10 分（空頭排列，最弱）
```

**布林帶評分**
```
位置（Bollinger Position）= (收盤 - 下軌) / (上軌 - 下軌)
位置 ≤ 10%  → 90 分（接近下軌，反彈機會）
10%~25%     → 75 分
25%~50%     → 50 分（中間）
50%~75%     → 40 分
75%~90%     → 20 分
> 90%       → 10 分（接近上軌，過熱）
```

**成交量評分**
```
成交量 ≥ 均量 2x → 90 分（爆量，訊號強度高）
1.5x~2x         → 75 分
1.0x~1.5x       → 60 分
0.7x~1.0x       → 45 分
< 0.7x          → 30 分（量縮，訊號弱）
```

---

## 三、情緒評分模型（`backend/app/services/sentiment.py`）

- 關鍵字加權 net = Σ正面權重 − Σ負面權重
- 最終分數 = 50 + net × 10（限制在 0~100）
- 50 = 中性，>65 = 正面，<35 = 負面

### 現有關鍵字列表
**英文正面（weight 1~3）**：beat, record, surge, breakthrough, upgrade, growth, profit, bullish, rally...
**英文負面（weight 1~3）**：miss, crash, fraud, investigation, downgrade, loss, decline, bearish, layoff...
**中文正面**：大漲, 創新高, 超預期, 買進, 法人買超, 上漲, 利多, 看好...
**中文負面**：暴跌, 崩跌, 跌停, 虧損, 砍單, 法人賣超, 下跌, 利空...

---

## 四、買賣決策邏輯（`backend/app/services/backtester.py`）

### 買入條件
- 技術評分 ≥ `buy_threshold`（預設 60）
- 目前持倉數 < `max_positions`（預設 5）
- 未持有該股票

### 賣出條件（任一觸發）
| 條件 | 說明 | 預設值 |
|------|------|--------|
| 停損 | 虧損超過 X% 立刻賣出 | -7% |
| 停利 | 獲利超過 X% 立刻賣出 | +15% |
| 追蹤停損 | 從最高點回落 X%（且獲利>3%）| -5% |

### 資金管理
- 每筆交易占總資金 10%（`position_size_pct`）
- 最多同時持有 5 檔（`max_positions`）
- 初始資金 1,000,000 元

---

## 五、可優化的方向

### A. 技術評分權重調整
目前：RSI 25%, MACD 30%, MA 25%, BB 10%, Volume 10%
- **趨勢型市場**：加大 MA 權重（→ 35%），降低 RSI 權重（→ 15%）
- **震盪市場**：加大 RSI + BB 權重，降低 MA 權重
- 修改位置：`technical.py` 第 124 行 `weights = {...}`

### B. RSI 閾值調整
- 目前超賣 < 35，超買 > 65
- 激進策略：超賣 < 40，超買 > 70（更早進場）
- 保守策略：超賣 < 30，超買 > 75（只抓極端值）
- 修改位置：`config.py` `RSI_OVERSOLD`, `RSI_OVERBOUGHT`

### C. 買入門檻（buy_threshold）
- 目前回測預設 60 分，每日推薦不設門檻（只排名）
- 建議範圍：55~70，越高越嚴格、交易次數越少但準確率可能更高
- 回測搜索空間：[50, 55, 60, 65, 70]

### D. 停損/停利參數
- 目前：停損 -7%, 停利 +15%, 追蹤 -5%
- 高波動股（TSLA, NVDA, AMD）建議放寬停損到 -10%
- 低波動股（SPY, QQQ）可縮緊到 -5%
- 修改位置：`config.py` `STOP_LOSS_PCT`, `TAKE_PROFIT_PCT`, `TRAILING_STOP_PCT`

### E. 情緒分析強化方向
- 目前：純關鍵字計數，無上下文理解
- 可優化：加入 negation 處理（"not good" 不應算正面）
- 可優化：加入 emoji 解析（📈😱）
- 可優化：針對不同股票類型使用不同關鍵字庫（科技股 vs 金融股 vs 半導體）
- 修改位置：`sentiment.py` `EN_POS`, `EN_NEG`, `ZH_POS`, `ZH_NEG`

### F. 複合訊號策略（進階）
目前各指標獨立評分後加權，可考慮：
1. **確認訊號**：要求 RSI + MACD 同時看多才給高分
2. **背離偵測**：股價創新高但 RSI 不創新高 → 頂背離警告
3. **量價配合**：爆量突破均線才算有效突破（成交量乘數調整 MA 分）
4. **跳空缺口**：隔日開盤跳空 >3% 加入訊號計算

---

## 六、回測搜索空間（`backtester.py optimize_weights()`）
```python
thresholds = [50.0, 55.0, 60.0, 65.0, 70.0]
stop_losses = [0.05, 0.07, 0.10]
# 共 15 種組合，找 Sharpe ratio 最高的
```
目前只搜索 threshold 和 stop_loss，可以擴展搜索：
- take_profit_pct: [0.10, 0.15, 0.20]
- position_size_pct: [0.05, 0.10, 0.15]

---

## 七、設定檔速查（`backend/app/config.py` / `.env`）

| 參數 | 預設值 | 說明 |
|------|--------|------|
| RSI_PERIOD | 14 | RSI 計算天數 |
| MACD_FAST | 12 | MACD 快線 |
| MACD_SLOW | 26 | MACD 慢線 |
| MACD_SIGNAL | 9 | MACD 訊號線 |
| BB_PERIOD | 20 | 布林帶天數 |
| MA_SHORT | 5 | 短期均線 |
| MA_MID | 20 | 中期均線 |
| MA_LONG | 60 | 長期均線 |
| VOLUME_MA | 20 | 量能均線 |
| WEIGHT_TECHNICAL | 0.6 | 技術分權重 |
| WEIGHT_SENTIMENT | 0.4 | 情緒分權重 |
| STOP_LOSS_PCT | 0.07 | 停損 7% |
| TAKE_PROFIT_PCT | 0.15 | 停利 15% |
| TRAILING_STOP_PCT | 0.05 | 追蹤停損 5% |
| DAILY_RECOMMEND_COUNT | 3 | 每日推薦幾支 |
| PRICE_HISTORY_DAYS | 365 | 抓幾天歷史資料 |

---

## 八、如何叫 Claude 優化

直接說：
- 「讀 STRATEGY.md，幫我把情緒分析改成更精準的版本」
- 「讀 STRATEGY.md，然後把 buy_threshold 回測搜索空間加入 take_profit 參數」
- 「讀 STRATEGY.md，我想改成趨勢型策略，幫我調整技術指標權重」
- 「讀 STRATEGY.md，幫我加入量價背離的訊號」
