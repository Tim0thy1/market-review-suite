"""
清理过期报告 —— 删除本地和GitHub上超过7个交易日的报告目录。
保留最近7个交易日的报告，重新生成 index.html。

用法: python cleanup_old_reports.py --dry-run
      python cleanup_old_reports.py
"""
import os, re, shutil, subprocess, sys
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
DIR_PATTERN = re.compile(
    r'^(美股|A股)/(美股复盘|A股复盘|A股盘前分析|A股视频提示词)-(\d{8})$'
)

def count_trading_days_back(n):
    """从今天往前数n个交易日（仅跳过周末），返回日期字符串列表"""
    today = datetime.now()
    dates = []
    d = today
    while len(dates) < n:
        if d.weekday() < 5:  # Mon-Fri
            dates.append(d.strftime('%Y%m%d'))
        d -= timedelta(days=1)
    return dates

def get_keep_cutoff():
    """获取保留截止日期：7个交易日前的日期"""
    keep_dates = count_trading_days_back(7)
    return min(keep_dates)  # 这个日期及之后的保留

def scan_report_dirs():
    """扫描所有报告目录，返回 (market, type, date_str, full_path) 列表"""
    dirs = []
    for market in ('美股', 'A股'):
        market_path = os.path.join(ROOT, market)
        if not os.path.isdir(market_path):
            continue
        for entry in os.listdir(market_path):
            full_path = os.path.join(market_path, entry)
            if not os.path.isdir(full_path):
                continue
            rel_path = f"{market}/{entry}"
            m = DIR_PATTERN.match(rel_path)
            if m:
                dirs.append({
                    'market': m.group(1),
                    'type': m.group(2),
                    'date_str': m.group(3),
                    'full_path': full_path,
                    'rel_path': rel_path,
                })
    return dirs

def delete_from_github(repo_path, dry_run=False):
    """通过git删除GitHub上的目录"""
    if dry_run:
        print(f"  [DRY-RUN] 会从GitHub删除: {repo_path}/")
        return True
    
    try:
        # git rm -r 目录
        result = subprocess.run(
            ['git', 'rm', '-r', '--quiet', repo_path],
            cwd=ROOT,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"  ✓ 已从git暂存区移除: {repo_path}/")
            return True
        else:
            print(f"  ✗ git rm失败: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ✗ git rm异常: {e}")
        return False

def delete_local(repo_path, dry_run=False):
    """删除本地目录"""
    full_path = os.path.join(ROOT, repo_path)
    if not os.path.isdir(full_path):
        return True
    if dry_run:
        print(f"  [DRY-RUN] 会删除本地目录: {full_path}")
        return True
    try:
        shutil.rmtree(full_path)
        print(f"  ✓ 已删除本地目录: {repo_path}/")
        return True
    except Exception as e:
        print(f"  ✗ 删除本地目录失败: {e}")
        return False

def regenerate_index(dry_run=False):
    """重新生成index.html"""
    if dry_run:
        print("  [DRY-RUN] 会重新生成 index.html")
        return True
    try:
        result = subprocess.run(
            ['python', 'generate_index.py'],
            cwd=ROOT,
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"  ✓ index.html 已重新生成")
            return True
        else:
            print(f"  ✗ generate_index.py 失败: {result.stderr.strip()}")
            return False
    except Exception as e:
        print(f"  ✗ generate_index.py 异常: {e}")
        return False

def main():
    dry_run = '--dry-run' in sys.argv
    
    cutoff = get_keep_cutoff()
    print(f"保留截止日期: {cutoff}（保留此日期及之后的报告）")
    print(f"{'='*60}")
    
    all_dirs = scan_report_dirs()
    to_delete = [d for d in all_dirs if d['date_str'] < cutoff]
    to_keep = [d for d in all_dirs if d['date_str'] >= cutoff]
    
    print(f"发现 {len(all_dirs)} 个报告目录")
    print(f"保留 {len(to_keep)} 个，删除 {len(to_delete)} 个")
    print()
    
    if not to_delete:
        print("无需清理。")
        if not dry_run:
            regenerate_index(dry_run=False)
        return
    
    # 先git rm所有需要删除的目录
    print("=== 从GitHub删除 ===")
    all_success = True
    for d in sorted(to_delete, key=lambda x: x['rel_path']):
        print(f"处理: {d['rel_path']}/")
        ok = delete_from_github(d['rel_path'], dry_run=dry_run)
        if not ok:
            all_success = False
    
    # 再删除本地目录
    print("\n=== 删除本地目录 ===")
    for d in sorted(to_delete, key=lambda x: x['rel_path']):
        ok = delete_local(d['rel_path'], dry_run=dry_run)
        if not ok:
            all_success = False
    
    if not dry_run and all_success:
        # 重新生成index.html
        print("\n=== 重新生成 index.html ===")
        regenerate_index(dry_run=False)
        
        # 提交并推送
        print("\n=== 提交并推送至GitHub ===")
        try:
            subprocess.run(
                ['git', 'add', 'index.html'],
                cwd=ROOT, capture_output=True, text=True, timeout=15
            )
            commit_result = subprocess.run(
                ['git', 'commit', '-m', f'清理 {len(to_delete)} 个过期报告目录'],
                cwd=ROOT, capture_output=True, text=True, timeout=15
            )
            if commit_result.returncode == 0:
                push_result = subprocess.run(
                    ['git', 'push', 'origin', 'master'],
                    cwd=ROOT, capture_output=True, text=True, timeout=60
                )
                if push_result.returncode == 0:
                    print(f"  ✓ 已推送至GitHub")
                else:
                    print(f"  ✗ 推送失败: {push_result.stderr.strip()}")
            else:
                print(f"  提交: {commit_result.stdout.strip()}")
        except Exception as e:
            print(f"  ✗ git操作异常: {e}")
    
    print(f"\n完成。{'（模拟运行，未实际删除）' if dry_run else ''}")

if __name__ == '__main__':
    main()