import sys, json, urllib.request
from datetime import datetime

symbol = sys.argv[1]

# Determine exchange: TPEx for some, TWSE for others
tpex_tickers = {'8299'}  # TPEx stocks

if symbol in tpex_tickers:
    # TPEx API
    date_str = datetime.now().strftime("%Y/%m/%d")
    url = f"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes?l=zh-tw&d={date_str}&se=EW"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    for item in data:
        if item.get('SecuritiesCompanyCode') == symbol:
            quote = {
                'symbol': symbol,
                'price': float(item.get('Close', '0').replace(',', '')),
                'changePct': float(item.get('Change', '0').replace('+', '').replace(',', '')) / float(item.get('Close', '1').replace(',', '')) * 100,
                'volume': int(item.get('TradingShares', '0').replace(',', '')),
                'marketCap': None,
                'pe': None,
                'eps': None
            }
            print(json.dumps(quote, ensure_ascii=False))
            sys.exit(0)
    # Not found, fallback to TWSE
else:
    # TWSE API
    date_str = datetime.now().strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={symbol}"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    if data.get('data'):
        last = data['data'][-1]
        fields = data['fields']
        info = dict(zip(fields, last))
        close = float(info.get('收盤價', '0').replace(',', ''))
        diff = info.get('漲跌價差', '0').replace('+', '').replace(',', '')
        try:
            change_val = float(diff)
        except:
            change_val = 0.0
        quote = {
            'symbol': symbol,
            'price': close,
            'changePct': (change_val / close * 100) if close > 0 else 0,
            'volume': int(info.get('成交股數', '0').replace(',', '')),
            'marketCap': None,
            'pe': None,
            'eps': None
        }
        print(json.dumps(quote, ensure_ascii=False))
        sys.exit(0)

# Fallback: empty data
print(json.dumps({'symbol': symbol, 'price': 0, 'changePct': 0, 'volume': 0, 'marketCap': None, 'pe': None, 'eps': None}, ensure_ascii=False))