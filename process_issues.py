#!/usr/bin/env python3
"""
process_issues.py — 檢查並處理 GitHub Issue（label: bot:stock-update）

流程:
  1. 用 gh CLI 列出所有 open 的 bot:stock-update Issues
  2. 解析每個 Issue 的標題（格式: "Add 1101" 或 "Remove 2330"）
  3. 更新 ticker_company.json（新增或移除對應代號）
  4. 執行 generate_all.py 重新產生頁面
  5. git add / commit / push 到 origin/master
  6. 關閉 Issue

使用方式:
    python process_issues.py            # 處理所有待處理 Issue
    python process_issues.py --dry-run # 只列出，不實際修改

排程建議:
    Windows Task Scheduler: 每 5~10 分鐘執行一次
    命令: python "C:\My_Project\Hermes\[工作區]\AutoStock\process_issues.py"
"""
import json, os, re, sys, subprocess, datetime

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
TICKERS_FILE = os.path.join(REPO_ROOT, 'ticker_company.json')
GIT = ['git', '-C', REPO_ROOT]
GH = ['gh', '-R', 'onlywjr/AutoStock']
LABEL = 'bot:stock-update'


def run(cmd, timeout=120, env=None):
    return subprocess.run(cmd, capture_output=True, text=True,
                           cwd=REPO_ROOT, timeout=timeout, env=env)


def list_issues() -> list:
    """列出所有 open 的 bot:stock-update Issues。"""
    r = run(GH + ['issue', 'list',
                  '--label', LABEL,
                  '--state', 'open',
                  '--json', 'number,title'])
    if r.returncode != 0:
        print(f'ERROR: gh issue list failed: {r.stderr.strip()[:300]}')
        return []
    try:
        return json.loads(r.stdout) if r.stdout.strip() else []
    except json.JSONDecodeError:
        print(f'ERROR: 無法解析 gh 輸出: {r.stdout[:200]}')
        return []


def parse_title(title: str) -> tuple | None:
    """解析 issue 標題，回傳 (action, ticker) 或 None。"""
    m = re.match(r'^(Add|Remove)\s+(\d{4})$', title.strip(), re.IGNORECASE)
    if m:
        return m.group(1).lower(), m.group(2)
    return None


