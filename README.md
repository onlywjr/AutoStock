# AutoStock 股票儀表板

台股每日收盤自動生成的股票儀表板（GitHub Pages 可直接開啟 `index.html`）。

## 架構

```
AutoStock/
├── index.html                  ← 首頁（卡片式，列出所有個股）
├── <代號>.html                 ← 各股專屬儀表板（1434 / 2327 / 2330 / 6139 / 6213 / 8299）
│
├── fetch_stock.py             ← 資料層：抓 TWSE / TPEx 收盤 + 近 5 日歷史（含公司名映射）
├── generate_all.py            ← 生成層：產出 .html / index.html / data/*.json
├── auto_update.py             ← 排程入口：generate_all + git commit & push
│
├── ticker_company.json       ← 公司名稱 / 產業 / 簡介 / 投資重點（唯一人工維護的檔案）
├── templates/
│   ├── dashboard_template.html
│   └── index_template.html
└── data/                     ← 每次抓取的 JSON 快取（抓取失敗時供 fallback 重繪）
```

## 每日流程（cron）

排程每天 16:00 執行 `auto_update.py`：
1. `generate_all.py` 抓六檔股票最新收盤並重繪所有頁面；
2. 若有任何檔案變更，自動 `git commit` + `git push origin master`；
3. 休市日資料全同時自動跳過 commit。

## 加入新股票

1. 在 `ticker_company.json` 加一個代號（name / industry / desc / catalysts）；
2. 在 `generate_all.py` 的 `TICKERS` 陣列加入代號；
3. 若該股是「上櫃」，在 `fetch_stock.py` 的 `TPEX_TICKERS` 加入。

## 手動執行

```bash
cd C:/My_Project/Hermes/AutoStock
python generate_all.py        # 只產頁面，不 push
python auto_update.py         # 產頁面 + push（等同排程）
```

## 資料來源與限制

**可用（實際驗證過）：**
- **TWSE `STOCK_DAY`**：收盤日K。`date=YYYYMM01` 可取整月資料 → 12 次呼叫取得一年歷史，衍生出 52 週高低、MA5/20/60、1/3/6 個月與 YTD 漲跌、30 日年化波動率、20 日均量
- **TPEx `tpex_mainboard_daily_close_quotes`**：上櫃股**最新一日**收盤（含開高收低量額）；對任意日期參數都回傳最新資料，無歷史

**已失效（回 404，勿使用）：**
- TWSE `STOCK_hour`（分時）、`STOCK_MAR`、`EPB`、`TWII` 等 exchangeReport 端點
- TWSE openapi.twse.com.tw 全部端點（EPS/PER/股利/大盤快照）
- TWSE `listDaily*` / `center/day/*.json` 週列表
- TPEx 其他 openapi（realtime、opening、traded_volume）

**因此 8299（上櫃）無 52 週區間與技術指標，頁面顯示「—」屬正常。**
