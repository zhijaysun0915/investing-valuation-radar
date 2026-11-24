# 📊 股票模型參考價 & 分析師預估價即時雷達 (Stock Valuation Radar)

[![GitHub Pages Deployment](https://img.shields.io/badge/線上_Live_Demo-GitHub_Pages-10b981?style=for-the-badge&logo=github)](https://zhijaysun0915.github.io/investing-valuation-radar/)
[![Version](https://img.shields.io/badge/版本-v2.14.0-8b5cf6?style=for-the-badge&logo=git)](https://github.com/zhijaysun0915/investing-valuation-radar/releases)
[![Issues](https://img.shields.io/badge/Issue_反饋-GitHub_Issues-f59e0b?style=for-the-badge&logo=github)](https://github.com/zhijaysun0915/investing-valuation-radar/issues)
[![Releases](https://img.shields.io/badge/Releases-GitHub_Releases-8b5cf6?style=for-the-badge&logo=github)](https://github.com/zhijaysun0915/investing-valuation-radar/releases)
[![GitHub Repository](https://img.shields.io/badge/GitHub_Repo-zhijaysun0915%2Finvesting--valuation--radar-181717?style=for-the-badge&logo=github)](https://github.com/zhijaysun0915/investing-valuation-radar)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

專為台股（TWSE / TPEX）與美股（NASDAQ / NYSE）研究設計的 **學術 5 模型參考價與外資分析師共識預估價 (Analyst Price Target) 即時查詢雷達**。

使用者只需在左側輸入股票代碼，右側即刻並列展示**最新成交價、學術多模型參考價（含折溢價百分比與 5 套期刊子模型拆解）、會計品質評分、外資分析師 12 個月平均目標價、預估高低區間、買進／賣出評級分布與各大投行券商評級明細**。

---

## 🚀 立即線上使用 (Live App)

👉 **線上免安裝直接看**：[https://zhijaysun0915.github.io/investing-valuation-radar/](https://zhijaysun0915.github.io/investing-valuation-radar/)

---

## 📸 介面與功能展示

```
+----------------------------------------------------------------------------------------------------+
|  [輸入代碼 2330 / 2327 / NVDA]  |  [右側雙核心看板]                                                |
|  - 批次輸入代碼                |  +------------------------------+  +-----------------------------+ |
|  - 熱門標的一鍵快選            |  | 💎 學術多模型參考價          |  | 🎯 分析師 12M 預估目標價    | |
|  - 已追蹤清單與 localStorage   |  | 5 套期刊模型拆解＋品質評分   |  | 外資共識目標價與評級分布    | |
|                                |  +------------------------------+  +-----------------------------+ |
|                                |  - 股價位階尺規 (現價 vs 模型參考價 vs 目標價)                    |
|                                |  - 外資機構明細表 (JPMorgan、Morgan Stanley、Nomura、Citi 等)     |
+----------------------------------------------------------------------------------------------------+
```

---

## 🌟 核心特色

1. **左輸右顯即時聯動（Split-Pane Dashboard）**
   - **左側輸入與管理**：輸入單一或多筆代碼（支援逗號、空白或換行分隔），提供台股/美股代碼自動識別、熱門股晶片快選與本地查詢歷史清單。
   - **右側重點估值看板**：並排呈現「學術 5 模型參考價（含 5 大子模型細項與 Piotroski/Sloan 品質評分）」與「外資分析師 12 個月共識預估價」，快速對比折溢價幅度。

2. **零後端依賴的雙引擎架構（免 API Key 即開即用）**
   - **引擎 A：每日自動化公開財報管線 ＋ 即時連線解析**：
     - 透過 GitHub Actions 每日抓取台灣證交所／櫃買中心官方本益比、股價淨值比與 Yahoo Finance 公開財報，執行 5 套同儕審查學術估值模型（Ohlson-DHS 剩餘收益、Ohlson-Juettner 再投資盈餘、Liu-Nissim-Thomas 細分產業調和本益比、Bhojraj-Lee 基本面迴歸、Lie-Lie 產業 EV/EBITDA），並附可重現的 2023–2026 樣本外回測腳本 `scripts/backtest_valuation.py`。
     - 單股即時搜尋亦可解析公開個股網頁之最新成交價、52 週高低點、外資分析師平均目標價與各大外資評級明細表。
   - **引擎 B：選填 Gemini AI + Google Search Grounding**：
     - 使用者可選擇填入個人的 Gemini API Key（僅留存於瀏覽器 localStorage，絕不上傳）。
     - 透過 Google Search 檢索最新公開財報摘要與法人研究參考區間作為輔助補充。

3. **⚡ 瀏覽器直連盤中即時報價引擎 ＋ 漲跌停支援 ＋ 離線備援**
   - **主引擎（瀏覽器直連，免 API Key）**：
     - 開啟網頁、點擊「🔄 同步最新盤中價」、切回分頁或開啟「⏱️ 自動輪詢（每 30 秒）」時，瀏覽器直接批次連線公開即時行情介面（支援 CORS，約 0.4 秒同步 125+ 檔台股／美股／港股），不再受限於 GitHub Actions 排程延遲。
     - 完整支援台股**漲停 (`▲ 漲停`)／跌停 (`▼ 跌停`)**鎖死狀態與即時動態重算五大區間報酬、模型折價空間、外資目標空間與總市值。
   - **備援與市值基準（GitHub Actions `data/quotes.json`）**：
     - 透過 `.github/workflows/update-quotes.yml` 與 `scripts/fetch_tw_quotes.py`（已修復 TWSE MIS 漲跌停市價單 `0.0000` 解析漏洞並內建自動備援）維護發行股數、市值百大排名與日股報價；若直連暫時受阻則自動降級並以琥珀色誠實標示備援時間。

4. **📊 個股擴充欄位：即時股價與 5 大區間表現 (近1日、近1週、近1月、近1季、近1年)**
   - **橫向比較表一鍵擴充**：點擊「📊 擴充表現欄位」即可於總覽表展開 1D / 1W / 1M / 1Q / 1Y 報酬率欄位，支援點擊表頭排序。
   - **獨立折疊明細卡**：每檔股票皆可單獨點擊展開，即時查看盤中振幅、昨收價、52週位階與各週期漲跌幅標籤（遵循台股標準：▲ 紅漲 ▼ 綠跌）。
   - **右側詳細檢視全面整合**：在 Split View 中提供專屬「即時盤況與多週期個股表現」儀表板區塊。
   - **自訂校準支援**：手動校準彈窗內建五大週期報酬率輸入欄位，方便隨時微調與自訂。

4. **🌐 GitHub Issue 與 Release 深度社群整合**
   - **GitHub Releases**：版本歷程、功能變更與發行標記全面公開於 [GitHub Releases](https://github.com/zhijaysun0915/investing-valuation-radar/releases)。
   - **GitHub Issues 反饋中心**：提供標準化 Issue 範本，使用者可前往 [GitHub Issues](https://github.com/zhijaysun0915/investing-valuation-radar/issues) 提交估值校準建議、Bug 回報與新功能提案。

5. **四大檢視視角切換（含 Top 100 雙向排行榜與分頁）**
   - **🏆 估值潛力 Top 100 榜單 (Leaderboard with Pagination)**：
     - **💎 公允價值折價榜 Top 100**：按 `(公允價 - 現價) / 現價` 排序，發掘潛在折價空間最大的價值型標的。
     - **🎯 分析師目標價看漲榜 Top 100**：按 `(分析師共識目標價 - 現價) / 現價` 排序，掌握法人外資看漲潛力最高的成長型標的。
     - **🌐 社群查過標的池 (Crowdsourced Pool)**：使用者每次查詢的新股票均自動併入標的庫，支援熱度統計、一鍵加入雷達與 JSON 格式匯出/匯入。
     - **完整分頁控制 (Pagination)**：支援自選每頁 20 / 50 / 100 筆顯示、上一頁 / 下一頁與數字頁碼切換。
   - **左右即時查詢台 (Split View)**：專注單一股票的深入估值、估值尺規與外資評級明細。
   - **多股雷達卡片牆 (Cards Grid)**：快速瀏覽所有自選股的公允價與目標價雷達卡片。
   - **總覽比較表 (Table View)**：密集表格排版，支援按代碼、股價、公允價空間、分析師目標價、P/E、P/B 進行升降序排序。

4. **資料匯出與自訂校準**
   - 一鍵匯出包含所有指標的繁體中文 CSV 報表。
   - 支援「社群標的池 JSON 匯出與匯入」，跨裝置分享與備份被查詢過的股票庫。
   - 支援「手動校準」彈窗，可微調各股的公允價格、估值區間或筆記，資料自動儲存於瀏覽器 `localStorage`。

---

## 🛠️ 技術架構與本地開發指南 (Developer Setup)

本專案採用 **純前端單檔架構（Zero-dependency Single Page Application）**，開發與維護極為輕量，任何開發者只要 `git clone` 即可在本地進行修改與二次開發。

### 1. 複製專案 (Clone Repository)

```bash
git clone https://github.com/zhijaysun0915/investing-valuation-radar.git
cd investing-valuation-radar
```

### 2. 專案目錄結構

```text
investing-valuation-radar/
├── index.html       # 核心單檔應用程式（包含 UI、Tailwind CDN、Parser 與爬蟲邏輯）
├── README.md        # 專案詳細說明、架構手冊與免責聲明
└── .git/            # Git 版本控制
```

### 3. 本地啟動預覽 (Local Development)

無需安裝複雜的 Node.js 構建套件，使用任何靜態 HTTP 伺服器即可啟動：

```bash
# 方法 1: 使用 Python 3
python3 -m http.server 8080

# 方法 2: 使用 Node.js 的 npx serve
npx serve .

# 方法 3: 直接用瀏覽器開啟 index.html
open index.html
```

瀏覽器打開 `http://localhost:8080` 即可預覽。

---

## 🧩 核心邏輯與擴充開發指南 (How It Works)

想要接手或擴充功能的開發者，主要程式邏輯皆集中於 [index.html](file:///Users/jaysun/Downloads/investing-valuation-radar/index.html) 的 `<script>` 區塊：

### 1. 股票代碼映射與核心標的池 (`KNOWN_SLUGS` / `TAIWAN_CORE_UNIVERSE`)
- 用於台股與全球指標股代碼與 URL slug（例如 `2330` ➔ `taiwan-semicon`、`2327` ➔ `yageo-corp`、`NVDA` ➔ `nvidia-corp`）的快速對應，並於開啟網頁時自動同步每日最新 `data/fundamentals.json` 與盤中即時 `data/quotes.json`。
- **擴充方式**：若要預設支援新的熱門股票，可在此字典新增對應的 `slug`、`name` 與 `market`。

### 2. 全球市場識別與候選股防撞評分演算法 (`resolveInvestingSlug` & `parseSearchQueryItems`)
- **跨國代碼防撞問題**：例如輸入 `3374` 可能同時命中台灣櫃買「精材 (3374)」與日本東京「Naigai Tec Corp (3374)」；輸入 `6488` 可能命中台灣櫃買「環球晶 (6488)」與日本東京「Yoshitake Inc (6488)」。
- **解決方案**：
  1. **輸入智慧剖析 (`parseSearchQueryItems`)**：支援 `3374 精材`、`6488 環球晶`（代碼+名稱提示）、純中文名稱（`精材`）、純代碼（`2330`）或多筆批次輸入。
  2. **交易所標籤識別**：自公開搜尋結果中精準識別 `TWSE / TPEX / TSE (東京) / NASDAQ / NYSE / HKEX`。
  3. **動態加權計分機制 (`scoreCandidate`)**：
     - 代碼完全相符：+100 分
     - 中文名稱/關鍵字相符：+150 分
     - 目標市場偏好（台股/美股/日股/港股）：+120 分
     - 四碼純數字啟發式優先權（自動模式下台股 +45 分，美股英文字母代碼 +45 分）
     - 保證在任何搜尋情境下均能精確匹配到使用者所指的目標標的。

### 3. 即時爬蟲與資料解析器 (`parseInvestingMarkdown`)
- 核心正則表達式解析器，從公開網頁 Markdown 文本擷取：
  - `成交價`、`昨收`、`當日高低`、`52週高低`
  - `12個月平均目標價`、`預估最高/最低價`、`分析師評級人數`
  - `分析師評級歷史明細表`（包含投行券商名稱、目標價、評級日期）
  - `同業市盈率 (P/E)`、`市帳率 (P/B)`

### 4. 學術 5 模型參考價推算邏輯 (`scripts/update_fundamentals.py`)
- 透過每日自動化管線由公開財報計算（完全不使用該股現價、分析師目標價或寫死快照）：
  1. **M1 剩餘收益模型 (RIM)** — *Ohlson (1995 CAR)* / *Dechow, Hutton & Sloan (1999 JAE, ω=0.62)* / *Gebhardt, Lee & Swaminathan (2001 JAR)*
  2. **M2 再投資一致盈餘折現 (OJ-DCF)** — *Ohlson & Juettner-Nauroth (2005 RAST)* / *Fuller & Hsia (1984 FAJ)* / *Damodaran (2012)*
  3. **M3 細分產業調和本益比 (Sub-Industry Harmonic P/E)** — *Liu, Nissim & Thomas (2002 JAR)*（Leave-One-Out）
  4. **M4 基本面合理倍數迴歸 (Warranted Multiples)** — *Bhojraj & Lee (2002 JAR)* / *Wilcox (1984 FAJ)*（Leave-One-Out Ridge）
  5. **M5 細分產業調和 EV/EBITDA** — *Lie & Lie (2002 FAJ)*（非金融業適用）
- 附帶 *Piotroski (2000 JAR)* / *Sloan (1996 TAR)* / *Novy-Marx (2013 JFE)* 5 分制會計品質評分、*Damodaran (2012 Ch.22)* 景氣循環常態化，以及可重現之 2023–2026 樣本外回測腳本 `scripts/backtest_valuation.py`。

### 5. JavaScript 語法檢驗指令
在提交或發布修改前，可執行以下指令進行語法安全檢查：

```bash
node -e '
const fs = require("fs");
const html = fs.readFileSync("index.html", "utf8");
const scriptMatches = [...html.matchAll(/<script[\s\S]*?>([\s\S]*?)<\/script>/gi)];
for (let i = 0; i < scriptMatches.length; i++) {
  if (scriptMatches[i][1].trim()) new Function(scriptMatches[i][1]);
}
console.log("語法檢驗通過，共檢查了", scriptMatches.length, "個腳本區塊");
'
```

---

## ⚖️ 免責聲明與法律聲明 (Disclaimer & Terms)

> [!IMPORTANT]
> **請在使用或開發本專案前詳細閱讀以下聲明：**

1. **僅供學術研究與個人參考用途**：
   - 本工具為開源技術研究專案，旨在展示前端資料解析、無伺服器自動化資料管線與公開財務模型視覺化技術。
   - 本應用程式所顯示的所有數據（包括但不限於最新股價、模型參考價、分析師預估目標價、本益比、市帳率等）**均不構成任何形式的投資建議、買賣推薦、招攬或財務顧問意見**。
2. **資料來源與延遲**：
   - 報價與公開財報數據係自動擷取自台灣證交所、櫃買中心、Yahoo Finance 及公開財經網頁。各市場報價可能存在 15~20 分鐘以上的法定延遲或未及時同步，實際交易價格請務必自行向合格券商或官方交易所確認。
   - 開發者與專案貢獻者不對資料的即時性、準確性、完整性或連續性提供任何明示或暗示的擔保。
3. **投資風險警示**：
   - 股票、期貨或任何金融工具之交易均涉及高度市場風險，可能導致部分或全部本金損失。投資人應獨立評估自身財務狀況、風險承受能力，並在必要時諮詢合格之註冊證券投資顧問。使用者因信賴或使用本工具之數據所做出之任何投資決策，概由使用者自行承擔全部風險與盈虧。
4. **商標與智慧財產權**：
   - 本專案所提及之第三方公開財經平台與交易所名稱及商標均歸其各自權利人所有。本開源專案為獨立學術研究工具，與任何第三方財經網站或商業估值平台無任何官方附屬、贊助、授權或代言關係。

---

## 📄 開源授權 (License)

本專案採用 [MIT License](https://opensource.org/licenses/MIT) 授權釋出。歡迎自由 Fork、提交 Issue 或發起 Pull Request 共同改進！
