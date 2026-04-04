from __future__ import annotations
"""
SMC (Smart Money Concepts) 分析 Service
計算 Order Blocks、Fair Value Gaps、市場結構、量能分佈、走勢機率
"""

import pandas as pd
import numpy as np
from typing import Any


# ─── 工具函數 ──────────────────────────────────────────────────────────────────

def _find_swing_highs(df: pd.DataFrame, left: int = 3, right: int = 3) -> list[dict]:
    """找擺動高點（左右 N 根更低）"""
    highs = []
    hi = df["High"].values
    for i in range(left, len(df) - right):
        if all(hi[i] >= hi[i - j] for j in range(1, left + 1)) and \
           all(hi[i] >= hi[i + j] for j in range(1, right + 1)):
            highs.append({"index": i, "date": str(df.index[i]), "price": float(hi[i])})
    return highs


def _find_swing_lows(df: pd.DataFrame, left: int = 3, right: int = 3) -> list[dict]:
    """找擺動低點"""
    lows = []
    lo = df["Low"].values
    for i in range(left, len(df) - right):
        if all(lo[i] <= lo[i - j] for j in range(1, left + 1)) and \
           all(lo[i] <= lo[i + j] for j in range(1, right + 1)):
            lows.append({"index": i, "date": str(df.index[i]), "price": float(lo[i])})
    return lows


# ─── Order Blocks ──────────────────────────────────────────────────────────────

def find_order_blocks(df: pd.DataFrame, lookback: int = 50) -> list[dict]:
    """
    Order Block：大幅度移動前的最後一根反向K棒
    - 多頭 OB：下跌後的最後一根陰棒（收盤 < 開盤），之後價格大漲超過 threshold
    - 空頭 OB：上漲後的最後一根陽棒（收盤 > 開盤），之後價格大跌超過 threshold
    """
    obs = []
    op = df["Open"].values
    hi = df["High"].values
    lo = df["Low"].values
    cl = df["Close"].values
    n = len(df)
    sub = min(lookback, n)

    threshold = 0.01  # 1% 以上才算有效移動

    for i in range(5, sub):
        # 多頭 OB：找陰棒，且之後 3~10 根有大漲
        if cl[i] < op[i]:  # 陰棒
            for j in range(i + 1, min(i + 10, n)):
                move = (cl[j] - cl[i]) / cl[i]
                if move > threshold:
                    obs.append({
                        "type": "bullish",
                        "date": str(df.index[i]),
                        "top": float(max(op[i], cl[i])),
                        "bottom": float(min(op[i], cl[i])),
                        "high": float(hi[i]),
                        "low": float(lo[i]),
                        "strength": round(abs(move) * 100, 1),
                        "mitigated": float(lo[slice(i + 1, j + 1)].min()) < float(min(op[i], cl[i])),
                    })
                    break

        # 空頭 OB：找陽棒，且之後 3~10 根有大跌
        elif cl[i] > op[i]:  # 陽棒
            for j in range(i + 1, min(i + 10, n)):
                move = (cl[j] - cl[i]) / cl[i]
                if move < -threshold:
                    obs.append({
                        "type": "bearish",
                        "date": str(df.index[i]),
                        "top": float(max(op[i], cl[i])),
                        "bottom": float(min(op[i], cl[i])),
                        "high": float(hi[i]),
                        "low": float(lo[i]),
                        "strength": round(abs(move) * 100, 1),
                        "mitigated": float(hi[slice(i + 1, j + 1)].max()) > float(max(op[i], cl[i])),
                    })
                    break

    # 去重（同日期保留最強）並只回傳最近幾個
    seen = {}
    for ob in obs:
        key = ob["date"]
        if key not in seen or ob["strength"] > seen[key]["strength"]:
            seen[key] = ob
    result = sorted(seen.values(), key=lambda x: x["date"], reverse=True)
    return result[:10]


# ─── Fair Value Gaps ───────────────────────────────────────────────────────────

