## TWSE Fallback for Stock Data

During a session we discovered that Yahoo Finance API often returned **HTTP 429** or **Unauthorized** responses for Taiwanese tickers. A reliable alternative is the Taiwan Stock Exchange (TWSE) public JSON endpoint:
```
https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date=YYYYMMDD&stockNo=<ticker>
```
- Returns daily trading data in Chinese field names.
- The latest entry (last element of `data`) contains the most recent closing price (`收盤價`), price change (`漲跌價差`), and date (`日期`).
- No authentication required and works without rate limits.

**Guidance**: Use this fallback when Yahoo fails, inserting a 1‑second sleep before retrying, and compute the `date` parameter with `datetime.now().strftime('%Y%m%d')`.

The `stock-dashboard-data-fetch` skill now documents this fallback in its workflow and tags it for easy discovery.
