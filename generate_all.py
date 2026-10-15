#!/usr/bin/env python3
"""
generate_all.py — AutoStock 頁面生成器

功能:
  1. 逐檔股票呼叫 fetch_stock.fetch_data() 取得最新收盤 + 近 5 日歷史
  2. 寫入 data/<代號>.json（備份 / 除錯用）
  3. 以 templates/dashboard_template.html 產出 <代號>.html
  4. 以 templates/index_template.html 產出 index.html（含全部卡片）

用法:
    python generate_all.py            # 產出全部頁面
抓取失敗時，會退回上一次的 data/<代號>.json 重繪頁面（不讓頁面掛掉）。
"""
import sys, os, json, datetime, html

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

import fetch_stock

TICKERS = ['1434', '2327', '2330', '6139', '6213', '8299']
DATA_DIR = os.path.join(REPO_ROOT, 'data')
TPL_DIR = os.path.join(REPO_ROOT, 'templates')


# ---------------------------------------------------------------- 格式化

def fmt_price(x):
    return f'{x:,.2f}'


def fmt_amount(x):
    if not x:
        return '—'
    yi = x / 1e8
    return f'{yi:,.1f} 億' if yi >= 1 else f'{x / 1e4:,.0f} 萬'


def fmt_volume(x):
    if not x:
        return '—'
    wan = x / 1e4
    return f'{wan:,.1f} 萬'


def change_info(change, pct):
    cls = 'up' if change > 0 else ('down' if change < 0 else 'flat')
    sign = '▲' if change > 0 else ('▼' if change < 0 else '＝')
    return cls, sign


def load_template(name: str) -> str:
    with open(os.path.join(TPL_DIR, name), encoding='utf-8') as f:
        return f.read()


def chart_body(history):
    """回傳 (CHART_BODY, CHART_SCRIPT)；歷史 < 2 點時改顯示說明。"""
    if len(history) < 2:
        note = (
            '<div class="chart-note">TPEx 公開 API 目前僅提供最新收盤資料，'
            '暫無近 5 日走勢（資料來源限制）。</div>'
        )
        return note, ''
    labels = [h['date'][-5:] for h in history]           # MM-DD
    vals = [h['close'] for h in history]
    color = '#22c55e' if vals[-1] >= vals[0] else '#ef4444'
    body = '<div class="chartbox"><canvas id="priceChart"></canvas></div>'
    script = (
        '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n'
        '<script>\n'
        'const c = document.getElementById("priceChart").getContext("2d");\n'
        'new Chart(c, {\n'
        '  type: "line",\n'
        '  data: { labels: ' + json.dumps(labels) + ',\n'
        '    datasets: [{ label: "收盤價 (NTD)", data: ' + json.dumps(vals) + ',\n'
        f'      borderColor: "{color}", backgroundColor: "rgba(56,189,248,0.08)",\n'
        '      borderWidth: 2, pointRadius: 4, pointBackgroundColor: "' + color + '",\n'
        '      tension: 0.25, fill: true }] },\n'
        '  options: { responsive: true, maintainAspectRatio: false,\n'
        '    plugins: { legend: { display: false } },\n'
        '    scales: {\n'
        '      x: { ticks: { color: "#8b9bb4" }, grid: { color: "rgba(148,163,184,0.08)" } },\n'
        '      y: { ticks: { color: "#8b9bb4" }, grid: { color: "rgba(148,163,184,0.08)" }, beginAtZero: false }\n'
        '    } }\n'
        '});\n'
        '</script>'
    )
    return body, script


def catalyst_items(catalysts):
    if not catalysts:
        return '<li>本檔股票暫無設定投資重點，請至 <b>ticker_company.json</b> 補上。</li>'
    out = []
    for i, c in enumerate(catalysts, 1):
        out.append(f'<li><b>{i}</b>{html.escape(str(c))}</li>')
    return '\n        '.join(out)