def find_fvg(df: pd.DataFrame, lookback: int = 60) -> list[dict]:
    """
    Fair Value Gap (FVG / Imbalance)：
    - 多頭 FVG：candle[i-1].high < candle[i+1].low（上漲跳空缺口）
    - 空頭 FVG：candle[i-1].low  > candle[i+1].high（下跌跳空缺口）
    """
    fvgs = []
    hi = df["High"].values
    lo = df["Low"].values
    cl = df["Close"].values
    n = len(df)
    sub = min(lookback, n - 2)

    for i in range(1, sub + 1):
        # 多頭 FVG
        if hi[i - 1] < lo[i + 1]:
            gap_size = lo[i + 1] - hi[i - 1]
            # 是否被填補（之後價格回到缺口範圍）
            filled = any(lo[j] <= lo[i + 1] and hi[j] >= hi[i - 1] for j in range(i + 2, n))
            fvgs.append({
                "type": "bullish",
                "date": str(df.index[i]),
                "top": float(lo[i + 1]),
                "bottom": float(hi[i - 1]),
                "gap_pct": round(gap_size / cl[i] * 100, 2),
                "filled": filled,
            })

        # 空頭 FVG
        elif lo[i - 1] > hi[i + 1]:
            gap_size = lo[i - 1] - hi[i + 1]
            filled = any(hi[j] >= hi[i + 1] and lo[j] <= lo[i - 1] for j in range(i + 2, n))
            fvgs.append({
                "type": "bearish",
                "date": str(df.index[i]),
                "top": float(lo[i - 1]),
                "bottom": float(hi[i + 1]),
                "gap_pct": round(gap_size / cl[i] * 100, 2),
                "filled": filled,
            })

    # 只回傳最近的、未填補的
    result = sorted(fvgs, key=lambda x: x["date"], reverse=True)
    return result[:12]


# ─── 市場結構 (BOS / ChoCH) ────────────────────────────────────────────────────

def find_structure(df: pd.DataFrame) -> dict:
    """
    分析市場結構：
    - BOS (Break of Structure)：同方向突破前高/前低 → 趨勢延續
    - ChoCH (Change of Character)：反向突破 → 趨勢轉換
    """
    swing_highs = _find_swing_highs(df, left=3, right=3)
    swing_lows  = _find_swing_lows(df, left=3, right=3)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"trend": "未知", "bos": [], "choch": [], "swing_highs": swing_highs[-5:], "swing_lows": swing_lows[-5:]}

    # 判斷當前趨勢（最近幾個擺動點的方向）
    recent_highs = sorted(swing_highs[-4:], key=lambda x: x["index"])
    recent_lows  = sorted(swing_lows[-4:], key=lambda x: x["index"])

    hh = len(recent_highs) >= 2 and recent_highs[-1]["price"] > recent_highs[-2]["price"]
    hl = len(recent_lows)  >= 2 and recent_lows[-1]["price"]  > recent_lows[-2]["price"]
    lh = len(recent_highs) >= 2 and recent_highs[-1]["price"] < recent_highs[-2]["price"]
    ll = len(recent_lows)  >= 2 and recent_lows[-1]["price"]  < recent_lows[-2]["price"]

    if hh and hl:
        trend = "上升趨勢"
    elif lh and ll:
        trend = "下降趨勢"
    else:
        trend = "盤整"

    # BOS events（最近 5 個結構突破）
    bos_events = []
    cl = df["Close"].values

    for i in range(1, min(len(swing_highs), 6)):
        sh = swing_highs[-i]
        # 看這個高點後面有沒有被突破
        after_idx = sh["index"] + 1
        if after_idx < len(df):
            broke = any(cl[j] > sh["price"] for j in range(after_idx, min(after_idx + 20, len(df))))
            bos_events.append({
                "type": "bullish_bos" if broke else "bearish_resist",
                "date": sh["date"],
                "price": sh["price"],
                "broke": broke,
            })

    return {
        "trend": trend,
        "bos": bos_events[:5],
        "swing_highs": swing_highs[-6:],
        "swing_lows": swing_lows[-6:],
    }


# ─── 量能分佈 (Volume Profile) ────────────────────────────────────────────────

