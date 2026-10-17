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
import sys, json, ssl, os, re, time, datetime, urllib.request

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

# ── FinMind JWT（從 .env 讀取，不洩漏至前端）────────────────────
_JWT = ''


def _load_finmind_token() -> str:
    global _JWT
    if _JWT:
        return _JWT
    env_file = os.path.join(REPO_ROOT, '.env')
    try:
        with open(env_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('FINMIND_TOKEN='):
                    _JWT = line.split('=', 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass
    return _JWT

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


def _get_json(url: str) -> dict | None:
    """GET JSON。SSL 驗證在本機不穩定：先用預設 context，失敗再換 CERT_NONE 重試。
    若仍失敗（例如需要 Authorization header），則加上 JWT 再試一次。"""
    ctx = ssl.create_default_context()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    for try_auth in (False, True):
        if try_auth and _JWT:
            headers['Authorization'] = f'Bearer {_JWT}'
        for verify in (True, False):
            try:
                req_ctx = ssl.create_default_context() if verify else ssl._create_unverified_context()
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, context=req_ctx, timeout=30) as resp:
                    return json.load(resp)
            except Exception:
                continue
    return None


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


def fetch_twse_year(symbol: str) -> list:
    """以「整月」方式逐月呼叫 STOCK_DAY，回傳近 12 個月的日K（時間正序）。

    回傳: [{'date': 'YYYY-MM-DD', 'close': float, 'volume': int}, ...]
    """
    today = datetime.date.today()
    months = []
    y, m = today.year, today.month
    for i in range(11, -1, -1):
        mm = m - i
        yy = y + (mm - 1) // 12
        mm = (mm - 1) % 12 + 1
        months.append((yy, mm))

    out, seen = [], set()
    for yy, mm in months:
        url = (f"https://www.twse.com.tw/exchangeReport/STOCK_DAY"
               f"?response=json&date={yy}{mm:02d}01&stockNo={symbol}")
        try:
            data = _get_json(url)
        except Exception:
            time.sleep(1)
            continue
        rows = data.get('data') or []
        if not rows:
            continue
        fields = data.get('fields') or []
        for r in rows:
            rec = dict(zip(fields, r))
            d = _norm_date(rec.get('日期', ''))
            close = _num(rec.get('收盤價'))
            if not d or close <= 0 or d in seen:
                continue
            seen.add(d)
            out.append({'date': d, 'close': close, 'volume': _int(rec.get('成交股數'))})
        time.sleep(0.2)
    out.sort(key=lambda x: x['date'])
    return out


def _rolling_ma(closes, k):
    """與 closes 等長的 MA 序列；前 k-1 點為 None。"""
    out = []
    for i in range(len(closes)):
        if i + 1 < k:
            out.append(None)
        else:
            out.append(round(sum(closes[i + 1 - k:i + 1]) / k, 2))
    return out


def compute_stats(series):
    """由日K系列衍生統計值；無資料回 None。

    series: [{'date','close','volume'}] 時間正序（約 240 點）。
    """
    if not series:
        return None
    closes = [r['close'] for r in series]
    vols = [r['volume'] for r in series]
    n = len(closes)
    last = closes[-1]

    def ma(k):
        return round(sum(closes[-k:]) / k, 2) if n >= k else None

    def chg(k):
        if n > k and closes[-1 - k]:
            return round((last - closes[-1 - k]) / closes[-1 - k] * 100, 2)
        return None

    high52, low52 = max(closes), min(closes)
    pos52 = round((last - low52) / (high52 - low52) * 100, 1) if high52 > low52 else 50.0

    vol30 = None
    if n >= 31:
        rets = [((closes[i] - closes[i - 1]) / closes[i - 1]) for i in range(n - 30, n) if closes[i - 1]]
        if len(rets) >= 20:
            mean = sum(rets) / len(rets)
            var = sum((x - mean) ** 2 for x in rets) / len(rets)
            vol30 = round((var ** 0.5) * (252 ** 0.5) * 100, 1)

    this_year = series[-1]['date'][:4]
    prev_closes = [r['close'] for r in series if r['date'][:4] == str(int(this_year) - 1)]
    ytd = round((last - prev_closes[-1]) / prev_closes[-1] * 100, 2) if prev_closes else None

    avg_vol20 = int(sum(vols[-20:]) / min(20, len(vols))) if vols else None
    vol_ratio = round(vols[-1] / avg_vol20, 2) if avg_vol20 else None

    return {
        'n_days': n,
        'ma5': ma(5), 'ma20': ma(20), 'ma60': ma(60),
        'high52': high52, 'low52': low52, 'pos52': pos52,
        'chg_52w': round((last - closes[0]) / closes[0] * 100, 2) if closes[0] else None,
        'm1': chg(21), 'm3': chg(63), 'm6': chg(126), 'ytd': ytd,
        'vol30_ann': vol30,
        'avg_vol20': avg_vol20, 'vol_ratio': vol_ratio,
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
        # TPEx 公開 API 只有最新一日收盤，無歷史 → 統計值皆為 None
        quote['stats'] = None
        quote['chart'] = None
    else:
        quote = fetch_twse(symbol, company)
        yser = fetch_twse_year(symbol)
        quote['stats'] = compute_stats(yser)
        # 圖表：近 60 個交易日收盤 + MA20（MA20 用完整年序列算，避免前段缺值）
        closes = [r['close'] for r in yser]
        ma20_all = _rolling_ma(closes, 20)
        seg = yser[-60:]
        quote['chart'] = {
            'labels': [r['date'][5:] for r in seg],
            'close': [r['close'] for r in seg],
            'ma20': ma20_all[-60:],
        }
        quote['year_series'] = yser  # 供 data/*.json 存檔與除錯

    # 公司名稱一律以映射檔為準（TPEx 的 API 名稱也交叉比對過，避免不一致）
    quote['company'] = company
    quote['full_name'] = info.get('full_name', company)
    quote['industry'] = info.get('industry', '')
    quote['desc'] = info.get('desc', '')
    quote['catalysts'] = info.get('catalysts', [])

    # FinMind：PER / PBR / 殖利率（Free）
    _load_finmind_token()
    if _JWT:
        try:
            per_data = _get_json(f'https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockPER&data_id={symbol}&start_date=2020-01-01&sort=data_date&limit=1')
            rows = per_data.get('data') if isinstance(per_data, dict) else None
            if rows:
                r = rows[-1]
                quote['per'] = r.get('PER')
                quote['pbr'] = r.get('PBR')
                quote['div_yield'] = r.get('dividend_yield')
        except Exception:
            pass
        try:
            sh_data = _get_json(f'https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockShareholding&data_id={symbol}&start_date=2026-01-01&sort=data_date&limit=1')
            rows = sh_data.get('data') if isinstance(sh_data, dict) else None
            if rows:
                r = rows[-1]
                quote['foreign_ratio'] = r.get('ForeignInvestmentSharesRatio')  # 外資持股比例 %
                quote['foreign_hold'] = r.get('ForeignInvestmentShares')       # 外資持股股數
                quote['foreign_limit_ratio'] = r.get('ForeignInvestmentUpperLimitRatio')
        except Exception:
            pass

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
