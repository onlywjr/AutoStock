#!/usr/bin/env python3
"""
fetch_market.py — 全市場日行情 + 熱門股排行

資料來源（均已實測可用）：
  - TWSE:  MI_INDEX?type=ALLBUT0999（每日收盤行情，全上市約 1,300+ 筆）
  - TPEx:  tpex_mainboard_daily_close_quotes（全上櫃，約 12,000 筆）

規則：
  - 排除「00 開頭」的非 ETF（如 00400A 股權證類；純 00xxx 五碼 ETF 保留）
  - 成交額 < MIN_AMOUNT（1 億）不列入排行
  - 四個榜：成交額 / 成交筆數 / 漲幅 / 跌幅，各取前 10
"""
import re, os, json, ssl, time, datetime, urllib.request

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

MIN_AMOUNT = 100_000_000        # 最小成交金額門檻：1 億元
TOP_N = 10                     # 每榜取前 N
ETF_RE = re.compile(r'^00\d{3}$')  # 純 ETF：五位數 00xxx

# 公司產業映射（與 ticker_company.json 共用結構，但這裡只做 symbol → industry）
def _load_industry_map():
    map_file = os.path.join(REPO_ROOT, 'ticker_company.json')
    try:
        with open(map_file, encoding='utf-8') as f:
            raw = json.load(f)
        out = {}
        for k, v in raw.items():
            if isinstance(v, dict):
                out[k] = v.get('industry', v.get('name', k))
            elif isinstance(v, str):
                out[k] = v
        return out
    except Exception:
        return {}

INDUSTRY_MAP = _load_industry_map()


def _get_json(url: str, timeout: int = 60):
    req = urllib.request.Request(
        url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))
    except Exception:
        ctx = ssl._create_unverified_context()
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return json.loads(r.read().decode('utf-8', 'replace'))


def _num(v) -> float:
    try:
        s = str(v or '').replace(',', '').replace('+', '').strip()
        return float(s) if s else 0.0
    except Exception:
        return 0.0


def _pct(change, close) -> float:
    prev = close - change
    return round(change / prev * 100, 2) if prev else 0.0


def _keep_00(sym: str) -> bool:
    """00 開頭者：只保留純 ETF（00xxx 五位數），其餘（00400A 等）剔除。"""
    return not sym.startswith('00') or bool(ETF_RE.match(sym))


def twse_market(date_compact: str):
    """回傳 [record] 或 None（無資料）。record: dict，含 market/symbol/name/close/..."""
    url = ('https://www.twse.com.tw/exchangeReport/MI_INDEX'
           f'?response=json&type=ALLBUT0999&date={date_compact}')
    j = _get_json(url)
    for t in (j.get('tables') or []):
        if '每日收盤行情' in str(t.get('title', '')):
            rows = t.get('data') or []
            if not rows:
                return None
            fields = t['fields']
            recs = []
            for r in rows:
                d = dict(zip(fields, r))
                sym = str(d.get('證券代號', '')).strip()
                if not _keep_00(sym):
                    continue
                close = _num(d.get('收盤價'))
                chg = _num(d.get('漲跌價差'))
                prev_close = close - chg
                high = _num(d.get('最高價'))
                low = _num(d.get('最低價'))
                recs.append({
                    'market': '上市',
                    'symbol': sym,
                    'name': str(d.get('證券名稱', '')).strip(),
                    'close': close,
                    'change_pct': _pct(chg, close),
                    'volume': int(_num(d.get('成交股數'))),
                    'amount': int(_num(d.get('成交金額'))),
                    'trades': int(_num(d.get('成交筆數'))),
                    'amplitude': round((high - low) / prev_close * 100, 2) if prev_close else None,
                    'industry': INDUSTRY_MAP.get(sym, ''),
                })
            return recs
    return None


