"""情緒分析 Service — 關鍵字加權，中英文雙語，不需付費 API"""

import re

EN_POS = {"beat":3,"beats":3,"record":3,"surge":3,"soar":3,"skyrocket":3,
           "breakthrough":3,"upgrade":3,"outperform":3,"growth":2,"profit":2,
           "revenue":2,"bullish":2,"rally":2,"gain":2,"rise":2,"higher":2,
           "increase":2,"expand":2,"recovery":2,"rebound":2,"dividend":2,
           "buyback":2,"up":1,"good":1,"better":1,"improve":1,"optimistic":1}
EN_NEG = {"miss":3,"misses":3,"crash":3,"plunge":3,"collapse":3,"bankrupt":3,
           "fraud":3,"investigation":3,"downgrade":3,"underperform":3,"slash":3,
           "loss":2,"decline":2,"drop":2,"fall":2,"lower":2,"bearish":2,
           "concern":2,"risk":2,"warning":2,"recall":2,"layoff":2,"lawsuit":2,
           "fine":2,"penalty":2,"down":1,"weak":1,"slow":1,"disappoint":1,
           "uncertain":1,"pressure":1}
ZH_POS = {"大漲":3,"創新高":3,"超預期":3,"爆量":3,"突破":3,"飆漲":3,
           "買進":3,"法人買超":3,"外資買超":3,"上漲":2,"獲利":2,"營收成長":2,
           "利多":2,"看好":2,"多頭":2,"反彈":2,"回升":2,"成長":2,"配息":2,
           "庫藏股":2,"訂單":2,"向上":1,"樂觀":1,"改善":1,"受惠":1}
ZH_NEG = {"暴跌":3,"崩跌":3,"跌停":3,"虧損":3,"詐欺":3,"調查":3,
           "下修":3,"砍單":3,"法人賣超":3,"外資賣超":3,"下跌":2,"利空":2,
           "看空":2,"空頭":2,"衰退":2,"裁員":2,"罰款":2,"訴訟":2,
           "下滑":2,"警示":2,"疑慮":1,"壓力":1,"不確定":1,"謹慎":1}


def score_title(text: str) -> float:
    """單一標題 → 情緒分數 0~100（50=中性）"""
    tl = text.lower()
    pos, neg = 0, 0
    for w, wt in EN_POS.items():
        if re.search(r'\b' + w + r'\b', tl):
            pos += wt
    for w, wt in EN_NEG.items():
        if re.search(r'\b' + w + r'\b', tl):
            neg += wt
    for w, wt in ZH_POS.items():
        if w in text:
            pos += wt
    for w, wt in ZH_NEG.items():
        if w in text:
            neg += wt
    net = pos - neg
    score = 50 + net * 10
    return round(max(0.0, min(100.0, score)), 1)


def aggregate_sentiment(scores: list[float]) -> dict:
    """將一組文章分數合併成整體情緒結果"""
    if not scores:
        return {"score": 50.0, "label": "中性（無新聞）", "article_count": 0}
    avg = sum(scores) / len(scores)
    avg = max(0, min(100, avg))
    if avg >= 65:   label = "正面"
    elif avg >= 55: label = "偏正面"
    elif avg >= 45: label = "中性"
    elif avg >= 35: label = "偏負面"
    else:           label = "負面"
    return {"score": round(avg, 1), "label": label, "article_count": len(scores)}
