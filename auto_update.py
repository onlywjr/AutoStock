#!/usr/bin/env python3
"""
auto_update.py — AutoStock 每日自動更新流水線（供 Hermes cron 排程呼叫）

流程:
  1. python generate_all.py   （抓取六檔股票最新資料 + 重繪 .html / index.html）
  2. git add 相關檔案 → commit → push origin master
     - 若本次無任何檔案變化（例如休市日資料全同），則跳過 commit
     - push 失敗會重試 2 次
  3. 印出摘要（供排程交付）
"""
import os, sys, subprocess, datetime

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
GIT = ['git', '-C', REPO_ROOT]


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, **kw)


def main():
    print(f'=== AutoStock auto-update {datetime.datetime.now():%Y-%m-%d %H:%M} ===')

    # 1) 重新生成頁面
    r = run([sys.executable, os.path.join(REPO_ROOT, 'generate_all.py')])
    print(r.stdout.strip())
    if r.returncode != 0:
        print(f'ERROR: generate_all.py exit={r.returncode}\n{r.stderr}')
        return 1

    # 2) git 狀態
    st = run(GIT + ['status', '--porcelain'])
    changed = st.stdout.strip()
    if not changed:
        print('NO CHANGE: 資料與頁面均無變化，跳過 commit（可能為休市日）')
        return 0

    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    r = run(GIT + ['add', 'data', 'templates', 'index.html', '*.html',
                   'fetch_stock.py', 'generate_all.py', 'auto_update.py',
                   'ticker_company.json'])
    if r.returncode != 0:
        print(f'ERROR: git add 失敗: {r.stderr}')
        return 1

    r = run(GIT + ['commit', '-m', f'Auto refresh stock dashboards ({now})'])
    if r.returncode != 0:
        print(f'ERROR: git commit 失敗: {r.stderr}')
        return 1
    print(r.stdout.strip())

    for attempt in (1, 2, 3):
        r = run(GIT + ['push', 'origin', 'master'], timeout=300)
        if r.returncode == 0:
            print('PUSHED: 已推送至 GitHub origin/master')
            return 0
        print(f'PUSH 失敗 (第 {attempt} 次): {r.stderr.strip()[:300]}')
    print('ERROR: push 三次皆失敗，請手動檢查')
    return 1


if __name__ == '__main__':
    sys.exit(main())