def tpex_market():
    """TPEx 只有最新一日；回傳 [record]。"""
    today = datetime.date.today()
    url = ('https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'
           f"?l=zh-tw&d={today.strftime('%Y/%m/%d')}&se=EW")
    try:
        lst = _get_json(url)
    except Exception:
        return [], today.strftime('%Y-%m-%d')
    if not isinstance(lst, list):
        return [], today.strftime('%Y-%m-%d')
    # 以第一筆的 Date 欄位為準（API 可能回傳非 requested 日期的資料）
    raw_date = str(lst[0].get('Date', '')).strip() if lst else ''
    data_date = raw_date[:8]
    if re.fullmatch(r'\d{7}', data_date):      # 國曆 yyyymmdd
        data_date = f'{1911 + int(data_date[:3]):04d}-{data_date[3:5]}-{data_date[5:7]}'
    elif re.fullmatch(r'\d{8}', data_date):     # 西曆 yyyymmdd
        data_date = f'{data_date[:4]}-{data_date[4:6]}-{data_date[6:8]}'
    else:
        data_date = today.strftime('%Y-%m-%d')

    recs = []
    for item in lst:
        sym = str(item.get('SecuritiesCompanyCode', '')).strip()
        if not _keep_00(sym):
            continue
        close = _num(item.get('Close'))
        chg = _num(item.get('Change'))
        prev_close = close - chg
        high = _num(item.get('High'))
        low = _num(item.get('Low'))
        recs.append({
            'market': '上櫃',
            'symbol': sym,
            'name': str(item.get('CompanyName', '')).strip(),
            'close': close,
            'change_pct': _pct(chg, close),
            'volume': int(_num(item.get('TradingShares'))),
            'amount': int(_num(item.get('TransactionAmount'))),
            'trades': int(_num(item.get('TransactionNumber'))),
            'amplitude': round((high - low) / prev_close * 100, 2) if prev_close else None,
            'industry': INDUSTRY_MAP.get(sym, ''),
        })
    return recs, data_date


def build_hot(max_back: int = 10, out_path: str = None) -> dict:
    """抓取全市場 → 過濾 → 排行。寫出 data/hot_stocks.json（決定性內容，可 git 追蹤）。"""
    today = datetime.date.today()

    # 上市：今日無資料（假日）時往前找
    twse_recs, twse_date = [], ''
    for i in range(max_back):
        d = today - datetime.timedelta(days=i)
        recs = twse_market(d.strftime('%Y%m%d'))
        if recs:
            twse_recs, twse_date = recs, d.strftime('%Y-%m-%d')
            break
        time.sleep(0.2)

    tpex_recs, tpex_date = tpex_market()

    all_recs = twse_recs + tpex_recs
    qual = [r for r in all_recs if r['amount'] >= MIN_AMOUNT]

    def topn(sorted_recs, key):
        out = []
        for i, r in enumerate(sorted_recs[:TOP_N], 1):
            item = dict(r)
            item['rank'] = i
            out.append(item)
        return out

    by_amt = sorted(qual, key=lambda r: r['amount'], reverse=True)
    by_trd = sorted(qual, key=lambda r: r['trades'], reverse=True)
    by_up = sorted(qual, key=lambda r: r['change_pct'], reverse=True)
    by_dn = sorted(qual, key=lambda r: r['change_pct'])

    result = {
        'twse_date': twse_date,
        'tpex_date': tpex_date,
        'filters': {'min_amount': MIN_AMOUNT, 'top_n': TOP_N, 'keep_etf_only': True},
        'counts': {
            'twse': len(twse_recs),
            'tpex': len(tpex_recs),
            'qualifying': len(qual),
        },
        'amount_top10': topn(by_amt, 'amount'),
        'trades_top10': topn(by_trd, 'trades'),
        'up_top10': topn(by_up, 'change_pct'),
        'down_top10': topn(by_dn, 'change_pct'),
    }

    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    return result


if __name__ == '__main__':
    out = os.path.join(REPO_ROOT, 'data', 'hot_stocks.json')
    r = build_hot(out_path=out)
    print(f"TWSE {r['counts']['twse']} 筆 ({r['twse_date']}) + TPEx {r['counts']['tpex']} 筆 ({r['tpex_date']})")
    print(f"符合門檻 {r['counts']['qualifying']} 筆，已寫入 {out}")
