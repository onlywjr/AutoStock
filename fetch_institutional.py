#!/usr/bin/env python3
"""
fetch_institutional.py — 法人買賣超資料（FinMind API）

使用方式:
    python fetch_institutional.py              # 抓所有 TICKERS 最新一日
    python fetch_institutional.py 2330         # 抓單一股票

輸出欄位 (JSON):
    foreign_net   : 外資淨額（正=買超，負=賣超）
    trust_net     : 投信淨額
    dealer_net    : 自營商淨額（Dealer_self + Dealer_Hedging）
    total_net     : 三大法人合計淨額
"""
import os, sys, json, ssl, datetime, urllib.request

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
TICKERS_FILE = os.path.join(REPO_ROOT, 'ticker_company.json')

# ── JWT 從 .env 讀取（不在程式碼中明文寫入）─────────────────
def _load_finmind_token() -> str:
    env_file = os.path.join(REPO_ROOT, '.env')
    try:
        with open(env_file, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('FINMIND_TOKEN='):
                    return line.split('=', 1)[1].strip().strip('"').strip("'")
    except Exception:
        pass
    return ''

JWT = _load_finmind_token()
if not JWT:
    sys.stderr.write('ERROR: .env 中沒有 FINMIND_TOKEN，請將 token 寫入 .env\n')
    sys.exit(1)

# ── 載入代號清單 ───────────────────────────────────────────────
def load_tickers() -> list:
    try:
        with open(TICKERS_FILE, encoding='utf-8') as f:
            raw = json.load(f)
        # 支援 dict 或 list 格式
        if isinstance(raw, dict):
            return list(raw.keys())
        elif isinstance(raw, list):
            return [str(x) for x in raw]
    except Exception:
        pass
    return ['1434', '2327', '2330', '6139', '6213', '8299']


# ── HTTP GET（自動 fallback CERT_NONE）────────────────────────
def _get_json(url: str) -> dict | None:
    ctx = ssl.create_default_context()
    try:
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {JWT}',
            'User-Agent': 'Mozilla/5.0'
        })
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:
        ctx = ssl._create_unverified_context()
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {JWT}',
            'User-Agent': 'Mozilla/5.0'
        })
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))


# ── 抓取單一股票最新一日法人買賣超 ─────────────────────────────
def fmt_lot(v: float | None) -> str:
    if v is None:
        return '—'
    if v >= 10000:
        return f'{v/10000:.1f} 萬張'
    else:
        return f'{v:.0f} 張'

def fetch_one(symbol: str) -> dict | None:
    """回傳 {foreign_net, trust_net, dealer_net, total_net, date}，無資料回 None。
    單位：張（1 張 = 1,000 股）"""
    url = (f'https://api.finmindtrade.com/api/v4/data'
           f'?dataset=TaiwanStockInstitutionalInvestorsBuySell'
           f'&data_id={symbol}&start_date=2020-01-01'
           f'&sort=data_date&limit=100')
    j = _get_json(url)
    rows = j.get('data') if isinstance(j, dict) else None
    if not rows:
        return None
    # 以最新日期分組
    by_date = {}
    for row in rows:
        d = row.get('date', '')
        by_date.setdefault(d, []).append(row)
    if not by_date:
        return None
    latest_date = max(by_date.keys())
    day_rows = by_date[latest_date]

    def net_for(name: str) -> float:
        """返回淨額（買賣差額），單位：張（1 張 = 1,000 股）"""
        total = 0.0
        for r in day_rows:
            if r.get('name') == name:
                buy = int(r.get('buy', 0))
                sell = int(r.get('sell', 0))
                total += (buy - sell) / 1000.0   # 轉換為張
        return total

    foreign_net = net_for('Foreign_Investor')
    trust_net   = net_for('Investment_Trust')
    dealer_net  = net_for('Dealer_self') + net_for('Dealer_Hedging')
    total_net   = foreign_net + trust_net + dealer_net

    return {
        'date': latest_date,
        'foreign_net': foreign_net,
        'trust_net':   trust_net,
        'dealer_net':  dealer_net,
        'total_net':   total_net,
    }


# ── 主程式 ─────────────────────────────────────────────────────
if __name__ == '__main__':
    tickers = load_tickers()
    if len(sys.argv) > 1:
        tickers = [sys.argv[1]]

    results = {}
    for sym in tickers:
        r = fetch_one(sym)
        if r:
            results[sym] = r
            sign = '買超' if r['total_net'] > 0 else ('賣超' if r['total_net'] < 0 else '平衡')
            print(f'{sym} {r["date"]}: 外資{fmt_lot(r["foreign_net"])} 投信{fmt_lot(r["trust_net"])} '
                  f'自營{fmt_lot(r["dealer_net"])} 合计{fmt_lot(r["total_net"])} {sign}')
        else:
            print(f'{sym}: 無資料')
    # 寫入 data/institutional.json
    out_path = os.path.join(REPO_ROOT, 'data', 'institutional.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'\n已寫入 {out_path}')
