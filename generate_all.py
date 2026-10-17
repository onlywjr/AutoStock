#!/usr/bin/env python3
"""
generate_all.py — AutoStock 頁面生成器（含自訂股 + 熱門股）

流程:
  1. 逐檔股票呼叫 fetch_stock.fetch_data() 取得最新收盤 + 近 5 日歷史
  2. 寫入 data/<代號>.json（備份 / 除錯用）
  3. 以 templates/dashboard_template.html 產出 <代號>.html
  4. 呼叫 fetch_market.build_hot() → 產出 data/hot_stocks.json
  5. 以新 layout（自訂股 + 熱門股四榜）產出 index.html
  6. 冪等：相同資料不會產生新的 git 差異
"""
import sys, os, json, datetime, html

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

import fetch_stock
import fetch_market

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
    """成交股數 → 張（1 張 = 1,000 股）。≥1 萬張顯示「X.X 萬張」。"""
    if not x:
        return '—'
    lots = x / 1000
    if lots >= 10000:
        return f'{lots / 10000:,.1f} 萬張'
    return f'{lots:,.0f} 張'


def fmt_amp(v):
    """漲跌幅區間（振幅）：例如 +1.23% 或 —。」"""
    if v is None:
        return '—'
    sign = '+' if v > 0 else ''
    return f'{sign}{v:.2f}%'


def change_info(change, pct):
    cls = 'up' if change > 0 else ('down' if change < 0 else 'flat')
    sign = '▲' if change > 0 else ('▼' if change < 0 else '＝')
    return cls, sign


def load_template(name: str) -> str:
    with open(os.path.join(TPL_DIR, name), encoding='utf-8') as f:
        return f.read()


def fmt_signed(v, suffix='%'):
    """+12.3% / -4.1% / —"""
    if v is None:
        return '—'
    sign = '+' if v > 0 else ''
    return f'{sign}{v:,.2f}{suffix}'


def perf_class(v):
    return 'up' if (v or 0) > 0 else ('down' if (v or 0) < 0 else 'flat')


def chart_section(d):
    """回傳 (CHART_TITLE, CHART_BODY, CHART_SCRIPT)。"""
    chart = d.get('chart')
    if chart and len(chart.get('close', [])) >= 2:
        labels = chart['labels']
        close = chart['close']
        ma20 = chart.get('ma20')
        color = '#ef4444' if close[-1] >= close[0] else '#22c55e'
        title = f"近 {len(close)} 日收盤與 MA20"
        ma_line = ('\n   { label: "MA20", data: ' + json.dumps(ma20) + ',\n'
                   '     borderColor: "#f59e0b", borderWidth: 1.5, borderDash: [5,3],\n'
                   '     pointRadius: 0, fill: false, tension: 0.25 }')
        body = '<div class="chartbox"><canvas id="priceChart"></canvas></div>'
        script = (
            '<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>\n'
            '<script>\n'
            'const c = document.getElementById("priceChart").getContext("2d");\n'
            'new Chart(c, {\n'
            '  type: "line",\n'
            '  data: { labels: ' + json.dumps(labels) + ',\n'
            '    datasets: [\n'
            '     { label: "收盤價 (NTD)", data: ' + json.dumps(close) + ',\n'
            f'      borderColor: "{color}", backgroundColor: "rgba(56,189,248,0.08)",\n'
            '      borderWidth: 2, pointRadius: 0, tension: 0.25, fill: true },'
            + ma_line + '\n'
            '    ] },\n'
            '  options: { responsive: true, maintainAspectRatio: false,\n'
            '    plugins: { legend: { labels: { color: "#8b9bb4" } } },\n'
            '    scales: {\n'
            '      x: { ticks: { color: "#8b9bb4", maxTicksLimit: 10 }, grid: { color: "rgba(148,163,184,0.08)" } },\n'
            '      y: { ticks: { color: "#8b9bb4" }, grid: { color: "rgba(148,163,184,0.08)" }, beginAtZero: false }\n'
            '    } }\n'
            '});\n'
            '</script>'
        )
        return title, body, script

    # fallback: 僅有短歷史（TPEx）
    history = d.get('history', [])
    if len(history) < 2:
        note = ('<div class="chart-note">TPEx 公開 API 目前僅提供最新收盤資料，'
                '無歷史走勢可繪（資料來源限制）。</div>')
        return '股價走勢', note, ''
    labels = [h['date'][-5:] for h in history]
    vals = [h['close'] for h in history]
    color = '#ef4444' if vals[-1] >= vals[0] else '#22c55e'
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
        '    scales: { x: { ticks: { color: "#8b9bb4" }, grid: { color: "rgba(148,163,184,0.08)" } },\n'
        '      y: { ticks: { color: "#8b9bb4" }, grid: { color: "rgba(148,163,184,0.08)" }, beginAtZero: false } } }\n'
        '});\n'
        '</script>'
    )
    return f"近 {len(vals)} 日收盤走勢", body, script


