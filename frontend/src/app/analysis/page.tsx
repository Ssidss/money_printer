export default function AnalysisPage() {
  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">系統說明手冊</h1>
        <p className="text-slate-500 text-sm mt-1">Money Printer v2 — 評分原理 · 操作流程 · SMC 策略</p>
      </div>

      {/* ── 1. 系統在做什麼 ── */}
      <Section title="這個系統在做什麼？" icon="🤖">
        <p className="text-slate-600 leading-relaxed mb-4">
          系統每天自動對所有追蹤的股票執行三層分析，輸出一個 <strong className="text-slate-800">0–100 的綜合分數</strong>，
          幫你篩選出「現在最值得關注」的標的。你不需要每天盯盤，只需要：
        </p>
        <div className="grid grid-cols-3 gap-3">
          {[
            { emoji: "📅", label: "每天跑一次", desc: "台股18:30 / 美股06:30 自動執行，或手動觸發" },
            { emoji: "📊", label: "輸出綜合分", desc: "技術 + 情緒 + SMC 三層評分整合" },
            { emoji: "🎯", label: "給你決策依據", desc: "買入建議價、停損、目標、風報比" },
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

      {/* ── 2. 評分公式（最新版，含 SMC）── */}
      <Section title="評分公式（含 SMC 整合）" icon="🧮">
        <p className="text-slate-600 mb-5 leading-relaxed">
          綜合分數由三個層次計算，<strong className="text-slate-800">SMC 趨勢是最後一道過濾器</strong>，
          可以大幅修正技術分數失真的情況（例如下降趨勢中 RSI 超賣看起來分數很高，但其實是繼續跌的陷阱）。
        </p>

        {/* 公式視覺化 */}
        <div className="bg-slate-50 rounded-xl border border-slate-200 p-5 mb-5 font-mono text-sm">
          <div className="space-y-2 text-slate-700">
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Step 1</span>
              <span>base = 技術分 <span className="text-blue-600">×0.6</span> + 情緒分 <span className="text-purple-600">×0.4</span></span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Step 2</span>
              <span>綜合分 = base × <span className="text-indigo-600">SMC乘數</span></span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-slate-400">Step 3</span>
              <span>下降趨勢時推薦等級封頂「觀察」</span>
            </div>
          </div>
        </div>

        {/* 技術分拆解 */}
        <h3 className="text-sm font-semibold text-slate-700 mb-3">技術分（0–100）= 五個指標加權</h3>
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
                { name: "MACD",   w: "30%", high: "MACD > Signal（金叉）且 MACD < 0（底部反彈）", low: "MACD < Signal（死叉）" },
                { name: "RSI",    w: "25%", high: "RSI < 35（超賣區）", low: "RSI > 65（超買區）" },
                { name: "均線",   w: "25%", high: "收盤 > MA5 > MA20 > MA60（多頭排列）", low: "收盤 < MA5 < MA20 < MA60（空頭排列）" },
                { name: "布林通道", w:"10%", high: "收盤接近下軌（超賣）", low: "收盤超過上軌（超買）" },
                { name: "成交量", w: "10%", high: "成交量 ≥ 1.5x 均量（放量）", low: "成交量 < 0.7x 均量（縮量）" },
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

        {/* SMC 乘數 */}
        <h3 className="text-sm font-semibold text-slate-700 mb-3">SMC 乘數（最後一道過濾）</h3>
        <div className="grid grid-cols-4 gap-2 mb-4">
          {[
            { trend: "上升趨勢", mult: "×1.10", color: "bg-green-50 border-green-200", tc: "text-green-700", desc: "順勢加分" },
            { trend: "盤整",     mult: "×0.90", color: "bg-yellow-50 border-yellow-200", tc: "text-yellow-700", desc: "方向不明扣分" },
            { trend: "下降趨勢", mult: "×0.70", color: "bg-red-50 border-red-200", tc: "text-red-600", desc: "逆勢重扣" },
            { trend: "未知",     mult: "×0.95", color: "bg-slate-50 border-slate-200", tc: "text-slate-500", desc: "資料不足" },
          ].map(s => (
            <div key={s.trend} className={`rounded-xl border p-3 text-center ${s.color}`}>
              <div className={`text-lg font-bold ${s.tc}`}>{s.mult}</div>
              <div className={`text-xs font-semibold mt-1 ${s.tc}`}>{s.trend}</div>
              <div className="text-xs text-slate-400 mt-0.5">{s.desc}</div>
            </div>
          ))}
        </div>
        <Callout type="warning" text="下降趨勢即使最終分數算出來 ≥65，推薦等級也會被強制封頂為「觀察」，不會出現「下降趨勢卻推薦」的矛盾。" />
      </Section>

      {/* ── 3. 推薦等級說明 ── */}
      <Section title="推薦等級 — 怎麼看分數" icon="🏷">
        <div className="space-y-3">
          {[
            { level: "🟢 強力推薦", range: "≥ 75 分", color: "border-green-200 bg-green-50",
              tc: "text-green-700", action: "可考慮買入",
              cond: "多項指標同時發動，且 SMC 為上升趨勢。這是最理想的進場條件。",
              do_: "進個股頁確認 OB/支撐位 → 參考「量化建議買入價」進場" },
            { level: "🔵 推薦", range: "65–75 分", color: "border-blue-200 bg-blue-50",
              tc: "text-blue-700", action: "觀察等拉回",
              cond: "條件不錯，但可能已有一段漲幅。等價格拉回到支撐再進。",
              do_: "設置價格提醒，等回到量化建議買入價再動" },
            { level: "🟡 觀察", range: "55–65 分", color: "border-yellow-200 bg-yellow-50",
              tc: "text-yellow-700", action: "加入追蹤，不急著買",
              cond: "有機會但指標尚未齊備，或 SMC 仍在盤整。",
              do_: "繼續觀察，等分數提升到推薦再說" },
            { level: "⚪ 不推薦", range: "< 55 分", color: "border-slate-200 bg-slate-50",
              tc: "text-slate-500", action: "不買，有倉位要評估",
              cond: "條件差，多項指標偏弱，或 SMC 下降趨勢導致分數被重壓。",
              do_: "若有持倉且已虧損，評估是否繼續持有；若無持倉，等待" },
          ].map(r => (
            <div key={r.level} className={`rounded-xl border p-4 ${r.color}`}>
              <div className="flex items-start justify-between mb-2">
                <div>
                  <span className={`font-bold text-sm ${r.tc}`}>{r.level}</span>
                  <span className="ml-2 text-xs bg-white/60 px-2 py-0.5 rounded font-mono text-slate-500">{r.range}</span>
                </div>
                <span className={`text-xs font-semibold px-2 py-1 rounded-lg bg-white/60 ${r.tc}`}>{r.action}</span>
              </div>
              <p className="text-xs text-slate-600 mb-1">{r.cond}</p>
              <p className="text-xs text-slate-500">› {r.do_}</p>
            </div>
          ))}
        </div>
      </Section>

      {/* ── 4. 量化建議欄位說明 ── */}
      <Section title="量化建議欄位說明" icon="📐">
        <p className="text-slate-600 mb-4 leading-relaxed">
          股票清單右側的「量化建議」欄，由系統根據技術指標自動計算，提供參考進場區間，
          <strong className="text-slate-800">不是「立刻以此價買入」，而是「回調到此價可以考慮」的目標區</strong>。
        </p>
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-3">
            {[
              { label: "買", color: "text-indigo-600", title: "建議買入價",
                desc: "= max(MA20, BB下軌)，是近期支撐水平。若當前股價已低於此值，代表現在就在買入區。" },
              { label: "停", color: "text-red-500",    title: "建議停損價",
                desc: "= 買入價 × 0.93，即 -7% 停損。進場後若跌破此價，無條件出場。" },
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
                desc: "= 買入價 × 1.15，即 +15% 停利。這是最小目標，若趨勢強可以追蹤停損讓利潤繼續跑。" },
              { label: "R:R", color: "text-slate-600", title: "風報比",
                desc: "= 潛在獲利 ÷ 潛在虧損。系統預設 2.1x（賺 2.1 塊 vs 虧 1 塊）。R:R < 1.5 的交易要謹慎。" },
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
        <Callout type="warning" text="量化建議是靜態計算的估算值，每次跑完分析會更新。高波動標的（TSLA、SMCI、ALAB 等）實際波動幅度可能遠大於這個範圍。" />
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
                "找「強力推薦 + 上升趨勢」的組合（最理想）",
                "看量化建議欄：當前價是否接近「買入建議價」",
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
              ],
            },
            {
              step: "4", color: "bg-green-500", title: "執行買入（確認後）",
              items: [
                "進「投資組合」頁 → 點「買入」",
                "以量化建議的「買入價」為基準，可以分批（先買一半）",
                "買入後系統會自動計算停損 (-7%) 和停利 (+15%) 並顯示在持倉表",
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
              "量化建議欄：每支股票的建議買 / 停 / 目標 / R:R",
              "新增追蹤按鈕（右上角）、移除按鈕（每行右側）",
            ]},
            { page: "個股頁 /stocks/[ticker]", icon: "📈", points: [
              "K線圖含 SMC 疊加：OB 線（綠/紅虛線）、FVG 線、POC、價值區",
              "走勢機率：↑XX% ↓XX%，綜合 SMC 結構 + Volume Profile 計算",
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
              ["停利", "15%"],
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
                desc="LH+LL：每個高點和低點都比前一個低。不做多，等反轉確認。" />
              <ConceptRow tag="盤整" tagColor="bg-yellow-100 text-yellow-700"
                desc="在前期高低點區間內震盪。等待方向突破後再進場。" />
              <ConceptRow tag="BOS" tagColor="bg-blue-100 text-blue-700"
                desc="突破結構（Break of Structure）：突破前高/前低，趨勢延續的確認訊號。" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">訂單塊 (Order Block)</h3>
            <div className="space-y-2">
              <ConceptRow tag="多頭 OB 🟢" tagColor="bg-green-100 text-green-700"
                desc="大漲前的最後一根陰棒區域。回測到此區域是做多機會。圖表上的綠色虛線。" />
              <ConceptRow tag="空頭 OB 🔴" tagColor="bg-red-100 text-red-700"
                desc="大跌前的最後一根陽棒區域。反彈到此區域是壓力。圖表上的紅色虛線。" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">Fair Value Gap (FVG)</h3>
            <div className="space-y-2">
              <ConceptRow tag="多頭 FVG" tagColor="bg-indigo-100 text-indigo-700"
                desc="快速上漲留下的缺口，市場高機率回來補。是做多支撐區。" />
              <ConceptRow tag="空頭 FVG" tagColor="bg-orange-100 text-orange-700"
                desc="快速下跌留下的缺口，反彈到此有壓力。" />
            </div>
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-2">量能分佈 (Volume Profile)</h3>
            <div className="space-y-2">
              <ConceptRow tag="POC" tagColor="bg-amber-100 text-amber-700"
                desc="成交量最大的價格（Point of Control）。偏離 POC 越遠越容易被吸引回來。圖表上的黃色實線。" />
              <ConceptRow tag="Value Area" tagColor="bg-indigo-100 text-indigo-700"
                desc="70% 成交量集中的區間。突破 VA High 是強訊號；跌破 VA Low 是弱訊號。圖表上的紫色虛線。" />
            </div>
          </div>
        </div>
        <div className="mt-4 bg-amber-50 border border-amber-100 rounded-xl p-4">
          <p className="text-sm font-semibold text-amber-700 mb-1">⚡ 最強進場條件（Confluence Zone）</p>
          <p className="text-sm text-amber-600">
            OB + FVG + POC 在同一個價格區域重疊 → 支撐/壓力力道最強，是最理想的進場點。
          </p>
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
