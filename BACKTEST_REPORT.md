# Backtest V3 策略回測報告

**日期**: 2026-04-12  
**系統版本**: Money Printer V3 — 多策略回測引擎  
**資料範圍**: 34 支美股（US market filter）  
**共執行 10 組回測**

---

## 1. 測試矩陣

### 已測試

| # | 名稱 | 策略 | Split | 狀態 |
|---|------|------|-------|------|
| 1 | SMC V2 單策略 | smc_v2 | validation (2023-2024) | ✅ |
| 2 | Momentum Breakout 單策略 | momentum_breakout | validation | ✅ (0 trades) |
| 3 | Explosion Scanner 單策略 | explosion_scanner | validation | ✅ |
| 4 | SMC + Momentum | smc_v2 + momentum_breakout | validation | ✅ |
| 5 | SMC + Explosion | smc_v2 + explosion_scanner | validation | ✅ |
| 6 | Momentum + Explosion | momentum_breakout + explosion_scanner | validation | ✅ |
| 7 | 三策略全開 | all 3 | validation | ✅ |
| 8 | Explosion Scanner | explosion_scanner | test (2025-now) | ✅ |
| 9 | SMC + Explosion | smc_v2 + explosion_scanner | test | ✅ |
| 10 | SMC V2 | smc_v2 | test | ✅ |

### 未測試（缺口）

| # | 缺口 | 重要性 | 說明 |
|---|------|--------|------|
| A | **Train split (2018-2022)** | 高 | 長週期測試，含 COVID crash + 2022 熊市，驗證策略在極端行情下的韌性 |
| B | **Momentum Breakout 參數調優** | 高 | 該策略在所有測試中產出 0 筆交易，等於完全沒被驗證，需要降低門檻或調整參數 |
| C | **不同 min_conditions 參數** | 中 | 目前全部用 min_conditions=3，未測 min_conditions=2（更寬鬆）看是否改善交易數量和報酬 |
| D | **不同 min_rr 參數** | 中 | 全部用 min_rr=2.0，未測 1.5 或 1.8 看是否放寬後增加有效交易 |
| E | **不同 risk_per_trade_pct** | 中 | 全用 1.0%，未測 1.5% 或 2.0% 看倉位大小對報酬和 MDD 的影響 |
| F | **不同 max_positions** | 低 | 全用 8，未測 5 或 12 看集中 vs 分散對績效的影響 |
| G | **TW 市場** | 中 | 全部只測 US，未測台股（market_filter="TW"）|
| H | **自訂日期範圍** | 低 | 未測跨 split 的自訂日期，如 2023-06 ~ 2025-06（橫跨 validation + test）|
| I | **壓力測試** | 中 | 未專門測 2022 熊市區間（如 2022-01 ~ 2022-12）看策略在下跌市場的表現 |

---

## 2. Validation 期結果（2023-01-01 ~ 2024-12-31）

| 排名 | 策略組合 | 報酬率 | CAGR | MDD | Sharpe | Sortino | PF | 勝率 | 交易數 | 曝險率 | 期望值 |
|------|---------|--------|------|-----|--------|---------|-----|------|-------|--------|--------|
| 1 | **Explosion Scanner** | +42.57% | 19.49% | -7.80% | 1.689 | 2.368 | 2.48 | 44.4% | 45 | 23.8% | 6.71 |
| 1 | Momentum + Explosion* | +42.57% | 19.49% | -7.80% | 1.689 | 2.368 | 2.48 | 44.4% | 45 | 23.8% | 6.71 |
| 3 | SMC + Explosion | +42.62% | 19.51% | -13.49% | 1.189 | 1.476 | 1.47 | 46.2% | 212 | 52.4% | 2.25 |
| 3 | 三策略全開* | +42.62% | 19.51% | -13.49% | 1.189 | 1.476 | 1.47 | 46.2% | 212 | 52.4% | 2.25 |
| 5 | SMC V2 | +13.63% | 6.63% | -12.15% | 0.571 | 0.644 | 1.20 | 46.6% | 189 | 38.4% | 0.71 |
| 5 | SMC + Momentum* | +13.63% | 6.63% | -12.15% | 0.571 | 0.644 | 1.20 | 46.6% | 189 | 38.4% | 0.71 |
| 7 | Momentum Breakout | 0% | 0% | 0% | 0 | 0 | 0 | 0% | **0** | 0% | 0 |

> *帶星號的組合與其主策略結果相同，因為 Momentum Breakout 沒有產出任何信號

### Validation 期觀察

1. **Explosion Scanner 是絕對贏家**：風險調整後指標全面領先（Sharpe 1.689, Calmar 2.498）
2. **低交易頻率但高品質**：45 筆交易，每筆期望值 6.71%，平均持倉 20 天
3. **SMC V2 交易頻繁但邊際效益低**：189 筆交易只貢獻 +13.63%，平均持倉 5.8 天
4. **加入 SMC 稀釋了 Explosion 的品質**：組合後 MDD 從 -7.8% 惡化到 -13.49%，Sharpe 從 1.689 降到 1.189

---

## 3. Test 期結果（2025-01-01 ~ 至今，Out-of-Sample）