def w52_bar(stats):
    if not stats or stats.get('high52') is None:
        return ('<div class="chart-note">上櫃股無歷史資料（TPEx 僅提供最新收盤），'
                '52 週區間暫無法顯示。</div>')
    pos = stats.get('pos52', 50)
    cls = perf_class(stats.get('chg_52w'))
    return (
        f'<div class="w52bar" style="--pos:{pos}%"><div class="fill" style="width:{pos}%"></div>'
        f'<div class="marker" style="left:{pos}%"></div></div>'
        f'<div class="w52labels"><span>52 週低 <b class="down">{fmt_price(stats["low52"])}</b></span>'
        f'<span><b class="{cls}">{fmt_signed(stats.get("chg_52w"))}</b>（52 週）</span>'
        f'<span>52 週高 <b class="up">{fmt_price(stats["high52"])}</b></span></div>'
    )


def perf_items(stats):
    keys = [('52 週', 'chg_52w'), ('6 個月', 'm6'), ('3 個月', 'm3'), ('1 個月', 'm1'), ('今年以來', 'ytd')]
    if not stats:
        cells = [f'<div class="cell"><div class="k">{k}</div><div class="v">—</div></div>' for k, _ in keys]
        return '\n'.join(cells)
    out = []
    for label, key in keys:
        v = stats.get(key)
        cls = perf_class(v)
        out.append(f'<div class="cell"><div class="k">{label}</div>'
                   f'<div class="v mono {cls}">{fmt_signed(v)}</div></div>')
    return '\n'.join(out)


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
    stats = d.get('stats') or {}
    chart_title, chart_body_html, chart_script = chart_section(d)

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
        '{{CHART_TITLE}}': chart_title,
        '{{CHART_BODY}}': chart_body_html,
        '{{CHART_SCRIPT}}': chart_script,
        '{{W52_BAR}}': w52_bar(stats or None),
        '{{PERF_ITEMS}}': perf_items(stats or None),
        '{{MA5}}': fmt_price(stats.get('ma5')) if stats.get('ma5') is not None else '—',
        '{{MA20}}': fmt_price(stats.get('ma20')) if stats.get('ma20') is not None else '—',
        '{{MA60}}': fmt_price(stats.get('ma60')) if stats.get('ma60') is not None else '—',
        '{{VOL30}}': f"{stats['vol30_ann']:,.1f}%" if stats.get('vol30_ann') is not None else '—',
        '{{AVG_VOL20}}': fmt_volume(stats.get('avg_vol20')) if stats.get('avg_vol20') else '—',
        '{{VOL_RATIO}}': f"{stats['vol_ratio']:,.2f}x" if stats.get('vol_ratio') is not None else '—',
        '{{CATALYST_ITEMS}}': catalyst_items(d.get('catalysts', [])),
    }
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


# ---------------------------------------------------------------- 首頁自訂股卡片

