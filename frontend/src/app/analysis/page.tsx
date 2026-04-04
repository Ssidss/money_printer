export default function AnalysisPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">系統說明手冊</h1>
        <p className="text-slate-500 text-sm mt-1">Money Printer v2 — 分層決策架構 · 趨勢追蹤 · SMC 驅動進場</p>
      </div>

      {/* ── 1. 系統在做什麼 ── */}
      <Section title="這個系統在做什麼？" icon="🤖">
        <p className="text-slate-600 leading-relaxed mb-4">
          系統每天自動對所有追蹤的股票執行<strong className="text-slate-800">三層分析</strong>，
          透過條件計數（而非加權平均）決定推薦等級和倉位大小，幫你篩選出「現在最值得關注」的標的。
        </p>
        <div className="grid grid-cols-3 gap-3">
          {[
            { emoji: "📅", label: "每天跑一次", desc: "台股18:30 / 美股06:30 自動執行，或手動觸發" },
            { emoji: "🧩", label: "分層決策", desc: "SMC門檻 → 動量確認 → 催化劑 → 條件計數" },
            { emoji: "🎯", label: "SMC 驅動進場", desc: "買入價基於 OB/FVG 結構，非固定百分比" },
          ].map(c => (
            <div key={c.label} className="bg-slate-50 rounded-xl p-4 text-center border border-slate-100">
              <div className="text-2xl mb-1">{c.emoji}</div>
              <div className="text-sm font-semibold text-slate-700">{c.label}</div>
              <div className="text-xs text-slate-400 mt-1">{c.desc}</div>
            </div>
          ))}
        </div>
        <Callout type="tip" text="系統是輔助工具，不是自動交易機器人。它幫你縮小範圍、給出參考價位，但最終決策還是你做。" />
      </Section>

      {/* ── 2. 分層決策架構 ── */}
      <Section title="分層決策架構（v2）" icon="🧮">
        <p className="text-slate-600 mb-5 leading-relaxed">
          v2 版本<strong className="text-slate-800">不再使用加權平均</strong>來決定推薦等級。
          改用「條件計數」：滿足越多條件 → 推薦等級越高、倉位越大。SMC 結構是第一道門檻。
        </p>

        {/* 分層流程視覺化 */}
        <div className="bg-slate-50 rounded-xl border border-slate-200 p-5 mb-5">
          <div className="space-y-3">
            {[
              { layer: "Layer 1", label: "SMC 結構門檻", desc: "下降趨勢 → 直接排除（不做多）", color: "bg-red-500" },
              { layer: "Layer 2", label: "動量確認", desc: "技術分 ≥ 60 → 通過（MACD/RSI/MA/BB/Vol 加權）", color: "bg-blue-500" },
              { layer: "Layer 3", label: "催化劑確認", desc: "新聞情緒 ≥ 65 → 加速；≤ 35 → 警告", color: "bg-purple-500" },
              { layer: "Layer 4", label: "風報比確認", desc: "SMC 進場的 R:R ≥ 2.0 → 加分", color: "bg-green-500" },
            ].map(l => (
              <div key={l.layer} className="flex items-center gap-3">
                <span className={`text-xs font-bold text-white px-2 py-1 rounded ${l.color} w-16 text-center`}>{l.layer}</span>
                <div>
                  <span className="text-sm font-semibold text-slate-700">{l.label}</span>
                  <span className="text-xs text-slate-400 ml-2">{l.desc}</span>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-4 pt-3 border-t border-slate-200 text-sm text-slate-600">
            <span className="font-semibold text-indigo-600">條件計數：</span>
            最多 4 個條件同時滿足 → 依計數決定推薦等級 + 倉位大小
          </div>
        </div>

        {/* 技術分（動量）拆解 */}
        <h3 className="text-sm font-semibold text-slate-700 mb-3">動量分（0–100）= 五個指標加權（趨勢追蹤版）</h3>
        <div className="rounded-xl border border-slate-200 overflow-hidden mb-5">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-500 text-xs uppercase">
                <th className="text-left px-4 py-2">指標</th>
                <th className="text-center px-4 py-2">權重</th>
                <th className="text-left px-4 py-2">高分條件</th>
                <th className="text-left px-4 py-2">低分條件</th>
              </tr>
            </thead>
            <tbody>
              {[
                { name: "MACD",   w: "30%", high: "金叉 + 柱體放大（底部金叉最強 90 分）", low: "死叉，MACD < 0 且 < Signal（15 分）" },
                { name: "均線",   w: "25%", high: "收盤 > MA5 > MA20 > MA60（多頭排列 90 分）", low: "收盤 < MA5 < MA20 < MA60（空頭排列 10 分）" },
                { name: "RSI",    w: "20%", high: "RSI 50-65 動量健康（85 分）、65-75 仍強勢", low: "RSI < 30 極度弱勢（20 分，不抄底）" },
                { name: "成交量", w: "15%", high: "帶量上漲 ≥ 2x 均量（95 分）", low: "帶量下跌 ≥ 2x 均量（15 分，賣壓湧入）" },
                { name: "布林通道", w:"10%", high: "突破上軌 = 強勢動能（85 分）", low: "跌破下軌 = 弱勢（15 分）" },
              ].map(r => (
                <tr key={r.name} className="border-t border-slate-100">
                  <td className="px-4 py-2.5 font-medium text-slate-700">{r.name}</td>
                  <td className="px-4 py-2.5 text-center">
                    <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded font-semibold">{r.w}</span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-green-700">{r.high}</td>
                  <td className="px-4 py-2.5 text-xs text-red-500">{r.low}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* 綜合分調整 */}
        <h3 className="text-sm font-semibold text-slate-700 mb-3">綜合分微調（用於排序，非決定推薦等級）</h3>
        <div className="grid grid-cols-4 gap-2 mb-4">
          {[
            { trend: "上升趨勢", mult: "×1.10", color: "bg-green-50 border-green-200", tc: "text-green-700", desc: "順勢加分" },
            { trend: "盤整",     mult: "×0.92", color: "bg-yellow-50 border-yellow-200", tc: "text-yellow-700", desc: "方向不明微扣" },
            { trend: "催化劑+", mult: "×1.05", color: "bg-blue-50 border-blue-200", tc: "text-blue-700", desc: "正面新聞加分" },
            { trend: "催化劑-", mult: "×0.90", color: "bg-red-50 border-red-200", tc: "text-red-600", desc: "負面新聞扣分" },
          ].map(s => (
            <div key={s.trend} className={`rounded-xl border p-3 text-center ${s.color}`}>
              <div className={`text-lg font-bold ${s.tc}`}>{s.mult}</div>
              <div className={`text-xs font-semibold mt-1 ${s.tc}`}>{s.trend}</div>
              <div className="text-xs text-slate-400 mt-0.5">{s.desc}</div>
            </div>
          ))}
        </div>
        <Callout type="warning" text="下降趨勢在 Layer 1 直接排除，不會進入後續計算。綜合分只用於同等級內的排序，推薦等級由條件計數決定。" />
      </Section>

      {/* ── 3. 推薦等級 + 倉位等級 ── */}
      <Section title="推薦等級 × 倉位等級" icon="🏷">
        <p className="text-slate-600 mb-4 leading-relaxed">
          v2 的推薦等級<strong className="text-slate-800">不再由分數區間決定</strong>，
          而是由「滿足幾個條件」決定。每個等級對應建議的倉位大小。
        </p>
        <div className="space-y-3">
          {[
            { level: "🟢 強力推薦", conds: "4 條件全滿", tier: "核心持倉 15-20%", color: "border-green-200 bg-green-50",
              tc: "text-green-700",
              desc: "SMC 上升 + 動量強勁 + 正面催化劑 + R:R ≥ 2.0，所有條件到位。",
              do_: "可考慮較大倉位進場，以量化建議的買入價為基準" },
            { level: "🔵 推薦", conds: "≥ 3 條件", tier: "標準倉位 8-12%", color: "border-blue-200 bg-blue-50",
              tc: "text-blue-700",
              desc: "主要條件滿足，但可能缺少催化劑或風報比偏低。",
              do_: "標準倉位進場，設好停損嚴格執行" },
            { level: "🟡 觀察", conds: "≥ 2 條件", tier: "探索倉位 3-5%", color: "border-yellow-200 bg-yellow-50",
              tc: "text-yellow-700",
              desc: "條件不完整，可能在盤整或缺乏催化劑。",
              do_: "小量試探或等待更多條件確認後再加碼" },
            { level: "⚪ 不推薦", conds: "< 2 條件 或下降趨勢", tier: "不建倉", color: "border-slate-200 bg-slate-50",
              tc: "text-slate-500",
              desc: "條件不足或 SMC 下降趨勢（Layer 1 直接排除）。",
              do_: "不買。若已持有，評估是否繼續持有或停損" },
          ].map(r => (
            <div key={r.level} className={`rounded-xl border p-4 ${r.color}`}>
              <div className="flex items-start justify-between mb-2">
                <div>
                  <span className={`font-bold text-sm ${r.tc}`}>{r.level}</span>
                  <span className="ml-2 text-xs bg-white/60 px-2 py-0.5 rounded font-mono text-slate-500">{r.conds}</span>
                </div>
                <span className={`text-xs font-semibold px-2 py-1 rounded-lg bg-white/60 ${r.tc}`}>{r.tier}</span>
              </div>
              <p className="text-xs text-slate-600 mb-1">{r.desc}</p>
              <p className="text-xs text-slate-500">{r.do_}</p>
            </div>
          ))}
        </div>
        <Callout type="tip" text="盤整中即使條件數夠多，最高只到「標準倉位」，不會出現盤整中的核心持倉。" />
      </Section>

      {/* ── 4. 量化建議欄位說明（SMC 驅動版） ── */}
      <Section title="量化建議欄位說明（SMC 驅動）" icon="📐">
        <p className="text-slate-600 mb-4 leading-relaxed">
          v2 的進場價位<strong className="text-slate-800">不再是固定百分比計算</strong>（如 MA20、entry×0.93），
          而是根據 SMC 結構中的 OB、FVG、Swing Low 等關鍵價位動態決定。
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-3">
            {[
              { label: "買", color: "text-indigo-600", title: "建議買入價",
                desc: "優先：未被觸及的多頭 OB 頂部 → 未填的多頭 FVG 底部 → Swing Low → POC → 收盤×0.97" },
              { label: "停", color: "text-red-500",    title: "建議停損價",
                desc: "設在買入價所在結構的底部。OB 進場停在 OB 底下；FVG 進場停在 FVG 底下。" },
            ].map(f => (
              <div key={f.label} className="flex gap-3 items-start bg-slate-50 rounded-xl p-3 border border-slate-100">
                <span className={`text-lg font-bold w-6 text-center ${f.color}`}>{f.label}</span>
                <div>
                  <p className="text-sm font-semibold text-slate-700">{f.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
          <div className="space-y-3">
            {[
              { label: "目", color: "text-green-600",  title: "目標價",
                desc: "優先：空頭 OB 底部（壓力）→ Swing High → VA High → 買入價 × 1.12" },
              { label: "R:R", color: "text-slate-600", title: "風報比",
                desc: "= (目標 - 買入) ÷ (買入 - 停損)。R:R ≥ 2.0 才算優秀，< 1.5 應謹慎。" },
            ].map(f => (
              <div key={f.label} className="flex gap-3 items-start bg-slate-50 rounded-xl p-3 border border-slate-100">
                <span className={`text-sm font-bold w-6 text-center ${f.color}`}>{f.label}</span>
                <div>
                  <p className="text-sm font-semibold text-slate-700">{f.title}</p>
                  <p className="text-xs text-slate-400 mt-0.5 leading-relaxed">{f.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="mt-4 bg-indigo-50 border border-indigo-100 rounded-xl p-4">
          <p className="text-sm font-semibold text-indigo-700 mb-2">倉位等級徽章</p>
          <div className="grid grid-cols-3 gap-3 text-xs">
            <div className="flex items-center gap-2"><span className="text-green-600 font-bold">🟢 核心</span><span className="text-slate-500">15-20%，全部條件到位</span></div>
            <div className="flex items-center gap-2"><span className="text-blue-600 font-bold">🔵 標準</span><span className="text-slate-500">8-12%，主要條件滿足</span></div>
            <div className="flex items-center gap-2"><span className="text-yellow-600 font-bold">🟡 探索</span><span className="text-slate-500">3-5%，先小量試探</span></div>
          </div>
        </div>
        <Callout type="warning" text="量化建議是基於當下 SMC 結構動態計算的，每次分析會更新。高波動標的（TSLA、SMCI、ALAB 等）結構變化快，進場前務必到個股頁確認最新 OB/FVG 位置。" />
      </Section>

      {/* ── 5. 每日操作 SOP ── */}
      <Section title="每日操作 SOP" icon="📋">
        <div className="space-y-4">
          {[
            {
              step: "1", color: "bg-indigo-500", title: "看 Dashboard（每天）",
              items: [
                "確認今日 Top 3 推薦 — 是否有新的強力推薦出現",
                "看「持倉速覽」— 有無 ⚠ 接近停損 的警示，有的話優先處理",
                "右上角確認分析日期是否是今天，若不是點「立即分析」更新",
              ],
            },
            {
              step: "2", color: "bg-blue-500", title: "篩選買入候選（有興趣時）",
              items: [
                "進「股票清單」→ 切到美股或台股 tab",
                "找「強力推薦 + 上升趨勢 + 🟢核心持倉」的組合（最理想）",
                "看量化建議欄：R:R ≥ 2.0 且有明確的 OB/FVG 進場依據",
                "SMC 趨勢必須是上升趨勢，不在上升趨勢不買",
              ],
            },
            {
              step: "3", color: "bg-violet-500", title: "進個股頁確認（買之前一定要做）",
              items: [
                "看右上角走勢機率：看漲機率 ≥ 55% 才考慮",
                "看 K 線圖上的綠色 OB 線 — 當前價是否在 OB 支撐附近",
                "看「關鍵支撐/壓力」面板 — 確認停損位有沒有強支撐",
                "確認近期沒有大型空頭 FVG 在上方擋路",
                "看量化建議卡：確認進場依據（如 OB+FVG）和倉位等級",
              ],
            },
            {
              step: "4", color: "bg-green-500", title: "執行買入（確認後）",
              items: [
                "進「投資組合」頁 → 點「買入」",
                "依倉位等級決定買入金額（核心 15-20%、標準 8-12%、探索 3-5%）",
                "以量化建議的「買入價」為基準，可以分批（先買一半）",
              ],
            },
            {
              step: "5", color: "bg-amber-500", title: "持倉監控（持有期間）",
              items: [
                "每天看 Dashboard 持倉速覽的損益欄和 SMC 趨勢欄",
                "出現「⚠ 接近停損」或 SMC 轉為「下降趨勢」→ 重新評估是否繼續持有",
                "跌破停損價 → 無條件出場，不要期待反彈",
                "到達目標價 → 可以先出一半，剩一半用追蹤停損跟趨勢走",
              ],
            },
          ].map(s => (
            <div key={s.step} className="flex gap-4">
              <div className={`w-8 h-8 rounded-full ${s.color} text-white flex items-center justify-center text-sm font-bold flex-shrink-0 mt-0.5`}>
                {s.step}
              </div>
              <div className="flex-1 pb-4 border-b border-slate-100 last:border-0">
                <p className="font-semibold text-slate-800 mb-2">{s.title}</p>
                <ul className="space-y-1.5">
                  {s.items.map((item, i) => (
                    <li key={i} className="text-sm text-slate-600 flex gap-2">
                      <span className="text-slate-300 mt-0.5 flex-shrink-0">›</span>{item}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 6. 各頁面功能速查 ── */}
      <Section title="各頁面功能速查" icon="🗺">
        <div className="space-y-3">
          {[
            { page: "Dashboard /", icon: "🏠", points: [
              "Top 3 推薦卡片（今日最值得看的標的）",
              "持倉速覽：當前價、損益、SMC趨勢、接近停損警示",
              "追蹤清單總覽：所有股票的分數和趨勢一眼看到底",
            ]},
            { page: "股票清單 /stocks", icon: "📋", points: [
              "可切換 全部 / 美股 / 台股 tab 篩選",
              "量化建議欄：每支股票的建議買 / 停 / 目標 / R:R + 倉位等級",
              "新增追蹤按鈕（右上角）、移除按鈕（每行右側）",
            ]},
            { page: "個股頁 /stocks/[ticker]", icon: "📈", points: [
              "K線圖含 SMC 疊加：OB 線（綠/紅虛線）、FVG 線、POC、價值區",
              "走勢機率：↑XX% ↓XX%，綜合 SMC 結構 + Volume Profile 計算",
              "量化建議卡：SMC 驅動的買入/停損/目標/R:R + 進場依據 + 倉位等級",
              "Order Blocks 列表、FVG 列表（只顯示未填的）",
              "右側面板：量能分佈視覺化、關鍵支撐/壓力、最新新聞",
            ]},
            { page: "投資組合 /portfolio", icon: "💼", points: [
              "持倉表：當前價、損益%、停損/停利、SMC趨勢",
              "買入/賣出 Modal（右上角 + 每行操作欄）",
              "完整交易紀錄",
            ]},
            { page: "回測 /backtest", icon: "🧪", points: [
              "SMC 設定區：可選擇開關「過濾下降趨勢入場」和「趨勢反轉出場」",
              "追蹤停損：利潤達 5% 後啟動，保護獲利但不截斷上升趨勢",
              "歷史回測結果列表：年化報酬、最大回撤、Sharpe、勝率",
            ]},
          ].map(p => (
            <div key={p.page} className="rounded-xl border border-slate-200 bg-white p-4">
              <div className="flex items-center gap-2 mb-2">
                <span>{p.icon}</span>
                <span className="font-semibold text-slate-700 text-sm">{p.page}</span>
              </div>
              <ul className="space-y-1">
                {p.points.map((pt, i) => (
                  <li key={i} className="text-xs text-slate-500 flex gap-2">
                    <span className="text-slate-300 flex-shrink-0 mt-0.5">·</span>{pt}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 7. 回測結論 ── */}
      <Section title="回測結論與建議參數" icon="📊">
        <p className="text-slate-600 mb-4 leading-relaxed">
          共跑了 8 次回測，測試有無 SMC 過濾、不同門檻與倉位集中度。
          以下是各組對比，<strong className="text-slate-800">B 組整體最佳</strong>。
        </p>
        <div className="rounded-xl border border-slate-200 overflow-hidden mb-4">
          <table className="w-full text-xs">
            <thead>
              <tr className="bg-slate-50 text-slate-500 uppercase text-xs">
                <th className="text-left px-3 py-2">組合</th>
                <th className="text-right px-3 py-2">年化</th>
                <th className="text-right px-3 py-2">最大回撤</th>
                <th className="text-right px-3 py-2">Sharpe</th>
                <th className="text-right px-3 py-2">勝率</th>
              </tr>
            </thead>
            <tbody>
              {[
                { name: "無 SMC（基準）",    annual: "0.53%",  dd: "23.52%", sharpe: "0.428", wr: "48%",   highlight: false },
                { name: "SMC 全開",          annual: "2.65%",  dd: "30.02%", sharpe: "0.554", wr: "47%",   highlight: false },
                { name: "A 高門檻+集中倉",   annual: "3.57%",  dd: "25.56%", sharpe: "0.420", wr: "47%",   highlight: false },
                { name: "B 只過濾入場 ✅",   annual: "3.79%",  dd: "31.46%", sharpe: "0.658", wr: "51%",   highlight: true },
              ].map(r => (
                <tr key={r.name} className={`border-t border-slate-100 ${r.highlight ? "bg-indigo-50" : ""}`}>
                  <td className={`px-3 py-2 font-medium ${r.highlight ? "text-indigo-700" : "text-slate-700"}`}>{r.name}</td>
                  <td className="px-3 py-2 text-right text-green-600 font-medium">{r.annual}</td>
                  <td className="px-3 py-2 text-right text-red-500">{r.dd}</td>
                  <td className="px-3 py-2 text-right text-slate-600">{r.sharpe}</td>
                  <td className="px-3 py-2 text-right text-slate-600">{r.wr}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4">
          <p className="text-sm font-semibold text-indigo-700 mb-2">✅ 建議採用的回測設定（B 組邏輯）</p>
          <div className="grid grid-cols-3 gap-x-4 gap-y-1 text-xs text-indigo-600">
            {[
              ["買入門檻", "60 分"],
              ["停損", "7%"],
              ["追蹤停損", "5%（利潤>5%後啟動）"],
              ["單筆倉位", "10%"],
              ["最大持倉", "5 支"],
              ["SMC 入場過濾", "✅ 開"],
              ["SMC 趨勢反轉出場", "❌ 關"],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between">
                <span className="text-indigo-400">{k}</span>
                <span className="font-semibold">{v}</span>
              </div>
            ))}
          </div>
        </div>
        <Callout type="warning" text="最大回撤 25-31% 的主因是跳空事件（ALAB -23%、UNH -18%），這是 7% 停損無法防住的風險。高波動股票（SMCI、SNOW、ALAB）建議半倉操作或避開財報前後。" />
      </Section>

      {/* ── 8. SMC 概念速查 ── */}
      <Section title="SMC 核心概念速查" icon="🧠">
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">市場結構</h3>
            <div className="space-y-2">
              <ConceptRow tag="上升趨勢" tagColor="bg-green-100 text-green-700"
                desc="HH+HL：每個高點和低點都比前一個高。只做多方向。" />
              <ConceptRow tag="下降趨勢" tagColor="bg-red-100 text-red-700"
                desc="LH+LL：每個高點和低點都比前一個低。Layer 1 直接排除，不做多。" />
              <ConceptRow tag="盤整" tagColor="bg-yellow-100 text-yellow-700"
                desc="在前期高低點區間內震盪。可小量試探，但倉位上限為標準倉位。" />
              <ConceptRow tag="BOS" tagColor="bg-blue-100 text-blue-700"
                desc="突破結構（Break of Structure）：突破前高/前低，趨勢延續的確認訊號。" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">訂單塊 (Order Block)</h3>
            <div className="space-y-2">
              <ConceptRow tag="多頭 OB 🟢" tagColor="bg-green-100 text-green-700"
                desc="大漲前的最後一根陰棒區域。回測到此區域是做多機會。系統優先用未被觸及的多頭 OB 頂部作為買入價。" />
              <ConceptRow tag="空頭 OB 🔴" tagColor="bg-red-100 text-red-700"
                desc="大跌前的最後一根陽棒區域。反彈到此區域是壓力。系統用空頭 OB 底部作為目標價。" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Fair Value Gap (FVG)</h3>
            <div className="space-y-2">
              <ConceptRow tag="多頭 FVG" tagColor="bg-indigo-100 text-indigo-700"
                desc="快速上漲留下的缺口，市場高機率回來補。無 OB 時，系統用未填的多頭 FVG 底部作為買入價。" />
              <ConceptRow tag="空頭 FVG" tagColor="bg-orange-100 text-orange-700"
                desc="快速下跌留下的缺口，反彈到此有壓力。" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">量能分佈 (Volume Profile)</h3>
            <div className="space-y-2">
              <ConceptRow tag="POC" tagColor="bg-amber-100 text-amber-700"
                desc="成交量最大的價格（Point of Control）。偏離 POC 越遠越容易被吸引回來。無 OB/FVG 時作為買入參考。" />
              <ConceptRow tag="Value Area" tagColor="bg-indigo-100 text-indigo-700"
                desc="70% 成交量集中的區間。VA High 可作為目標價參考；突破 VA High 是強訊號。" />
            </div>
          </div>
        </div>
        <div className="mt-4 bg-amber-50 border border-amber-100 rounded-xl p-4">
          <p className="text-sm font-semibold text-amber-700 mb-1">⚡ 最強進場條件（Confluence Zone）</p>
          <p className="text-sm text-amber-600">
            OB + FVG + POC 在同一個價格區域重疊 → 支撐力道最強，是最理想的進場點。
          </p>
        </div>
      </Section>

      {/* ── 9. 趨勢追蹤哲學 ── */}
      <Section title="核心投資哲學：趨勢追蹤" icon="🎯">
        <p className="text-slate-600 mb-4 leading-relaxed">
          本系統的設計哲學是<strong className="text-slate-800">趨勢追蹤（Trend Following）</strong>，
          而非均值回歸。以下是幾個核心原則：
        </p>
        <div className="space-y-3">
          {[
            { icon: "📈", title: "RSI 高 = 動量強，不是超買", desc: "RSI 65 不代表要賣，而是動量健康。只有 RSI > 80 才微扣分。" },
            { icon: "💥", title: "布林突破上軌 = 強勢動能", desc: "突破上軌代表強勢，給 85 分。不是「要回歸中軌」的賣出訊號。" },
            { icon: "📊", title: "量價配合是關鍵", desc: "漲 + 量增 = 有資金推動；漲 + 量縮 = 動能不足要小心。" },
            { icon: "🚫", title: "不抄底、不接刀", desc: "RSI < 30 給 20 分（最低），趨勢追蹤不在下降中買入。" },
            { icon: "🔒", title: "停損紀律", desc: "跌破停損無條件出場。最多 8-10 持倉，單筆依倉位等級控制風險。" },
          ].map(p => (
            <div key={p.title} className="flex gap-3 items-start bg-slate-50 rounded-xl p-3 border border-slate-100">
              <span className="text-xl flex-shrink-0">{p.icon}</span>
              <div>
                <p className="text-sm font-semibold text-slate-700">{p.title}</p>
                <p className="text-xs text-slate-400 mt-0.5">{p.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </Section>

    </div>
  )
}

// ─── 小元件 ─────────────────────────────────────────────────────────────────

function Section({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="text-lg font-bold text-slate-800 mb-4 flex items-center gap-2">
        <span>{icon}</span>{title}
      </h2>
      {children}
    </div>
  )
}

function ConceptRow({ tag, tagColor, desc }: { tag: string; tagColor: string; desc: string }) {
  return (
    <div className="flex gap-3 items-start">
      <span className={`text-xs font-bold px-2 py-0.5 rounded whitespace-nowrap mt-0.5 ${tagColor}`}>{tag}</span>
      <p className="text-xs text-slate-500 leading-relaxed">{desc}</p>
    </div>
  )
}

function Callout({ type, text }: { type: "tip" | "how" | "warning"; text: string }) {
  const styles = {
    tip:     { bg: "bg-blue-50 border-blue-100",   icon: "💡", color: "text-blue-700" },
    how:     { bg: "bg-green-50 border-green-100", icon: "🖥",  color: "text-green-700" },
    warning: { bg: "bg-amber-50 border-amber-100", icon: "⚠️", color: "text-amber-700" },
  }
  const s = styles[type]
  return (
    <div className={`mt-4 rounded-xl border p-3 flex gap-2 ${s.bg}`}>
      <span className="flex-shrink-0">{s.icon}</span>
      <p className={`text-sm ${s.color}`}>{text}</p>
    </div>
  )
}
