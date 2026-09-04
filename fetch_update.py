import os, json, urllib.request, datetime, sys, glob

def fetch_yahoo(ticker):
    url = f'https://query1.finance.yahoo.com/v7/finance/quote?symbols={ticker}.TW'
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
        result = data['quoteResponse']['result'][0]
        price = result.get('regularMarketPrice')
        change = result.get('regularMarketChangePercent')
        return price, change
    except Exception as e:
        print(f'[DEBUG] Yahoo fetch failed for {ticker}: {e}', file=sys.stderr)
        return None, None

def fetch_twse(ticker):
    # Use today's date in YYYYMMDD format, fallback to previous day if needed
    today = datetime.datetime.now()
    for delta in range(0, 3):
        date_str = (today - datetime.timedelta(days=delta)).strftime('%Y%m%d')
        url = f'https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={ticker}'
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                data = json.load(resp)
            if data.get('stat') != 'OK':
                continue
            # last entry is most recent trading day
            last = data['data'][-1]
            fields = data['fields']
            info = dict(zip(fields, last))
            price = float(info['收盤價'].replace(',', '')) if info['收盤價'] not in ('--', '') else None
            # change percent not directly provided; compute from previous close if possible
            prev = float(info['開盤價'].replace(',', '')) if info['開盤價'] not in ('--', '') else None
            change = None
            if price is not None and prev is not None and prev != 0:
                change = (price - prev) / prev * 100
            return price, change
        except Exception as e:
            print(f'[DEBUG] TWSE fetch error for {ticker} on {date_str}: {e}', file=sys.stderr)
    return None, None

def generate_html(ticker, price, change):
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    price_str = f"{price:.2f}" if price is not None else 'N/A'
    change_str = f"{change:.2f}%" if change is not None else 'N/A'
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>{ticker} 股票儀表板</title>
</head>
<body>
<h1>{ticker} 股票儀表板</h1>
<p>更新時間：{now}</p>
<p>收盤價：{price_str} NTD</p>
<p>漲跌幅：{change_str}</p>
</body>
</html>'''
    return html

def main():
    repo_dir = r'C:/My_Project/Hermes/[工作區]/AutoStock'
    os.chdir(repo_dir)
    html_files = [f for f in os.listdir('.') if f.endswith('.html') and f.lower()!='index.html']
    tickers = [os.path.splitext(f)[0] for f in html_files]
    if not tickers:
        tickers = ['8299','1434','6213','6139']
    for t in tickers:
        price, change = fetch_yahoo(t)
        if price is None:
            price, change = fetch_twse(t)
        html = generate_html(t, price, change)
        with open(f'{t}.html','w',encoding='utf-8') as f:
            f.write(html)
        print(f'[DEBUG] Updated {t}.html with price={price} change={change}')
    # update index.html
    index_path = 'index.html'
    links = '\n'.join([f'<li><a href="{t}.html">{t}.html</a></li>' for t in tickers])
    index_content = f'''<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><title>AutoStock Dashboard Index</title></head>
<body>
<h1>股票儀表板索引</h1>
<ul>
{links}
</ul>
</body></html>'''
    with open(index_path,'w',encoding='utf-8') as f:
        f.write(index_content)
    print('[DEBUG] Updated index.html')

if __name__ == '__main__':
    main()