def build_custom_cards(records: dict) -> str:
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
        ytd = (d.get('stats') or {}).get('ytd')
        ytd_cell = f'<span class="{perf_class(ytd)}">YTD {fmt_signed(ytd)}</span>' if ytd is not None else '<span>YTD —</span>'
        cards.append(f'''<a class="card" href="{sym}.html">
  <div class="row1">
    <span class="ticker mono">{sym}.TW</span>
    <span class="industry">{html.escape(d.get("industry", "—"))}</span>
  </div>
  <h3>{name_attr}<small>{full}</small></h3>
  <div class="meta">資料日期 {html.escape(d.get("date", ""))}<span>成交量 {fmt_volume(d.get("volume", 0))}</span>{ytd_cell}</div>
  <div class="pricerow">
    <span class="price mono {cls}">{fmt_price(d.get("close", 0))}</span>
    <span class="chg mono {cls}">{sign} {fmt_price(abs(d.get("change", 0)))} ({abs(d.get("change_pct", 0)):,.2f}%)</span>
  </div>
</a>''')
    return '\n'.join(cards)


# ---------------------------------------------------------------- 熱門股

def build_hot_section(hot_data: dict) -> str:
    """回傳熱門股四榜的 HTML（含 tab + panel）。"""
    def hot_row(r, show_industry=False):
        sym = r['symbol']
        link = f'{sym}.html' if sym in TICKERS else '#'
        cls = perf_class(r['change_pct'])
        amp = fmt_amp(r.get('amplitude'))
        ind = html.escape(r.get('industry', '')) if r.get('industry') else ''
        ind_cell = f'<span class="hind">{ind}</span>' if ind else ''
        return (
            f'<a class="hrow" href="{link}">'
            f'  <span class="hrank">{r["rank"]}</span>'
            f'  <span class="hcode">{sym}</span>'
            f'  <span class="hname">{html.escape(r["name"])} {ind_cell}<em class="mkt">{r["market"]}</em></span>'
            f'  <span class="hprice {cls}">{fmt_price(r["close"])}</span>'
            f'  <span class="hchg {cls}">{fmt_signed(r["change_pct"])}</span>'
            f'  <span class="hamp">{amp}</span>'
            f'  <span class="hvol">{fmt_volume(r["volume"])}</span>'
            f'  <span class="hamt">{fmt_amount(r["amount"])}</span>'
            f'</a>'
        )
    panels = []
    for key, label in [
        ('amount_top10', '金額榜'),
        ('trades_top10', '活躍榜'),
        ('up_top10', '漲幅榜'),
        ('down_top10', '跌幅榜'),
    ]:
        recs = hot_data.get(key, []) or []
        show_ind = (key == 'amount_top10')  # 只有金額榜前 10 顯示產業
        rows = [hot_row(r, show_industry=show_ind) for r in recs]
        panel = '<div class="panel active" id="panel-' + key + '">' + ('\n'.join(rows) or '<div style="text-align:center; padding:24px; color:#8b9bb4;">無資料</div>') + '</div>'
        panels.append(panel)
    tabs_html = '<div class="tabs">' + ''.join(
        f'<button class="tab active" data-t="{key}">{label}</button>'
        for key, label in [('amount_top10', '金額榜'), ('trades_top10', '活躍榜'),
                           ('up_top10', '漲幅榜'), ('down_top10', '跌幅榜')]
    ) + '</div>'
    return f'''{tabs_html}
{''.join(panels)}
<script>
  (function() {{
    const tabs = document.querySelectorAll('.tabs button');
    const panels = document.querySelectorAll('.panel');
    tabs.forEach(tab => {{
      tab.addEventListener('click', () => {{
        tabs.forEach(t => t.classList.remove('active'));
        panels.forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        const panel = document.getElementById('panel-' + tab.dataset.t);
        if (panel) panel.classList.add('active');
      }});
    }});
  }})();
</script>'''


# ---------------------------------------------------------------- 生成首頁（自訂股 + 熱門股）

