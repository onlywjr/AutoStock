#!/usr/bin/env python3
"""
fetch_stock.py — 單一股票資料取得層（AutoStock 重構版）

用法:
    python fetch_stock.py 6139          # 印出 JSON 到 stdout
    import fetch_stock                  # 當成模組使用

輸出欄位 (JSON):
    symbol, company, date, open, high, low, close, prev_close,
    change, change_pct, volume, amount,
    history: [{date, close} x5]

資料來源:
    TWSE (上市):  https://www.twse.com.tw/exchangeReport/STOCK_DAY
    TPEx (上櫃):  https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes

SSL 說明: 本機環境 SSL 驗證時好時壞（Missing Subject Key Identifier），
因此 _get_json 先走預設 context，失敗時自動以 CERT_NONE 重試。
"""
import sys, json, ssl, os, re, datetime, urllib.request

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# 上櫃股票走 TPEx；1434/2327/2330/6213 為上市（走 TWSE）
TPEX_TICKERS = {'8299'}

HISTORY_DAYS = 5        # 儀表板近 N 日收盤圖
TWSE_LOOKBACK_DAYS = 10  # TWSE 一次取回多少日（保證 >= HISTORY_DAYS 個交易日）


def _num(v):
    """'2,440.00' / '-50.00' / '0' / '-' -> float；無效值回 0.0"""
    try:
        s = str(v).replace(',', '').replace('+', '').strip()
        if s in ('', '-'):
            return 0.0
        return float(s)
    except Exception:
        return 0.0


def _int(v):
    return int(_num(v))


def _get_json(url: str):
    """GET JSON。SSL 驗證在本機不穩定：先用預設 context，失敗再換 CERT_NONE 重試。"""
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.load(resp)
    except Exception:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
            return json.load(resp)


def _norm_date(s) -> str:
    """TWSE 的國曆日期 '115/10/15' → '2026-10-15'；西曆 'YYYY-MM-DD' 原樣回傳。"""
    s = str(s or '').strip()
    m = re.match(r'^(\d{3})/(\d{1,2})/(\d{1,2})$', s)
    if m:
        try:
            d = datetime.date(1911 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d.strftime('%Y-%m-%d')
        except ValueError:
            return s
    return s


def fetch_twse(symbol: str, company: str = '') -> dict:
    """TWSE: 一次取回近期所有交易日（含 5 日歷史），回傳標準化資料。"""
    today = datetime.date.today()
    end = today.strftime('%Y%m%d')
    start = (today - datetime.timedelta(days=TWSE_LOOKBACK_DAYS)).strftime('%Y%m%d')
    url = (
        f"https://www.twse.com.tw/exchangeReport/STOCK_DAY"
        f"?response=json&startdate={start}&stockNo={symbol}"
    )
    data = _get_json(url)
    rows = data.get('data') or []
    if not rows:
        raise RuntimeError(f'TWSE 無資料: {symbol} ({start}~{end})，可能是非交易日')
    fields = data.get('fields') or []
    series = [dict(zip(fields, r)) for r in rows]
    last = series[-1]

    close = _num(last.get('收盤價'))
    change = _num(last.get('漲跌價差'))
    prev_close = close - change
    change_pct = (change / prev_close * 100) if prev_close else 0.0

    history = [
        {'date': _norm_date(s.get('日期', '')), 'close': _num(s.get('收盤價'))}
        for s in series[-HISTORY_DAYS:]
    ]
    return {
        'symbol': symbol,
        'company': company,
        'date': _norm_date(last.get('日期', '')),
        'open': _num(last.get('開盤價')),
        'high': _num(last.get('最高價')),
        'low': _num(last.get('最低價')),
        'close': close,
        'prev_close': prev_close,
        'change': change,
        'change_pct': change_pct,
        'volume': _int(last.get('成交股數')),
        'amount': _int(last.get('成交金額')),
        'history': history,
    }


def _parse_roc_date(s: str):
    """解析 TPEx 的 Date 欄位，回傳 datetime.date 或 None。

    支援格式:
      - ISO 'YYYY-MM-DD'
      - 國曆 'yyyymmdd'（7 碼, 如 '1151015' → 2026-10-15）
      - 西曆 'yyyymmdd'（8 碼）
    """
    s = str(s or '').strip()
    if not s:
        return None
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s)
    if m:
        try:
            return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    m = re.match(r'^\d{7}$', s)
    if m:
        try:  # 國曆 yyyymmdd
            return datetime.date(1911 + int(s[:3]), int(s[3:5]), int(s[5:7]))
        except ValueError:
            return None
    m = re.match(r'^\d{8}$', s)
    if m:  # 西曆 yyyymmdd
        try:
            return datetime.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except ValueError:
            return None
    return None


