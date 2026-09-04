---
name: autostock-daily-update
description: "每日自動更新 AutoStock 儀表板並推送到 GitHub。"
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [windows]
category: productivity
tags: ["stock","auto","daily"]
related_skills: ["push_stock_dashboard","stock-dashboard-data-fetch"]
---

# Autostock Daily Update (autostock-daily-update)

## Goal
自動執行以下流程，確保所有股票儀表板皆為最新資料，並同步到 GitHub:
1️⃣ 執行 `update_dashboards.py`（抓取最新股價、更新 HTML）。
2️⃣ 呼叫已存在的 `push_stock_dashboard` skill 完成 commit & push。

## Prerequisites
- 專案根目錄：`C:/My_Project/Hermes/[工作區]/AutoStock`
- 已安裝 Python 3.11（可直接執行 `python` 指令）。
- `push_stock_dashboard` skill 已在本專案內（見 `skills/productivity/push_stock_dashboard`）。
- `git` 已在環境路徑，可正常 push。

## Workflow (Shell script)
```bash
#!/usr/bin/env bash
# 1️⃣ 切到專案根目錄
cd "C:/My_Project/Hermes/[工作區]/AutoStock"

# 2️⃣ 更新儀表板（會自行抓取資料、寫入 *.html、更新 index.html）
python update_dashboards.py

# 3️⃣ 使用已存在的 skill 進行 commit & push
# Hermes CLI 會自動載入本目錄下的 skill
hermes skill run push_stock_dashboard
```

將此腳本保存為 `run_daily.sh`（已隨本 skill 一起提供），並確保執行權限 (`chmod +x run_daily.sh` 在 Bash 下) 即可。

## How to trigger manually
在 Hermes 聊天輸入：
```
hermes skill run autostock-daily-update
```
即可即時執行全部步驟。

---

## Cron job (optional)
若想每天自動在 07:00 執行，可建立以下 cronjob（Hermes 內建 `cronjob` 工具）：
```json
{
  "action": "create",
  "schedule": "0 7 * * *",
  "prompt": "執行 autostock-daily-update skill",
  "name": "autostock_daily_update",
  "repeat": null,
  "deliver": "origin"
}
```
此工作會在背景執行，完成後結果會自動回報到本聊天。

---

## Extensibility
- 若未來需要加入更多股票，只要在 `update_dashboards.py` 中的 `tickers` 陣列加入代號即可，skill 會自動涵蓋。
- 若要變更執行時間，只需要編輯 cronjob 的 `schedule` 欄位。

---

*此 skill 已放置於專案 `skills/productivity/autostock-daily-update` 目錄，包含說明檔與執行腳本，可直接使用。*