def build_index(records: dict, hot_data: dict) -> str:
    custom_html = build_custom_cards(records)
    hot_html = build_hot_section(hot_data)
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    twse_date = html.escape(str(hot_data.get('twse_date', '')))
    tpex_date = html.escape(str(hot_data.get('tpex_date', '')))
    counts = hot_data.get('counts', {})
    qualifying = counts.get('qualifying', '?')
    return f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AutoStock 股票儀表板</title>
<style>
  :root {{
    --bg: #0b1120;
    --card: #111a2e;
    --card2: #16213a;
    --border: #22304f;
    --text: #e6edf7;
    --muted: #8b9bb4;
    --up: #ef4444;
    --down: #22c55e;
    --flat: #f59e0b;
    --accent: #38bdf8;
    --chip: #1d2a47;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: radial-gradient(1200px 500px at 80% -10%, #16233f 0%, var(--bg) 55%) fixed;
    color: var(--text);
    font-family: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif;
    min-height: 100vh;
    padding: 36px 20px 48px;
  }}
  .wrap {{ max-width: 1080px; margin: 0 auto; }}
  .mono {{ font-variant-numeric: tabular-nums; font-family: "JetBrains Mono", "Consolas", monospace; }}
  header.hero {{
    display: flex; justify-content: space-between; align-items: flex-end;
    gap: 16px; flex-wrap: wrap;
    margin-bottom: 26px;
  }}
  header h1 {{ font-size: 30px; font-weight: 800; letter-spacing: .5px; }}
  header h1 span {{ color: var(--accent); }}
  header p {{ color: var(--muted); font-size: 14px; margin-top: 6px; line-height: 1.7; max-width: 560px; }}
  .stamp {{
    color: var(--muted); font-size: 13px;
    background: var(--chip); border: 1px solid var(--border);
    padding: 6px 14px; border-radius: 999px;
  }}
  .section {{ margin-bottom: 40px; }}
  .sec-title {{
    font-size: 20px;
    font-weight: 700;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 10px;
  }}
  .sec-title .stamp {{ font-size: 12px; padding: 4px 10px; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
  }}
  .card {{
    display: flex; flex-direction: column; gap: 12px;
    background: linear-gradient(135deg, var(--card) 0%, var(--card2) 100%);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 20px 22px;
    color: inherit;
    text-decoration: none;
    transition: transform .15s ease, border-color .15s ease;
  }}
  .card:hover {{ transform: translateY(-3px); border-color: var(--accent); }}
  .card .row1 {{ display: flex; align-items: center; gap: 10px; }}
  .card .ticker {{
    background: var(--accent); color: #06121f;
    font-weight: 700; font-size: 13px;
    padding: 2px 10px; border-radius: 999px;
  }}
  .card .industry {{ color: var(--muted); font-size: 13px; }}
  .card h3 {{ font-size: 21px; font-weight: 700; }}
  .card h3 small {{ color: var(--muted); font-size: 12px; font-weight: 400; margin-left: 8px; }}
  .card .pricerow {{
    display: flex; align-items: baseline; justify-content: space-between;
    border-top: 1px solid var(--border); padding-top: 12px; margin-top: auto;
  }}
  .card .price {{ font-size: 26px; font-weight: 800; }}
  .card .chg {{ font-size: 14px; font-weight: 600; }}
  .card .meta {{ color: var(--muted); font-size: 12px; }}
  .card .meta span {{ display: block; margin-top: 2px; }}
  .up {{ color: var(--up); }} .down {{ color: var(--down); }} .flat {{ color: var(--flat); }}
  .card .price.up, .card .chg.up {{ color: var(--up); }}
  .card .price.down, .card .chg.down {{ color: var(--down); }}

  /* 熱門股面板 */
  .tabs {{
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }}
  .tabs button {{
    flex: 1;
    padding: 12px 0;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text);
    font-weight: 600;
    cursor: pointer;
    transition: background .2s;
  }}
  .tabs button.active {{
    background: var(--accent);
    color: #06121f;
  }}
  .panel {{
    display: none;
  }}
  .panel.active {{
    display: block;
  }}
  .hrow {{
    display: flex;
    align-items: center;
    padding: 12px 0;
    border-bottom: 1px solid var(--border);
    text-decoration: none;
    color: inherit;
  }}
  .hrow:last-child {{ border-bottom: none; }}
  .hrow:hover {{ background: rgba(56,189,248,0.06); }}
  .hrank {{
    min-width: 28px;
    font-weight: 700;
    text-align: right;
    margin-right: 8px;
    font-size: 14px;
    color: var(--muted);
  }}
  .hcode {{
    min-width: 56px;
    font-weight: 600;
    font-family: monospace;
  }}
  .hname {{
    flex: 1;
    min-width: 0;
  }}
  .hprice {{
    min-width: 72px;
    text-align: right;
    font-weight: 700;
    margin-left: 4px;
  }}
  .hchg {{
    min-width: 68px;
    text-align: right;
    font-weight: 600;
    margin-left: 4px;
  }}
  .hvol, .hamt {{
    min-width: 80px;
    text-align: right;
  }}
  .hamp {{
    min-width: 64px;
    text-align: right;
    font-variant-numeric: tabular-nums;
  }}
  .hind {{
    font-size: 12px;
    color: var(--accent);
    opacity: 0.9;
    margin-right: 4px;
    font-style: normal;
  }}
  .mkt {{
    font-size: 12px;
    opacity: 0.8;
    margin-left: 4px;
  }}
  footer {{
    margin-top: 30px;
    text-align: center;
    color: #5b6c88;
    font-size: 12px;
    line-height: 1.8;
  }}
  @media (max-width: 620px) {{
    .cards {{ grid-template-columns: repeat(2, 1fr); }}
  }}
