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
LOCK_PATH = os.path.join(REPO_ROOT, '.process_issues.lock')
LOCK_TIMEOUT_S = 900  # 等鎖最久 15 分鐘（generate_all.py 可能很慢）
LOG_FILE = os.path.join(REPO_ROOT, 'logs', 'process_issues.log')


class _Tee:
    """同時寫到 console 與 log 檔案。"""
    def __init__(self, *streams):
        self.streams = streams
    def write(self, data):
        for s in self.streams:
            try:
                s.write(data)
            except Exception:
                pass
    def flush(self):
        for s in self.streams:
            try:
                s.flush()
            except Exception:
                pass


def acquire_lock():
    """Windows 排他鎖：避免排程/手動同時執行造成 git 衝突。"""
    import msvcrt, time
    f = open(LOCK_PATH, 'w')
    deadline = time.time() + LOCK_TIMEOUT_S
    while True:
        try:
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            f.write(str(os.getpid()))
            f.flush()
            return f
        except OSError:
            if time.time() >= deadline:
                f.close()
                return None
            time.sleep(5)


def release_lock(f):
    if f is None:
        return
    try:
        import msvcrt
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    except Exception:
        pass
    f.close()


def run(cmd, timeout=120, env=None):
    """subprocess：子程序強制 UTF-8（PYTHONUTF8），避免 CP950 編碼崩潰。"""
    base_env = {**os.environ, 'PYTHONUTF8': '1'}
    if env:
        base_env.update(env)
    return subprocess.run(cmd, capture_output=True, text=True,
                           cwd=REPO_ROOT, timeout=timeout, env=base_env,
                           encoding='utf-8', errors='replace')


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
        entry = {'name': name, 'industry': industry, 'desc': '', 'catalysts': []}
        if full_name and full_name != name:
            entry['full_name'] = full_name
        data[ticker] = entry
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


STOCK_ID_FILE = os.path.join(REPO_ROOT, 'stock_id.json')


def _fetch_company_info(ticker: str) -> tuple:
    """從 stock_id.json（上市+上櫃代號對照表）查詢股票名稱。
    回傳 (name, full_name, industry)；找不到回傳 Unknown。"""
    try:
        with open(STOCK_ID_FILE, encoding='utf-8') as f:
            entries = json.load(f)
        for item in entries:
            if str(item.get('code', '')).zfill(4) == ticker:
                name = str(item.get('name', '')).strip()
                if name:
                    # 產業本對照表沒提供，先標「—」；full_name 留空讓頁面以簡稱顯示
                    return name, '', '—'
    except Exception:
        pass
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
    issues = list_issues()
    if not issues:
        print('無待處理 Issue')   # 僅 console（排程的 bat 會丟棄此輸出）；不寫 log
        return 0

    # 有工作要做 → 將後續處理明細寫入 log
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    logf = open(LOG_FILE, 'a', encoding='cp950', errors='replace')
    real_stdout = sys.stdout
    sys.stdout = _Tee(real_stdout, logf)

    print(f'=== process_issues {datetime.datetime.now():%Y-%m-%d %H:%M} {"(dry-run)" if dry_run else ""} ===')
    print(f'找到 {len(issues)} 個待處理 Issue:')
    for issue in issues:
        print(f'  #{issue["number"]}: {issue["title"]}')

    if dry_run:
        print('(dry-run 模式，不執行修改)')
        sys.stdout = real_stdout
        logf.close()
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
            sys.stdout = real_stdout
            logf.close()
            return 1
        if not commit_and_push():
            print('[ERROR] push 失敗')
            sys.stdout = real_stdout
            logf.close()
            return 1

    print('DONE')
    sys.stdout = real_stdout
    logf.close()
    return 0


if __name__ == '__main__':
    lock = acquire_lock()
    if lock is None:
        print('LOCK: 其他執行中鎖定 .process_issues.lock（已等待 15 分鐘），本次跳過')
        sys.exit(0)
    try:
        sys.exit(main())
    finally:
        release_lock(lock)
