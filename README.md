# 📊 Investing.com 股票公允價 & 分析師預估價即時雷達 (Investing Valuation Radar)

[![立即線上使用 Live Demo](https://img.shields.io/badge/🚀_立即線上查看_Live_App-GitHub_Pages-10b981?style=for-the-badge)](https://zhijaysun0915.github.io/investing-valuation-radar/)

輸入台股或美股股票代碼，**左邊輸入／點選股票，右邊立即顯示 Investing.com 最新股價、公允價 (Fair Value) 與外資分析師 12 個月共識預估價 (Analyst Price Target)**！

---

## 🌐 線上直接使用 (GitHub Pages)

👉 **[https://zhijaysun0915.github.io/investing-valuation-radar/](https://zhijaysun0915.github.io/investing-valuation-radar/)**

---

## ✨ 核心功能亮點

1. **左輸右顯直覺工作台（Split-Pane Dashboard）**
   - **左側面板**：支援單筆或批次輸入台股／美股代碼（如 `2330`, `2327`, `2454`, `2317`, `8299`, `NVDA`, `AAPL`），內建熱門股一鍵快選與已查詢清單。
   - **右側面板**：大字體並排呈現 **「公允價 (InvestingPro Fair Value)」** 與 **「分析師預估價 (Analyst Consensus Target)」**，計算潛在折溢價空間（%）與高低區間。
2. **免 API Key 即時連線 Investing.com**
   - 內建無伺服器跨網域連線引擎（`r.jina.ai` + `hk.investing.com`），無須安裝後端或填寫金鑰即可在瀏覽器直接抓取：
     - 最新成交價、昨收價、當日波動、52 週高低位階
     - 外資分析師 12 個月平均目標價、最高／最低預估價、買進／持有／賣出分析師人數
     - 各大外資券商（JPMorgan、Morgan Stanley、Nomura、Macquarie、Citi 等）最新目標價與評級明細表
     - 個股 vs 同業平均本益比 (P/E)、市帳率 (P/B)、同業公允價值上升空間 (%)
3. **三種檢視模式切換 & CSV 報表匯出**
   - 支援「**左右即時查詢台**」、「**多股雷達卡片牆**」、「**總覽比較表**」一鍵切換，並可匯出 CSV 報表或手動微調校準。