</style>
</head>
<body>
<div class="wrap">

  <header class="hero">
    <div>
      <h1>Auto<span>Stock</span> 儀表板</h1>
      <p>台股每日收盤自動更新：即時收盤價、漲跌幅、近 5 日走勢與投資關注重點，由 Hermes AI Agent 每日排程自動生成並推送。</p>
    </div>
    <span class="stamp">生成時間：{now}</span>
  </header>

  <section class="section">
    <h2 class="sec-title">🔶 我的自訂股</h2>
    <div class="cards">
      {custom_html}
    </div>
  </section>

  <section class="section">
    <h2 class="sec-title">🔥 今日熱門股 <span class="stamp">上市 {twse_date} ・ 上櫃 {tpex_date} ・ 成交額 ≥1 億（共 {qualifying} 檔符合門檻）</span></h2>
    {hot_html}
  </section>

  <footer>
    數據來源：臺灣證券交易所 (TWSE)、金融櫃買交易所 (TPEx) 公開 API ｜ 每日 16:00 自動更新<br>
    本頁由 Hermes AI Agent 自動生成，僅供資訊參考，不構成投資建議
  </footer>

</div>
</body>
</html>
'''


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
            if os.path.exists(path):
                with open(path, encoding='utf-8') as f:
                    records[sym] = json.load(f)
                print(f'[FALLBACK] {sym} 使用 data/{sym}.json 舊資料重繪')

    # 產生各股頁面
    for sym, d in records.items():
        page = build_stock_page(d)
        with open(os.path.join(REPO_ROOT, f'{sym}.html'), 'w', encoding='utf-8') as f:
            f.write(page)
        print(f'[PAGE] {sym}.html')

    # 產生熱門股資料（寫入 data/hot_stocks.json）
    print('--- building hot stocks ---')
    hot_data = fetch_market.build_hot(out_path=os.path.join(DATA_DIR, 'hot_stocks.json'))
    print(f'[HOT]  TWSE {hot_data["counts"].get("twse",0)} + TPEx {hot_data["counts"].get("tpex",0)} → {hot_data["counts"].get("qualifying",0)} qualifying')

    # 產生 index（含自訂股 + 熱門股）
    with open(os.path.join(REPO_ROOT, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(build_index(records, hot_data))
    print('[PAGE] index.html')

    if failed:
        print(f'WARN: 以下代號本次抓取失敗（已用舊資料重繪）: {failed}')
    print('DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())