def volume_profile(df: pd.DataFrame, bins: int = 24) -> dict:
    """
    計算各價格區間的買賣量能分佈
    - 用 VWAP 估算每根K棒的買/賣量
    - 找 POC（Point of Control）：成交量最大的價格
    - 找 Value Area（70% 成交量集中的區間）
    """
    price_min = float(df["Low"].min())
    price_max = float(df["High"].max())
    bin_size  = (price_max - price_min) / bins

    buy_vol  = [0.0] * bins
    sell_vol = [0.0] * bins

    for _, row in df.iterrows():
        mid = (row["High"] + row["Low"]) / 2
        vol = float(row["Volume"])
        is_bull = row["Close"] >= row["Open"]

        bin_idx = int((mid - price_min) / bin_size)
        bin_idx = max(0, min(bins - 1, bin_idx))

        if is_bull:
            buy_vol[bin_idx]  += vol * 0.7
            sell_vol[bin_idx] += vol * 0.3
        else:
            buy_vol[bin_idx]  += vol * 0.3
            sell_vol[bin_idx] += vol * 0.7

    total_vol = [buy_vol[i] + sell_vol[i] for i in range(bins)]

    # POC
    poc_idx  = total_vol.index(max(total_vol))
    poc_price = price_min + (poc_idx + 0.5) * bin_size

    # Value Area（累積 70% 成交量）
    sorted_idx = sorted(range(bins), key=lambda i: -total_vol[i])
    target     = sum(total_vol) * 0.70
    accum, va_bins = 0.0, []
    for idx in sorted_idx:
        accum += total_vol[idx]
        va_bins.append(idx)
        if accum >= target:
            break

    va_high = price_min + (max(va_bins) + 1) * bin_size
    va_low  = price_min + min(va_bins) * bin_size

    levels = []
    for i in range(bins):
        price_lo = price_min + i * bin_size
        price_hi = price_lo + bin_size
        levels.append({
            "price_low":  round(price_lo, 2),
            "price_high": round(price_hi, 2),
            "price_mid":  round((price_lo + price_hi) / 2, 2),
            "buy_vol":    round(buy_vol[i]),
            "sell_vol":   round(sell_vol[i]),
            "total_vol":  round(total_vol[i]),
            "is_poc":     i == poc_idx,
            "in_va":      i in va_bins,
        })

    max_vol = max(total_vol) if total_vol else 1
    for lv in levels:
        lv["buy_pct"]  = round(lv["buy_vol"] / max_vol * 100, 1)
        lv["sell_pct"] = round(lv["sell_vol"] / max_vol * 100, 1)

    return {
        "levels": levels,
        "poc": round(poc_price, 2),
        "va_high": round(va_high, 2),
        "va_low":  round(va_low, 2),
        "price_min": round(price_min, 2),
        "price_max": round(price_max, 2),
    }


# ─── 走勢機率分析 ──────────────────────────────────────────────────────────────

def trend_probability(df: pd.DataFrame, structure: dict, vp: dict) -> dict:
    """
    綜合 SMC 指標估算後續走勢機率
    """
    close = float(df["Close"].iloc[-1])
    scores = {"bullish": 50, "bearish": 50}

    # 1. 趨勢方向
    trend = structure.get("trend", "")
    if trend == "上升趨勢":
        scores["bullish"] += 20
        scores["bearish"] -= 20
    elif trend == "下降趨勢":
        scores["bullish"] -= 20
        scores["bearish"] += 20

    # 2. 相對 POC 位置
    poc = vp.get("poc", close)
    if close > poc:
        scores["bullish"] += 10
        scores["bearish"] -= 10
    else:
        scores["bullish"] -= 10
        scores["bearish"] += 10

    # 3. 相對 Value Area
    va_high = vp.get("va_high", close)
    va_low  = vp.get("va_low", close)
    if close > va_high:
        scores["bullish"] += 15  # 強勢突破 VA
    elif close < va_low:
        scores["bearish"] += 15  # 弱勢跌破 VA
    else:
        scores["bullish"] += 5   # 在 VA 內，偏向均值回歸

    # 4. 最近 5 根K棒動能
    recent = df.tail(5)
    bull_candles = sum(1 for _, r in recent.iterrows() if r["Close"] >= r["Open"])
    if bull_candles >= 4:
        scores["bullish"] += 10
    elif bull_candles <= 1:
        scores["bearish"] += 10

    # 5. 成交量趨勢（最近 5 根 vs 前 10 根）
    if len(df) >= 15:
        recent_vol = float(df["Volume"].tail(5).mean())
        prior_vol  = float(df["Volume"].tail(15).head(10).mean())
        if recent_vol > prior_vol * 1.3:
            # 量增，看是漲是跌
            if bull_candles >= 3:
                scores["bullish"] += 8
            else:
                scores["bearish"] += 8

    # 限制在 20~80 之間
    bull = max(20, min(80, scores["bullish"]))
    bear = 100 - bull

    # 生成文字分析
    reasons = []
    if trend != "未知":
        reasons.append(f"目前市場結構：{trend}")
    if close > poc:
        reasons.append(f"收盤價 {close:.2f} 高於 POC {poc:.2f}，買方佔優")
    else:
        reasons.append(f"收盤價 {close:.2f} 低於 POC {poc:.2f}，賣方佔優")
    if close > va_high:
        reasons.append("突破 Value Area 上緣，短期強勢")
    elif close < va_low:
        reasons.append("跌破 Value Area 下緣，短期弱勢")
    else:
        reasons.append(f"位於 Value Area 內（{va_low:.2f}~{va_high:.2f}），方向待確認")

    if bull >= 60:
        outlook = "偏多"
        detail = "SMC 結構顯示買方力量較強，注意回測 OB/FVG 支撐後的做多機會"
    elif bear >= 60:
        outlook = "偏空"
        detail = "SMC 結構顯示賣方主導，需等待 OB/FVG 測試或結構轉換後才考慮進場"
    else:
        outlook = "中性"
        detail = "買賣力量相當，建議等待明確的 BOS 或 ChoCH 確認方向"

    return {
        "bullish_pct": bull,
        "bearish_pct": bear,
        "outlook": outlook,
        "detail": detail,
        "reasons": reasons,
    }


