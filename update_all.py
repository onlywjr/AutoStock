import subprocess, json, os, datetime, sys

repo_dir = r'C:/My_Project/Hermes/[工作區]/AutoStock'
os.chdir(repo_dir)

# Only real ticker dashboards (exclude index.html, helpers, examples)
html_files = [f for f in os.listdir('.') if f.endswith('.html') and f.lower() != 'index.html']
tickers = [os.path.splitext(f)[0] for f in html_files]
print(f'[DEBUG] Found tickers: {tickers}')

results = {}
for t in tickers:
    r = subprocess.run([sys.executable, 'fetch_stock.py', t], capture_output=True, text=True, cwd=repo_dir)
    if r.returncode == 0:
        try:
            quote = json.loads(r.stdout.strip())
            results[t] = quote
            print(f'[DEBUG] {t}: price={quote["price"]} change={quote["changePct"]:.2f}% vol={quote["volume"]}')
        except json.JSONDecodeError:
            print(f'[DEBUG] {t}: JSON parse failed: {r.stdout[:200]}')
    else:
        print(f'[DEBUG] {t}: fetch_stock.py failed: {r.stderr[:200]}')

# Save live_data.json
with open('live_data.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print('[DEBUG] Saved live_data.json')

# Generate per-ticker dashboards
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
for t in tickers:
    q = results.get(t, {'price': 0, 'changePct': 0})
    price = q.get('price', 0)
    change = q.get('changePct', 0)
    price_str = f"{price:,.2f}"
    arrow = '▲' if change >= 0 else '▼'
    change_str = f"{arrow} {abs(change):.2f}%"
    vol = q.get('volume', 0)
    vol_str = f"{vol:,}" if vol else 'N/A'
    html = f'''<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<title>{t} 股票儀表板</title>
<style>
  body {{ font-family: system-ui, sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem; background: #f8fafc; color: #1e293b; }}
  h1 {{ border-bottom: 2px solid #3b82f6; padding-bottom: 0.5rem; }}
  .price {{ font-size: 2rem; font-weight: bold; margin: 1rem 0; }}
  .up {{ color: #ef4444; }} .down {{ color: #22c55e; }}
  .meta {{ color: #64748b; font-size: 0.9rem; }}
</style>
</head>
<body>
<h1>📊 {t} 股票儀表板</h1>
<p class="meta">更新時間：{now}</p>
<p class="price">{price_str} NTD</p>
<p class="{'up' if change >= 0 else 'down'}">{change_str}</p>
<p class="meta">成交量：{vol_str}</p>
</body>
</html>'''
    with open(f'{t}.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'[DEBUG] Wrote {t}.html')

# Generate index.html
links = '\n'.join([
    f'    <li><a href="{t}.html">{t}.html</a> — 收盤價：{results[t]["price"]:,.2f} NTD / 漲跌幅：{"▲" if results[t]["changePct"]>=0 else "▼"} {abs(results[t]["changePct"]):.2f}% / 更新：{now}</li>'
    for t in tickers
])
index_content = f'''<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"><title>AutoStock Dashboard Index</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; background: #f8fafc; color: #1e293b;">
  <h1 style="border-bottom: 2px solid #3b82f6; padding-bottom: 0.5rem;">📊 股票儀表板索引</h1>
  <p style="color: #64748b; margin-bottom: 1.5rem;">更新時間：{now}</p>
  <ul style="list-style: none; padding: 0;">
{links}
  </ul>
</body></html>'''
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(index_content)
print('[DEBUG] Wrote index.html')
print('[DONE] All dashboards updated.')