def update_tickers(action: str, ticker: str) -> bool:
    """更新 ticker_company.json。回傳 True 表示有變化。"""
    try:
        with open(TICKERS_FILE, encoding='utf-8') as f:
            data = json.load(f)
        if not isinstance(data, dict):
            data = {}
    except Exception:
        data = {}

    if action == 'add':
        if ticker in data:
            print(f'[SKIP] {ticker} 已存在於 ticker_company.json')
            return False
        # 嘗試從 TPEx API 抓取公司名稱（若為上櫃股）
        name, full_name, industry = _fetch_company_info(ticker)
        data[ticker] = {
            'name': name,
            'full_name': full_name,
            'industry': industry,
            'desc': '',
            'catalysts': [],
        }
        print(f'[ADD] 已新增 {ticker} ({name}) 到 ticker_company.json')
    elif action == 'remove':
        if ticker not in data:
            print(f'[SKIP] {ticker} 不存在於 ticker_company.json，跳過')
            return False
        del data[ticker]
        print(f'[REMOVE] 已移除 {ticker} 從 ticker_company.json')
    else:
        print(f'[ERROR] 未知 action: {action}')
        return False

    with open(TICKERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return True


def _fetch_company_info(ticker: str) -> tuple:
    """嘗試從 TPEx API 抓取公司名稱與產業（若為上櫃股）。
    回傳 (name, full_name, industry)。"""
    import urllib.request, ssl
    ctx = ssl._create_unverified_context()
    # 先試 TPEx API
    try:
        url = (f'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes'
               f'?l=zh-tw&d=2026-10-01&se=EW')
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            rows = json.loads(resp.read().decode('utf-8'))
        for item in rows:
            if str(item.get('SecuritiesCompanyCode', '')).zfill(4) == ticker:
                name = item.get('CompanyName', '')
                return name, name, '上櫃'
    except Exception:
        pass
    # 若不在 TPEx，則回傳 Unknown
    return 'Unknown', 'Unknown', 'Unknown'


def regenerate() -> bool:
    """執行 fetch_institutional.py + generate_all.py 重新產生頁面。"""
    # 先更新法人買賣超資料
    r = run([sys.executable, os.path.join(REPO_ROOT, 'fetch_institutional.py')],
            timeout=300)
    if r.returncode != 0:
        print(f'[WARN] fetch_institutional.py 失敗 (exit={r.returncode})，繼續產生頁面')
        print(r.stderr.strip()[:300])
    else:
        print('[OK] fetch_institutional.py 完成')

    # 再產生頁面
    r = run([sys.executable, os.path.join(REPO_ROOT, 'generate_all.py')],
            timeout=900)
    if r.returncode != 0:
        print(f'[ERROR] generate_all.py 失敗 (exit={r.returncode})')
        print(r.stderr.strip()[:500])
        return False
    print('[OK] generate_all.py 完成')
    return True


def commit_and_push() -> bool:
    """git add / commit / push。"""
    # 若無變更，跳過
    status = run(GIT + ['diff', '--quiet'])
    if status.returncode == 0:
        print('[INFO] 無檔案變化，跳過 commit')
        return True

    run(GIT + ['add', '-A'])
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    r = run(GIT + ['commit', '-m', f'Bot: update custom stocks ({now})'])
    if r.returncode != 0:
        if 'nothing to commit' in (r.stdout + r.stderr):
            print('[INFO] nothing to commit')
            return True
        print(f'[ERROR] git commit 失敗: {r.stderr.strip()[:300]}')
        return False

    r = run(GIT + ['push', 'origin', 'master'], timeout=300)
    if r.returncode != 0:
        # 嘗試 rebase 後重試
        run(GIT + ['fetch', 'origin', 'master'])
        rr = run(GIT + ['rebase', '--no-edit', 'origin/master'],
                 env={**os.environ, 'GIT_EDITOR': 'true',
                      'GIT_SEQUENCE_EDITOR': 'true'})
        if rr.returncode != 0:
            conflicted = run(GIT + ['diff', '--name-only', '--diff-filter=U']).stdout.splitlines()
            for line in conflicted:
                run(GIT + ['checkout', '--theirs', '--', line])
                run(GIT + ['add', line])
            run(GIT + ['rebase', '--continue'],
                env={**os.environ, 'GIT_EDITOR': 'true',
                     'GIT_SEQUENCE_EDITOR': 'true'})
        r = run(GIT + ['push', 'origin', 'master'], timeout=300)
        if r.returncode != 0:
            print(f'[ERROR] git push 失敗: {r.stderr.strip()[:300]}')
            return False

    print('[OK] 已推送至 GitHub origin/master')
    return True


def close_issue(number: int, comment: str = '') -> None:
    """關閉 Issue 並（可選）留言。"""
    if comment:
        run(GH + ['issue', 'comment', str(number), '--body', comment])
    run(GH + ['issue', 'close', str(number)])
    print(f'[CLOSE] Issue #{number} 已關閉')


def main():
    dry_run = '--dry-run' in sys.argv
    print(f'=== process_issues {datetime.datetime.now():%Y-%m-%d %H:%M} {"(dry-run)" if dry_run else ""} ===')

    issues = list_issues()
    if not issues:
        print('無待處理 Issue')
        return 0

    print(f'找到 {len(issues)} 個待處理 Issue:')
    for issue in issues:
        print(f'  #{issue["number"]}: {issue["title"]}')

    if dry_run:
        print('(dry-run 模式，不執行修改)')
        return 0

    changed = False
    for issue in issues:
        number = issue['number']
        title = issue['title']
        parsed = parse_title(title)
        if not parsed:
            print(f'[SKIP] Issue #{number} 標題格式不正確: "{title}"，關閉之')
            close_issue(number, f'標題格式不正確，請使用 "Add 1101" 或 "Remove 2330"。')
            continue

        action, ticker = parsed
        print(f'--- 處理 Issue #{number}: {action} {ticker} ---')
        ok = update_tickers(action, ticker)
        if ok:
            changed = True
        # 即使沒變化也要處理（可能 Issue 是重複的）
        close_issue(number, f'已處理：{"已" + ("新增" if action == "add" else "移除") + f" {ticker}" if ok else f"{ticker} 無變化"}')

    if changed:
        if not regenerate():
            print('[ERROR] 頁面重新產生失敗，跳過 push')
            return 1
        if not commit_and_push():
            print('[ERROR] push 失敗')
            return 1

    print('DONE')
    return 0


if __name__ == '__main__':
    sys.exit(main())