# ─── SMC 驅動進出場建議 ──────────────────────────────────────────────────────

def compute_smc_entry(
    close: float,
    order_blocks: list[dict],
    fvgs: list[dict],
    key_levels: list[dict],
    structure: dict,
    vp: dict | None = None,
) -> dict | None:
    """
    純 SMC 驅動的進出場建議
    - 買入價：最近的 bullish OB 上緣 / 未填 bullish FVG 底部 / swing low 支撐
    - 停損：買入依據的結構底部（OB bottom / FVG 底 / swing low 下方）
    - 目標：最近的 bearish OB 底部 / swing high 壓力
    - 風報比：動態計算

    如果 SMC 資料不足則回退到 POC / VA 作為參考
    """
    if not close or close <= 0:
        return None

    # ── 收集支撐位（做多進場候選）──────────────────────────────
    supports: list[dict] = []   # {price, stop, source}

    # 1) 未被 mitigate 的 bullish OB → 機構買盤區域
    for ob in order_blocks:
        if ob["type"] == "bullish" and not ob.get("mitigated", True):
            ob_top = ob["top"]
            ob_bottom = ob["bottom"]
            if ob_top < close * 1.02:  # OB 在現價下方（或略高 2%）
                supports.append({
                    "price": ob_top,       # 進場在 OB 上緣
                    "stop": ob_bottom,     # 停損在 OB 下緣（結構失效）
                    "source": "OB",
                    "strength": ob.get("strength", 0),
                })

    # 2) 未填的 bullish FVG → 效率缺口回補區
    for fvg in fvgs:
        if fvg["type"] == "bullish" and not fvg.get("filled", True):
            fvg_top = fvg["top"]
            fvg_bottom = fvg["bottom"]
            if fvg_top < close * 1.02:
                supports.append({
                    "price": fvg_bottom,   # 進場在缺口底部（深度回補）
                    "stop": fvg_bottom * 0.98,  # 停損在缺口下方 2%
                    "source": "FVG",
                    "strength": fvg.get("gap_pct", 0),
                })

    # 3) swing low 支撐位
    for lv in key_levels:
        if lv["type"] == "support" and lv["price"] < close:
            supports.append({
                "price": lv["price"],
                "stop": lv["price"] * 0.97,  # 跌破支撐 3% = 失效
                "source": "SwingLow",
                "strength": 0,
            })

    # 4) POC / VA 作為次要參考
    if vp:
        poc = vp.get("poc", 0)
        va_low = vp.get("va_low", 0)
        if 0 < poc < close:
            supports.append({
                "price": poc,
                "stop": va_low if va_low > 0 else poc * 0.95,
                "source": "POC",
                "strength": 0,
            })

    # ── 收集壓力位（目標價候選）──────────────────────────────
    resistances: list[float] = []

    # 1) bearish OB 底部 → 機構賣壓區
    for ob in order_blocks:
        if ob["type"] == "bearish" and not ob.get("mitigated", True):
            if ob["bottom"] > close:
                resistances.append(ob["bottom"])

    # 2) swing high 壓力位
    for lv in key_levels:
        if lv["type"] == "resistance" and lv["price"] > close:
            resistances.append(lv["price"])

    # 3) VA high 作為次要目標
    if vp:
        va_high = vp.get("va_high", 0)
        if va_high > close:
            resistances.append(va_high)

    # ── 選出最佳進場組合 ──────────────────────────────────────

    if not supports:
        # 完全沒有 SMC 支撐 → 簡易回退（現價下方 3%）
        entry = round(close * 0.97, 2)
        stop = round(close * 0.90, 2)  # -7% from entry
    else:
        # 選離現價最近的支撐（最有可能觸及且風報比合理）
        supports.sort(key=lambda s: abs(close - s["price"]))
        best = supports[0]

        # 如果最近支撐離現價太遠（>10%），取較近的或直接用現價折扣
        if best["price"] < close * 0.90:
            entry = round(close * 0.97, 2)
            stop = round(best["stop"], 2) if best["stop"] > close * 0.85 else round(close * 0.93, 2)
        else:
            entry = round(best["price"], 2)
            stop = round(best["stop"], 2)

    # 停損不能高於買入價
    if stop >= entry:
        stop = round(entry * 0.93, 2)

    # ── 目標價 ────────────────────────────────────────────────
    if resistances:
        # 取最近的壓力位作為目標
        resistances.sort()
        target = round(resistances[0], 2)
        # 如果目標太近（< 5% 獲利），取下一個
        if target < entry * 1.05 and len(resistances) > 1:
            target = round(resistances[1], 2)
        # 如果還是太近，用固定比例
        if target < entry * 1.05:
            target = round(entry * 1.12, 2)
    else:
        target = round(entry * 1.12, 2)

    # 確保目標高於進場
    if target <= entry:
        target = round(entry * 1.10, 2)

    # ── 風報比 ────────────────────────────────────────────────
    risk = entry - stop
    reward = target - entry
    rr = round(reward / max(risk, 0.01), 1) if risk > 0 else 0

    # 收集建議來源說明
    sources_used = list(set(s["source"] for s in supports[:3])) if supports else ["Fallback"]
    target_source = "OB壓力" if any(ob["type"] == "bearish" and not ob.get("mitigated") and ob["bottom"] == target for ob in order_blocks) else "結構壓力"

    return {
        "entry": entry,
        "stop": stop,
        "target": target,
        "rr": rr,
        "entry_basis": "+".join(sources_used),       # e.g. "OB+FVG"
        "target_basis": target_source,
        "risk_pct": round((entry - stop) / entry * 100, 1),
        "reward_pct": round((target - entry) / entry * 100, 1),
    }


