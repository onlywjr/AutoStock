import yfinance as yf
import datetime
import os

tickers = [
    ("8299", "8299.TWO"),
    ("1434", "1434.TW"),
    ("2327", "2327.TW"),
    ("2330", "2330.TW"),
    ("6139", "6139.TW"),
    ("6213", "6213.TW"),
]

now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

data = {}
for ticker, symbol in tickers:
    try:
        t = yf.Ticker(symbol)
        info = t.info
        price = info.get("regularMarketPrice")
        change = info.get("regularMarketChangePercent", 0)
        volume = info.get("regularMarketVolume", info.get("volume", 0))
        if price is None:
            print(f"Warning: no price for {ticker} ({symbol})")
            price = 0
        data[ticker] = {
            "price": price,
            "change": change if change is not None else 0,
            "volume": volume if volume else 0,
        }
        print(f"Fetched {ticker}: price={price}, change={change}, volume={volume}")
    except Exception as e:
        print(f"Error fetching {ticker} ({symbol}): {e}")
        data[ticker] = {"price": 0, "change": 0, "volume": 0}

def write_dashboard(ticker, info):
    price = info["price"]
    change = info["change"]
    volume = info["volume"]
    price_str = f"{price:,.2f}" if price else "0.00"
    if change > 0:
        arrow, cls = "▲", "up"
    elif change < 0:
        arrow, cls = "▼", "down"
    else:
        arrow, cls = "—", "up"
    change_str = f"{arrow} {abs(change):.2f}%"
    vol_str = f"{volume:,}" if volume else "N/A"
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>{ticker} 股票儀表板</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem; background: #f8fafc; color: #1e293b; }}
  h1 {{ border-bottom: 2px solid #3b82f6; padding-bottom: 0.5rem; }}
  .price {{ font-size: 2rem; font-weight: bold; margin: 1rem 0; }}
  .up {{ color: #ef4444; }} .down {{ color: #22c55e; }}
  .meta {{ color: #64748b; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>📊 {ticker} 股票儀表板</h1>
<p class="meta">更新時間：{now}</p>
<p class="price">{price_str} NTD</p>
<p class="{cls}">{change_str}</p>
<p class="meta">成交量：{vol_str}</p>
</body>
</html>'''
    with open(f"{ticker}.html", "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Wrote {ticker}.html")

def write_index():
    lines = []
    for ticker, _ in tickers:
        info = data[ticker]
        price = info["price"]
        change = info["change"]
        price_str = f"{price:,.2f}" if price else "0.00"
        if change > 0:
            arrow = "▲"
        elif change < 0:
            arrow = "▼"
        else:
            arrow = "—"
        change_str = f"{arrow} {abs(change):.2f}%"
        lines.append(
            f'    <li><a href="{ticker}.html">{ticker}.html</a> — 收盤價：{price_str} NTD / 漲跌幅：{change_str} / 更新：{now}</li>'
        )
    links = "\n".join(lines)
    html = f'''<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><title>AutoStock Dashboard Index</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #f8fafc; color: #1e293b;">
  <h1 style="border-bottom: 2px solid #3b82f6; padding-bottom: 0.5rem;">📊 股票儀表板索引</h1>
  <p style="color: #64748b; margin-bottom: 1.5rem;">更新時間：{now}</p>
  <ul style="list-style: none; padding: 0;">
{links}
  </ul>
</body></html>'''
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Wrote index.html")

for ticker, _ in tickers:
    write_dashboard(ticker, data[ticker])
write_index()
print("Done refreshing dashboards.")
