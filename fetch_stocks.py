import yfinance as yf
import datetime
import os
import sys



tickers = ['8299.tw', '1434.tw', '6213.tw', '6139.tw']
for ticker in tickers:
    try:
        data = yf.Ticker(ticker)
        info = data.info
        price = info.get('regularMarketPrice', 0)
        change = info.get('changePercent', 0)
        volume = info.get('volume', 0)
        last_trade = info.get('regularMarketTime', '2026-10-14 00:00')
        arrow = '▲' if change >= 0 else '▼'
        formatted_price = f'{price:,.0f}'
        update_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        # Write HTML
        os.makedirs('/c/My_Project/Hermes/[工作區]/AutoStock', exist_ok=True)
        html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>{ticker.replace('.tw', '')} 股票儀表板</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem; }}
h1 {{ border-bottom: 2px solid #3b82f6; padding-bottom: 0.5rem; }}
.price {{ font-size: 2rem; font-weight: bold; margin: 1rem 0; }}
.up {{ color: #22c55e; }} .down {{ color: #ef4444; }}
.meta {{ color: #64748b; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>{ticker.replace('.tw', '')} 股票儀表板</h1>
<p class="meta">更新時間：{update_time}</p>
<p class="price">{formatted_price}</p>
<p class="{arrow}">{arrow} {abs(change):.2f}%</p>
<p class="meta">成交量：{volume:,}</p>
</body>
</html>'''
        out_path = f'/c/My_Project/Hermes/[工作區]/AutoStock/{ticker.replace(".tw", "")}.html'
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'{ticker.replace(".tw", "")} {arrow} {change:.2f}% price {formatted_price}, volume {volume:,}, updated {update_time}')
    except Exception as e:
        print(f'Error fetching {ticker}: {e}')