# ─── 主入口 ────────────────────────────────────────────────────────────────────

def run_smc_analysis(df: pd.DataFrame) -> dict[str, Any]:
    """對 DataFrame 執行完整 SMC 分析"""
    if df is None or len(df) < 20:
        return {"error": "資料不足（需至少 20 根K棒）"}

    obs       = find_order_blocks(df)
    fvgs      = find_fvg(df)
    structure = find_structure(df)
    vp        = volume_profile(df)
    prob      = trend_probability(df, structure, vp)

    # 關鍵支撐/壓力價位
    swing_highs = structure.get("swing_highs", [])
    swing_lows  = structure.get("swing_lows", [])
    key_levels = []
    for sh in swing_highs[-3:]:
        key_levels.append({"type": "resistance", "price": sh["price"], "date": sh["date"]})
    for sl in swing_lows[-3:]:
        key_levels.append({"type": "support", "price": sl["price"], "date": sl["date"]})
    key_levels.sort(key=lambda x: x["price"])

    close = float(df["Close"].iloc[-1])
    entry_sug = compute_smc_entry(
        close=close,
        order_blocks=obs,
        fvgs=fvgs,
        key_levels=key_levels,
        structure=structure,
        vp=vp,
    )

    return {
        "order_blocks": obs,
        "fvg": fvgs,
        "structure": structure,
        "volume_profile": vp,
        "probability": prob,
        "key_levels": key_levels,
        "entry_suggestion": entry_sug,
    }
