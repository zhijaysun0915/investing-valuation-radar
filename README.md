# 📊 Investing.com 股票公允價 & 分析師預估價即時雷達 (Investing Valuation Radar)

[![GitHub Pages Deployment](https://img.shields.io/badge/線上_Live_Demo-GitHub_Pages-10b981?style=for-the-badge&logo=github)](https://zhijaysun0915.github.io/investing-valuation-radar/)
[![Version](https://img.shields.io/badge/版本-v2.5.0-8b5cf6?style=for-the-badge&logo=git)](https://github.com/zhijaysun0915/investing-valuation-radar/releases)
[![Issues](https://img.shields.io/badge/Issue_反饋-GitHub_Issues-f59e0b?style=for-the-badge&logo=github)](https://github.com/zhijaysun0915/investing-valuation-radar/issues)
[![Releases](https://img.shields.io/badge/Releases-GitHub_Releases-8b5cf6?style=for-the-badge&logo=github)](https://github.com/zhijaysun0915/investing-valuation-radar/releases)
[![GitHub Repository](https://img.shields.io/badge/GitHub_Repo-zhijaysun0915%2Finvesting--valuation--radar-181717?style=for-the-badge&logo=github)](https://github.com/zhijaysun0915/investing-valuation-radar)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

專為台股（TWSE / TPEX）與美股（NASDAQ / NYSE）投資人設計的 **Investing.com 股票公允價 (Fair Value) 與外資分析師共識預估價 (Analyst Price Target) 即時查詢雷達**。

使用者只需在左側輸入股票代碼，右側即刻並列展示 Investing.com 的**最新成交價、模型公允價值（含折溢價百分比）、外資分析師 12 個月平均目標價、預估高低區間、買進／賣出評級分布與各大投行券商評級明細**。

---

## 🚀 立即線上使用 (Live App)

👉 **線上免安裝直接看**：[https://zhijaysun0915.github.io/investing-valuation-radar/](https://zhijaysun0915.github.io/investing-valuation-radar/)

---

## 📸 介面與功能展示

```
+----------------------------------------------------------------------------------------------------+
|  [輸入代碼 2330 / 2327 / NVDA]  |  [右側雙核心看板]                                                |
|  - 批次輸入代碼                |  +------------------------------+  +-----------------------------+ |
|  - 熱門標的一鍵快選            |  | 💎 公允價 (InvestingPro)     |  | 🎯 分析師 12M 預估目標價    | |
|  - 已追蹤清單與 localStorage   |  | NT$ 2,495.00 (+16.9% 折價)   |  | NT$ 3,409.80 (+59.7% 空間)  | |
|                                |  +------------------------------+  +-----------------------------+ |
|                                |  - 股價位階尺規 (現價 vs 公允價 vs 目標價)                        |
|                                |  - 外資機構明細表 (JPMorgan、Morgan Stanley、Nomura、Citi 等)     |
+----------------------------------------------------------------------------------------------------+
```

---

## 🌟 核心特色

1. **左輸右顯即時聯動（Split-Pane Dashboard）**
   - **左側輸入與管理**：輸入單一或多筆代碼（支援逗號、空白或換行分隔），提供台股/美股代碼自動識別、熱門股晶片快選與本地查詢歷史清單。
   - **右側重點估值看板**：並排呈現「InvestingPro 模型公允價」與「外資分析師 12 個月共識預估價」，快速對比折溢價幅度。

2. **零後端依賴的雙引擎架構（免 API Key 即開即用）**
   - **引擎 A：預設免金鑰即時連線（Live Jina Reader Proxy）**：
     - 利用支援 CORS 的瀏覽器渲染代理直接連線 `hk.investing.com`。
     - 即時解析個股頁面與 FAQ 結構化資料：即時價格、昨收、52 週高低價、分析師平均目標價、最高與最低預估價、買進/持有/賣出人數、各大外資評級明細表、同業本益比 (P/E) 與市帳率 (P/B)。
   - **引擎 B：選填 Gemini AI + Google Search Grounding**：
     - 使用者可選擇填入個人的 Gemini API Key（僅留存於瀏覽器 localStorage，絕不上傳）。
     - 自動呼叫 Google Search 檢索 `site:investing.com/pro` 快照，進一步增強付費牆背後的公允價值數值。

3. **📊 個股擴充欄位：即時股價與 5 大區間表現 (近1日、近1週、近1月、近1季、近1年)**
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

### 1. 股票代碼映射與已知快照字典 (`KNOWN_SLUGS`)
- 定義於代碼約 **490~530 行**。
- 用於台股代碼與 Investing.com URL slug（例如 `2330` ➔ `taiwan-semicon`、`2327` ➔ `yageo-corp`、`NVDA` ➔ `nvidia-corp`）的極速對應，並內建已驗證的 InvestingPro 公允價基底。
- **擴充方式**：若要預設支援新的熱門股票，可在此字典新增對應的 `slug`、`name` 與 `market`。

### 2. 全球市場識別與候選股防撞評分演算法 (`resolveInvestingSlug` & `parseSearchQueryItems`)
- 定義於代碼約 **950~1120 行**。
- **跨國代碼防撞問題**：例如輸入 `3374` 可能同時命中台灣櫃買「精材 (3374)」與日本東京「Naigai Tec Corp (3374)」；輸入 `6488` 可能命中台灣櫃買「環球晶 (6488)」與日本東京「Yoshitake Inc (6488)」。
- **解決方案**：
  1. **輸入智慧剖析 (`parseSearchQueryItems`)**：支援 `3374 精材`、`6488 環球晶`（代碼+名稱提示）、純中文名稱（`精材`）、純代碼（`2330`）或多筆批次輸入。
  2. **交易所標籤識別**：自 Investing.com 搜尋結果中精準過濾 `[3374 精材 股票 - 台北證券櫃檯買賣中心 equities]`，精確識別 `TWSE / TPEX / TSE (東京) / NASDAQ / NYSE / HKEX`。
  3. **動態加權計分機制 (`scoreCandidate`)**：
     - 代碼完全相符：+100 分
     - 中文名稱/關鍵字相符：+150 分
     - 目標市場偏好（台股/美股/日股/港股）：+120 分
     - 四碼純數字啟發式優先權（自動模式下台股 +45 分，美股英文字母代碼 +45 分）
     - 保證在任何搜尋情境下均能精確匹配到使用者所指的目標標的。

### 3. 即時爬蟲與資料解析器 (`parseInvestingMarkdown`)
- 定義於代碼約 **1120~1310 行**。
- 核心正則表達式解析器，從 Markdown 文本精準擷取：
  - `成交價`、`昨收`、`當日高低`、`52週高低`
  - `12個月平均目標價`、`預估最高/最低價`、`分析師評級人數`
  - `分析師評級歷史明細表`（包含投行券商名稱、目標價、評級日期）
  - `同業市盈率 (P/E)`、`市帳率 (P/B)`、`同業公允價上升空間`

### 4. 多模型公允價值推算邏輯
- 當個股因付費牆限制未直接顯示特定公允數值時，系統啟動同業估值矩陣：
  1. **同業公允價上升空間模型 (Peer Upside Benchmark)**
  2. **板塊公允價上升空間模型 (Sector Upside Benchmark)**
  3. **同業本益比乘數相對折溢價模型 (P/E Relative Multiple)**
  4. **外資保守目標錨定模型 (Conservative Analyst Anchor)**
- 綜合推算合理公允價與估值區間，並提供「開啟 Pro 公允價快照搜尋」按鈕直通 Google 原始快照。

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
   - 本工具為開源技術研究專案，旨在展示前端資料解析、無伺服器 API 串接與視覺化排版技術。
   - 本應用程式所顯示的所有數據（包括但不限於最新股價、公允價值、分析師預估目標價、本益比、市帳率等）**均不構成任何形式的投資建議、買賣推薦、招攬或財務顧問意見**。
2. **資料來源與延遲**：
   - 資料皆即時或依快照擷取自 [Investing.com](https://www.investing.com) 公開網頁及搜尋引擎索引快照。各市場報價可能存在 15~20 分鐘以上的法定延遲，且可能受第三方網路連線或目標網站版面調整影響。
   - 開發者與專案貢獻者不對資料的即時性、準確性、完整性或連續性提供任何明示或暗示的擔保。
3. **投資風險警示**：
   - 股票、期貨、被動元件或任何金融工具之交易均涉及高度市場風險，可能導致部分或全部本金損失。投資人應獨立評估自身財務狀況、風險承受能力，並在必要時諮詢合格之註冊證券投資顧問。使用者因信賴或使用本工具之數據所做出之任何投資決策，概由使用者自行承擔全部風險與盈虧。
4. **商標與智慧財產權**：
   - `Investing.com` 與 `InvestingPro` 為 Fusion Media Limited 之商標或註冊商標。本開源專案與該公司無任何官方附屬、贊助、授權或代言關係。

---

## 📄 開源授權 (License)

本專案採用 [MIT License](https://opensource.org/licenses/MIT) 授權釋出。歡迎自由 Fork、提交 Issue 或發起 Pull Request 共同改進！