def build_stock_page(d: dict) -> str:
    tpl = load_template('dashboard_template.html')
    cls, sign = change_info(d.get('change', 0), d.get('change_pct', 0))
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    chart_body_html, chart_script = chart_body(d.get('history', []))

    out = tpl
    replacements = {
        '{{TICKER}}': d['symbol'],
        '{{COMPANY_NAME}}': d.get('company', d['symbol']),
        '{{COMPANY_FULL}}': d.get('full_name', ''),
        '{{INDUSTRY}}': d.get('industry', '—'),
        '{{DESC}}': d.get('desc', ''),
        '{{DATA_DATE}}': d.get('date', ''),
        '{{CLOSE}}': fmt_price(d.get('close', 0)),
        '{{OPEN}}': fmt_price(d.get('open', 0)),
        '{{HIGH}}': fmt_price(d.get('high', 0)),
        '{{LOW}}': fmt_price(d.get('low', 0)),
        '{{PREV_CLOSE}}': fmt_price(d.get('prev_close', 0)),
        '{{VOLUME}}': fmt_volume(d.get('volume', 0)),
        '{{AMOUNT}}': fmt_amount(d.get('amount', 0)),
        '{{CHANGE}}': fmt_price(abs(d.get('change', 0))),
        '{{CHANGE_PCT}}': f"{abs(d.get('change_pct', 0)):,.2f}",
        '{{CHANGE_SIGN}}': sign,
        '{{CHANGE_CLASS}}': cls,
        '{{HISTORY_DAYS}}': str(len(d.get('history', []))),
        '{{CHART_BODY}}': chart_body_html,
        '{{CHART_SCRIPT}}': chart_script,
        '{{CATALYST_ITEMS}}': catalyst_items(d.get('catalysts', [])),
    }
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def build_index(records) -> str:
    tpl = load_template('index_template.html')
    cards = []
    for sym in TICKERS:
        d = records.get(sym)
        if not d:
            cards.append(
                f'<a class="card" href="#" aria-disabled="true" style="opacity:.45">'
                f'<div class="row1"><span class="ticker mono">{sym}.TW</span>'
                f'<span class="industry">—</span></div>'
                f'<h3>資料未取得</h3>'
                f'<div class="pricerow"><span class="meta">抓取失敗，請見 git log</span></div></a>'
            )
            continue
        cls, sign = change_info(d.get('change', 0), d.get('change_pct', 0))
        full = html.escape(d.get('full_name', ''))
        name_attr = html.escape(d.get('company', sym))
        cards.append(f'''<a class="card" href="{sym}.html">
  <div class="row1">
    <span class="ticker mono">{sym}.TW</span>
    <span class="industry">{html.escape(d.get("industry", "—"))}</span>
  </div>
  <h3>{name_attr}<small>{full}</small></h3>
  <div class="meta">資料日期 {html.escape(d.get("date", ""))}<span>成交量 {fmt_volume(d.get("volume", 0))} 股</span></div>
  <div class="pricerow">
    <span class="price mono {cls}">{fmt_price(d.get("close", 0))}</span>
    <span class="chg mono {cls}">{sign} {fmt_price(abs(d.get("change", 0)))} ({abs(d.get("change_pct", 0)):,.2f}%)</span>
  </div>
</a>''')
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    out = tpl.replace('{{CARDS}}', '\n    '.join(cards)).replace('{{UPDATE_TIME}}', now)
    return out


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    records, failed = {}, []

    for sym in TICKERS:
        path = os.path.join(DATA_DIR, f'{sym}.json')
        fresh = None
        try:
            fresh = fetch_stock.fetch_data(sym)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(fresh, f, ensure_ascii=False, indent=2)
            records[sym] = fresh
            print(f'[OK]   {sym} close={fresh.get("close")} {fresh.get("date")}')
        except Exception as e:
            print(f'[FAIL] {sym} {e}')
            failed.append(sym)
            if os.path.exists(path):          # 退回上一版資料
                with open(path, encoding='utf-8') as f:
                    records[sym] = json.load(f)
                print(f'[FALLBACK] {sym} 使用 data/{sym}.json 舊資料重繪')

    # 產生各股頁面
    for sym, d in records.items():
        page = build_stock_page(d)
        with open(os.path.join(REPO_ROOT, f'{sym}.html'), 'w', encoding='utf-8') as f:
            f.write(page)
        print(f'[PAGE] {sym}.html')

    # 產生 index
    with open(os.path.join(REPO_ROOT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build_index(records))
    print('[PAGE] index.html')

    if failed:
        print(f'WARN: 以下代號本次抓取失敗（已用舊資料重繪）: {failed}')
    print('DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
