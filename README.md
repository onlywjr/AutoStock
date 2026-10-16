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

- 上市股（TWSE）：可取近 5 交易日歷史；
- 上櫃股（TPEx）：公開 API 只回傳最新收盤，走勢圖會顯示說明；
- 本機 SSL 憑證庫偶發異常，`fetch_stock.py` 已內建自動重試（CERT_NONE fallback）。
