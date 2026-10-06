import sys, json, urllib.request, ssl
from datetime import datetime
symbol = sys.argv[1]
ctx = ssl._create_unverified_context()
tpex_tickers = {'8299'}
if symbol in tpex_tickers:
    date_str = datetime.now().strftime("%Y/%m/%d")
    url = f"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes?l=zh-tw&d={date_str}&se=EW"
else:
    date_str = datetime.now().strftime("%Y%m%d")
    url = f"https://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={date_str}&stockNo={symbol}"
req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
try:
    with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
        data = json.load(resp)
except Exception as e:
    print(json.dumps({'error': str(e)}))
    sys.exit(1)

if symbol in tpex_tickers:
    for item in data:
        if item.get('SecuritiesCompanyCode') == symbol:
            quote = {
                'symbol': symbol,
                'price': float(item.get('Close','0').replace(',','')),
                'changePct': float(item.get('Change','0').replace('+','').replace(',','')) / float(item.get('Close','1').replace(',','')) *100,
                'volume': int(item.get('TradingShares','0').replace(',','')),
            }
            print(json.dumps(quote, ensure_ascii=False))
            sys.exit(0)
    # fallback
else:
    if data.get('data'):
        last = data['data'][-1]
        fields = data['fields']
        info = dict(zip(fields, last))
        close = float(info.get('收盤價','0').replace(',',''))
        diff = info.get('漲跌價差','0').replace('+','').replace(',','')
        try:
            change_val = float(diff)
        except:
            change_val = 0.0
        quote = {
            'symbol': symbol,
            'price': close,
            'changePct': (change_val/close*100) if close>0 else 0,
            'volume': int(info.get('成交股數','0').replace(',','')),
        }
        print(json.dumps(quote, ensure_ascii=False))
        sys.exit(0)

print(json.dumps({'symbol':symbol,'price':0,'changePct':0,'volume':0}))
