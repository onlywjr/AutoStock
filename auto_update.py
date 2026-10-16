#!/usr/bin/env python3
"""
auto_update.py — AutoStock 每日自動更新流水線（供 Hermes cron 排程呼叫）

流程:
  1. python generate_all.py   （抓取六檔股票最新資料 + 重繪 .html / index.html）
  2. git add -A → commit → push origin master
     - 無任何檔案變化（休市日資料全同）→ 自動跳過 commit
     - 「nothing to commit」一律視為成功（冪等，避免與並行執行碰撞而誤報錯）
     - push 被拒（遠端有更新）→ 自動 rebase 後重試
  3. 全程持有排他鎖，手動執行與排程同時觸發會互斥，不會碰撞

退出碼: 0 = 成功或無變更；1 = 真正失敗
"""
import os, sys, subprocess, datetime, time

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
GIT = ['git', '-C', REPO_ROOT]
LOCK_PATH = os.path.join(REPO_ROOT, '.autostock.lock')
LOCK_TIMEOUT_S = 300          # 等鎖最久 5 分鐘
REBASE_ENV = {**os.environ, 'GIT_EDITOR': 'true', 'GIT_SEQUENCE_EDITOR': 'true'}


def run(cmd, timeout=600, env=None):
    return subprocess.run(cmd, capture_output=True, text=True,
                           cwd=REPO_ROOT, timeout=timeout, env=env)


# ---------------------------------------------------------------- 互斥鎖（Windows）

def acquire_lock():
    import msvcrt
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


def do_rebase(origin_master='origin/master'):
    """非互動 rebase；衝突時一律採本地（重構版）內容。"""
    rr = run(GIT + ['rebase', '--no-edit', origin_master], env=REBASE_ENV)
    if rr.returncode == 0:
        return True
    # 有衝突 → 逐檔採「被 apply 的 commit」版本（--theirs）
    conflicted = run(GIT + ['diff', '--name-only', '--diff-filter=U']).stdout.splitlines()
    for line in conflicted:
        run(GIT + ['checkout', '--theirs', '--', line])
        run(GIT + ['add', line])
    run(GIT + ['rebase', '--continue'], env=REBASE_ENV)
    return run(GIT + ['status', '--porcelain']).stdout.strip() == ''


# ---------------------------------------------------------------- git 操作

def commit(message):
    r = run(GIT + ['commit', '-m', message])
    if r.returncode == 0:
        return True, r.stdout.strip()
    out = (r.stdout + r.stderr)
    if 'nothing to commit' in out:
        return True, 'nothing to commit（無變更）'
    return False, out.strip()


def push(retry=3):
    for attempt in range(1, retry + 1):
        r = run(GIT + ['push', 'origin', 'master'], timeout=300)
        if r.returncode == 0:
            return True, 'pushed'
        out = r.stderr.strip()
        if 'rejected' in out or 'fetch first' in out or 'non-fast-forward' in out:
            run(GIT + ['fetch', 'origin', 'master'])
            do_rebase()
            continue  # 重試 push
        print(f'PUSH 失敗 (第 {attempt} 次): {out[:300]}')
        time.sleep(5)
    return False, 'push 三次皆失敗'


def main():
    print(f'=== AutoStock auto-update {datetime.datetime.now():%Y-%m-%d %H:%M} ===')

    lock = acquire_lock()
    if lock is None:
        print('ERROR: 其他執行中鎖定 .autostock.lock（已等待 5 分鐘），本次跳過')
        return 1

    try:
        # 1) 重新生成頁面
        r = run([sys.executable, os.path.join(REPO_ROOT, 'generate_all.py')], timeout=900)
        print(r.stdout.strip())
        if r.returncode != 0:
            print(f'ERROR: generate_all.py exit={r.returncode}\n{r.stderr.strip()[:500]}')
            return 1

        # 2) 若落後遠端，先同步（避免 push 被拒）
        run(GIT + ['fetch', 'origin', 'master'])
        behind = run(GIT + ['rev-list', '--count', 'HEAD..origin/master']).stdout.strip()
        if behind not in ('0', ''):
            if do_rebase():
                print(f'已同步遠端 {behind} 個 commit')
            else:
                print('ERROR: rebase 遠端失敗，跳過本次 push')
                return 1

        # 3) 全部暫存（含 README、模板、資料、頁面、腳本）
        r = run(GIT + ['add', '-A'])
        if r.returncode != 0:
            print(f'ERROR: git add 失敗: {r.stderr.strip()[:300]}')
            return 1

        # 4) 無變更 → 成功跳過
        if run(GIT + ['diff', '--cached', '--quiet']).returncode == 0:
            print('NO CHANGE: 資料與頁面均無變化，跳過 commit（可能為休市日）')
            return 0

        # 5) commit（nothing to commit 視為成功）
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
        ok, msg = commit(f'Auto refresh stock dashboards ({now})')
        if not ok:
            print(f'ERROR: git commit 失敗: {msg[:300]}')
            return 1
        print(f'COMMIT: {msg.splitlines()[0] if msg else ""}')

        # 6) push
        ok, msg = push()
        if not ok:
            print(f'ERROR: {msg}，請手動檢查')
            return 1
        print('PUSHED: 已推送至 GitHub origin/master')
        return 0
    finally:
        release_lock(lock)


if __name__ == '__main__':
    sys.exit(main())
