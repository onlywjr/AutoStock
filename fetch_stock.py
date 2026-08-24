import sys, json, urllib.request
symbol = sys.argv[1]
url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbol}.TW"
with urllib.request.urlopen(url) as resp:
    data = json.load(resp)
quote = data.get('quoteResponse',{}).get('result',[{}])[0]
print(json.dumps({
    'symbol': quote.get('symbol'),
    'price': quote.get('regularMarketPrice'),
    'changePct': quote.get('regularMarketChangePercent'),
    'volume': quote.get('regularMarketVolume'),
    'marketCap': quote.get('marketCap'),
    'pe': quote.get('trailingPE'),
    'eps': quote.get('trailingEps')
}, ensure_ascii=False))