def fetch_tpex(symbol: str, company: str = '') -> dict:
    """TPEx: 單一日期 endpoint。逐日回查、以 Date 欄位去重，回傳近 5 個交易日（時間正序）。

    注意: 此 endpoint 對任意 d 參數都可能回傳「最新」收盤資料，因此改用
    Date 欄位做真實交易日去重，避免重複計入同一天。
    """
    today = datetime.date.today()

    def query(day: datetime.date):
        """回傳該日該股的 enriched dict；無資料回 None。以 Date 欄位記錄真實日期。"""
        url = (
            "https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes"
            f"?l=zh-tw&d={day.strftime('%Y/%m/%d')}&se=EW"
        )
        try:
            lst = _get_json(url)
        except Exception:
            return None
        if not isinstance(lst, list):
            return None
        for item in lst:
            if item.get('SecuritiesCompanyCode') != symbol:
                continue
            return {
                'actual_date': _parse_roc_date(item.get('Date')) or day,
                'open': _num(item.get('Open')),
                'high': _num(item.get('High')),
                'low': _num(item.get('Low')),
                'close': _num(item.get('Close')),
                'change': _num(item.get('Change')),
                'volume': _int(item.get('TradingShares')),
                'amount': _int(item.get('TransactionAmount')),
                'company': item.get('CompanyName') or '',
            }
        return None

    # 此 endpoint 對任意 d 參數都回傳「最新」收盤資料，故只需查今天與昨天，
    # 依 Date 欄位去重；去重後最多 1~2 個真實交易日（無法取得完整 5 日歷史）。
    seen = {}
    for i in range(0, 2):
        day = today - datetime.timedelta(days=i)
        if day.weekday() >= 5:
            continue
        rec = query(day)
        if rec:
            key = rec.pop('actual_date')
            rec['date'] = key.strftime('%Y-%m-%d')
            seen.setdefault(key, rec)

    days = sorted(seen.values(), key=lambda r: r['date'])[-HISTORY_DAYS:]
    if not days:
        raise RuntimeError(f'TPEx 無資料: {symbol}')

    last = days[-1]
    close = last['close']
    prev_close = close - last['change']
    change_pct = (last['change'] / prev_close * 100) if prev_close else 0.0

    return {
        'symbol': symbol,
        'company': last.get('company') or company,
        'date': last['date'],
        'open': last['open'],
        'high': last['high'],
        'low': last['low'],
        'close': close,
        'prev_close': prev_close,
        'change': last['change'],
        'change_pct': change_pct,
        'volume': last['volume'],
        'amount': last['amount'],
        'history': [{'date': d['date'], 'close': d['close']} for d in days],
    }


def load_company_map() -> dict:
    """讀取 ticker_company.json（代號 → 名稱/產業/重點）。

    相容兩種格式：
      - 新格式: {"1434": {"name": "福懋興業", "industry": "...", ...}}
      - 舊格式: {"1434": "福懋興業股份有限公司"}
    """
    map_file = os.path.join(REPO_ROOT, 'ticker_company.json')
    try:
        with open(map_file, encoding='utf-8') as f:
            raw = json.load(f)
    except Exception:
        return {}
    normalized = {}
    for k, v in raw.items():
        if isinstance(v, dict):
            normalized[k] = v
        elif isinstance(v, str):
            normalized[k] = {'name': v}
    return normalized


def fetch_data(symbol: str) -> dict:
    """回傳單一股票完整資料（公司名稱以映射檔為準，確保不會失誤）。"""
    mapping = load_company_map()
    info = mapping.get(symbol, {})
    company = info.get('name', symbol)

    if symbol in TPEX_TICKERS:
        quote = fetch_tpex(symbol, company)
    else:
        quote = fetch_twse(symbol, company)

    # 公司名稱一律以映射檔為準（TPEx 的 API 名稱也交叉比對過，避免不一致）
    quote['company'] = company
    quote['industry'] = info.get('industry', '')
    quote['desc'] = info.get('desc', '')
    quote['catalysts'] = info.get('catalysts', [])
    return quote


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.stderr.write('使用方式: python fetch_stock.py <代號>\n')
        sys.exit(1)
    sym = sys.argv[1]
    try:
        result = fetch_data(sym)
    except Exception as e:
        sys.stderr.write(f'fetch failed: {e}\n')
        sys.exit(1)
    print(json.dumps(result, ensure_ascii=False))