| 排名 | 策略組合 | 報酬率 | CAGR | MDD | Sharpe | PF | 勝率 | 交易數 |
|------|---------|--------|------|-----|--------|-----|------|-------|
| 1 | **SMC + Explosion** | +19.34% | 15.04% | -14.59% | 1.054 | 1.48 | 42.6% | 94 |
| 2 | **SMC V2** | +19.20% | 14.93% | -11.45% | 1.088 | 1.51 | 44.3% | 97 |
| 3 | Explosion Scanner | +5.74% | 4.52% | -4.94% | 0.625 | 1.75 | 33.3% | 12 |

### Test 期觀察

1. **Explosion 在 OOS 大幅衰退**：CAGR 從 19.49% → 4.52%，交易數從 45 → 12（318 天只觸發 12 筆）
2. **SMC V2 反而在 OOS 表現更好**：CAGR 從 6.63% → 14.93%，Sharpe 從 0.571 → 1.088
3. **SMC 是更穩健的策略**：交易頻率穩定（97 筆 / 318 天），不依賴特定市場環境
4. **組合效益在 OOS 不明顯**：SMC + Explosion 和 SMC 單策略報酬幾乎相同

---

## 4. 關鍵問題

### 問題 A: Momentum Breakout 完全失效
- **現象**: 在所有 split（validation + test）中都沒有產出任何交易
- **可能原因**: 信號生成條件過於嚴格、與當前股票池不匹配、或 min_conditions/min_rr 門檻擋掉了所有信號
- **建議**: 需要深入檢查策略的 `generate_signals()` 邏輯，降低門檻做 A/B 測試

### 問題 B: Explosion Scanner OOS 衰退嚴重
- **Validation**: +42.57%, Sharpe 1.689
- **Test**: +5.74%, Sharpe 0.625
- **衰退幅度**: CAGR 下降 77%，交易數下降 73%
- **可能原因**: 
  - 策略可能過度擬合 2023-2024 的市場環境（疫後復甦 + AI 牛市）
  - 信號條件在不同市場 regime 下觸發率差異巨大
- **建議**: 需要 train split (2018-2022) 的數據來判斷是過擬合還是市場環境差異

### 問題 C: 參數敏感度未知
- 所有回測使用相同參數（min_conditions=3, min_rr=2.0, risk=1.0%）
- 無法判斷這些參數是否最優，也不知道小幅調整會如何影響結果
- **建議**: 做參數網格搜索（至少 min_conditions × min_rr × risk 三維度）

### 問題 D: 組合策略未展現分散化效益
- SMC + Explosion 的 MDD 比兩者單獨都高
- 原因可能是策略信號在同一時間觸發，共用 max_positions 導致衝突
- **建議**: 考慮分帳戶機制或策略間的倉位分配比例

---

## 5. 建議的下一步測試

### 優先級 1（必做）
1. **Train split 回測** — 用 2018-2022 數據驗證，確認策略是否只在牛市有效
2. **Momentum Breakout 診斷** — 檢查信號生成，嘗試 min_conditions=2 + min_rr=1.5
3. **參數敏感度測試** — 至少測以下組合：
   - min_conditions: [2, 3, 4]
   - min_rr: [1.5, 2.0, 2.5]
   - risk_per_trade_pct: [0.5, 1.0, 2.0]

### 優先級 2（建議做）
4. **2022 熊市壓力測試** — start_date=2022-01-01, end_date=2022-12-31
5. **台股市場測試** — market_filter="TW" 跑同樣的策略矩陣
6. **max_positions 敏感度** — 測 [4, 6, 8, 12] 看集中度影響

### 優先級 3（nice to have）
7. **跨 split 日期範圍** — 2023-06 ~ 2025-06 看策略在跨期的穩定性
8. **Monte Carlo 模擬** — 打亂交易順序看報酬分佈
9. **滑動窗口測試** — 6 個月為單位，逐月推進，看策略是否有明顯的 regime dependency

---

## 6. 總結

| 指標 | 評分 | 說明 |
|------|------|------|
| 策略覆蓋率 | ⚠️ 2/3 | Momentum Breakout 完全沒信號，等於只測了 2 個策略 |
| 時間覆蓋率 | ⚠️ 2/3 | 缺 train split（2018-2022），沒有長週期熊市驗證 |
| 參數覆蓋率 | ❌ 1 組 | 只用了一組參數，缺敏感度分析 |
| 市場覆蓋率 | ❌ US only | 完全沒測台股 |
| OOS 驗證 | ✅ 已做 | 有 validation → test 的 OOS 對照 |
| 組合策略 | ✅ 已做 | 7 種組合（單策略 × 3 + 雙 × 3 + 三全開）|
| 壓力測試 | ❌ 未做 | 缺 2022 熊市、COVID crash 的專項測試 |

**結論**: 目前的測試確認了 Explosion Scanner 和 SMC V2 各有優勢，但測試深度不足以做出最終策略配置決定。最關鍵的缺口是 (1) Momentum Breakout 需要修復 (2) 缺 train split 長週期驗證 (3) 缺參數敏感度分析。
