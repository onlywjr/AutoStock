import sys, json, subprocess, os

tickers = ['8299', '1434', '6213', '6139', '2327', '2330']
repo_dir = r'C:\My_Project\Hermes\[工作區]\AutoStock'
print(f'Working in {repo_dir}')

# Ensure we are in the repo directory
os.chdir(repo_dir)

# Load live_data.json if exists
live = {}
if os.path.exists('live_data.json'):
    with open('live_data.json', encoding='utf-8') as f:
        live = json.load(f)

# For each ticker, call fetch_unverified.py
for t in tickers:
    cmd = [sys.executable, 'fetch_unverified.py', t]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        live[t] = {
            'price': data.get('price'),
            'changePct': data.get('changePct'),
            'volume': data.get('volume')
        }
        print(f'[UPDATE] {t}: price={data["price"]}, change={data["changePct"]}%')
    else:
        print(f'[FAIL] {t}: {result.stderr}')
        live[t] = {'price': None, 'changePct': None, 'volume': None}

# Write back
with open('live_data.json', 'w', encoding='utf-8') as f:
    json.dump(live, f, ensure_ascii=False, indent=2)
print('\n[INFO] live_data.json updated')
