import json, sys, subprocess
tickers = ["8299", "1434", "6213", "6139"]
live = {}
for t in tickers:
    cmd = [sys.executable, "fetch_unverified.py", t]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        data = json.loads(result.stdout)
        live[t] = {"price": data.get("price"), "changePct": data.get("changePct"), "volume": data.get("volume")}
    else:
        live[t] = {"price": None, "changePct": None, "volume": None}
with open("live_data.json", "w", encoding="utf-8") as f:
    json.dump(live, f, ensure_ascii=False, indent=2)
print("[UPDATE] Updated live_data.json")