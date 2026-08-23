"""
生成 index.html —— 扫描本地报告目录，生成带完整文件列表的静态首页。
无需联网，无需 API，推送到 GitHub 即可直接访问。
"""
import os, re
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.abspath(__file__))
# 新结构：市场/类型-日期/文件
# 匹配: 美股/美股复盘-20260818/... 或 A股/A股复盘-20260819/... 等
DIR_PATTERN = re.compile(
    r'^(美股|A股)/(美股复盘|A股复盘|A股盘前分析|A股视频提示词)-(\d{8})$'
)
FILE_PATTERN = re.compile(r'\.(html|txt)$', re.I)

# 市场前缀 → 显示信息
MARKET_MAP = {
    '美股': '🇺🇸',
    'A股': '📈',
}

# 类型 → (显示标签, CSS类)
TYPE_MAP = {
    '美股复盘':    ('美股复盘', 'type-us'),
    'A股复盘':    ('A股复盘', 'type-ashare'),
    'A股盘前分析': ('盘前分析', 'type-premarket'),
    'A股视频提示词': ('视频脚本', 'type-video'),
}

# 暂不展示的类型（index.html 隐藏，文件保留在仓库；恢复展示时从集合移除即可）
EXCLUDE_TYPES = {'A股视频提示词'}

def scan():
    """扫描目录，按日期分组"""
    groups = {}
    for market in os.listdir(ROOT):
        market_path = os.path.join(ROOT, market)
        if not os.path.isdir(market_path) or market.startswith('.'):
            continue
        if market not in ('美股', 'A股'):
            continue
        for entry in os.listdir(market_path):
            full_path = os.path.join(market_path, entry)
            if not os.path.isdir(full_path):
                continue
            # 构造匹配路径: 美股/美股复盘-20260818
            rel_path = f"{market}/{entry}"
            m = DIR_PATTERN.match(rel_path)
            if not m:
                continue
            mkt, rtype, date_str = m.group(1), m.group(2), m.group(3)
            if rtype in EXCLUDE_TYPES:
                continue
            for fname in os.listdir(full_path):
                if FILE_PATTERN.search(fname):
                    date_key = date_str
                    if date_key not in groups:
                        y, mo, d = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
                        groups[date_key] = {
                            'date_obj': datetime(y, mo, d),
                            'entries': []
                        }
                    groups[date_key]['entries'].append({
                        'market': mkt,
                        'type': rtype,
                        'dirname': rel_path,
                        'fname': fname,
                    })
    return groups


def render(groups):
    today_str = datetime.now().strftime('%Y%m%d')
    yesterday_str = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d')
    sorted_dates = sorted(groups.keys(), reverse=True)

    weekdays = ['一', '二', '三', '四', '五', '六', '日']

    total_reports = 0
    markets = set()
    cards_html = ''

    for date_str in sorted_dates:
        g = groups[date_str]
        dt = g['date_obj']
        y, mo, d = dt.year, dt.month, dt.day

        # 排序：美股复盘 → A股盘前分析 → A股复盘
        type_order = ['美股复盘', 'A股盘前分析', 'A股复盘']
        g['entries'].sort(key=lambda x: type_order.index(x['type']) if x['type'] in type_order else 99)

        tag = ''
        if date_str == today_str:
            tag = '<span class="tag tag-today">今日</span>'
        elif date_str == yesterday_str:
            tag = '<span class="tag tag-past">昨日</span>'

        total_reports += len(g['entries'])

        cards_html += f'<div class="date-group"><div class="date-header">{y:04d}-{mo:02d}-{d:02d}（周{weekdays[dt.weekday()]}） {tag}</div><div class="report-grid">'

        for e in g['entries']:
            mkt_icon = MARKET_MAP.get(e['market'], '')
            type_cfg = TYPE_MAP.get(e['type'], (e['type'], ''))
            display = e['fname'].rsplit('.', 1)[0]
            markets.add(e['market'])
            repo_path = f"{e['dirname']}/{e['fname']}"
            url = f'https://htmlpreview.github.io/?https://github.com/Tim0thy1/market-review-suite/blob/master/{repo_path}'
            cards_html += f'''<a class="report-card" href="{url}" target="_blank">
          <div class="type {type_cfg[1]}">{mkt_icon} {type_cfg[0]}</div>
          <div class="title">{e['market']} · {type_cfg[0]} · {mo}月{d}日</div>
          <div class="desc">{display}</div>
          <div class="arrow">查看报告 →</div>
        </a>'''

        cards_html += '</div></div>'

    return cards_html, total_reports, len(sorted_dates), len(markets)


def generate():
    groups = scan()
    if not groups:
        print('未找到任何报告目录')
        return
    cards_html, total, days, mkt = render(groups)

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>跨市场复盘报告</title>
<style>
:root{{--bg:#f1f5f9;--card:#fff;--border:#e2e8f0;--text:#1e293b;--text2:#64748b;--accent:#1e3a5f;--accent2:#2563eb;--green:#16a34a;--amber:#d97706}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:var(--bg);color:var(--text);font-family:'Noto Sans CJK SC','Microsoft YaHei',-apple-system,sans-serif;line-height:1.6;font-size:14px;min-height:100vh}}
.container{{max-width:960px;margin:0 auto;padding:32px 20px}}
.header{{text-align:center;padding:40px 20px 32px;border-bottom:2px solid var(--accent);margin-bottom:32px}}
.header h1{{font-size:28px;font-weight:800;color:var(--accent);margin-bottom:8px;letter-spacing:1px}}
.header .subtitle{{color:var(--text2);font-size:14px}}
.header .badge{{display:inline-block;margin-top:10px;padding:4px 16px;background:var(--accent);color:#fff;border-radius:20px;font-size:12px;font-weight:600}}
.stats{{display:flex;justify-content:center;gap:32px;margin:18px 0 0}}
.stat{{text-align:center}}
.stat .num{{font-size:24px;font-weight:800;color:var(--accent2)}}
.stat .label{{font-size:12px;color:var(--text2)}}
.date-group{{margin-bottom:28px}}
.date-header{{font-size:18px;font-weight:800;color:var(--accent);margin-bottom:14px;padding-bottom:8px;border-bottom:2px solid var(--accent);display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.date-header .tag{{font-size:11px;font-weight:600;padding:2px 10px;border-radius:10px;color:#fff}}
.tag-today{{background:var(--green)}}
.tag-past{{background:var(--text2)}}
.report-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}}
.report-card{{border:1px solid var(--border);border-radius:12px;padding:18px;background:var(--card);transition:all .2s;text-decoration:none;color:var(--text);display:flex;flex-direction:column;box-shadow:0 1px 3px rgba(0,0,0,.04)}}
.report-card:hover{{transform:translateY(-2px);box-shadow:0 6px 16px rgba(30,58,95,.12);border-color:var(--accent2)}}
.report-card .type{{font-size:11px;font-weight:700;padding:2px 10px;border-radius:6px;display:inline-block;width:fit-content;margin-bottom:8px}}
.type-us{{background:#eff6ff;color:#1d4ed8}}
.type-ashare{{background:#fef2f2;color:#b91c1c}}
.type-premarket{{background:#f0fdf4;color:#15803d}}
.type-video{{background:#fffbeb;color:#92400e}}
.report-card .market-tag{{font-size:11px;font-weight:600;color:var(--text2);margin-bottom:2px}}
.report-card .title{{font-size:15px;font-weight:700;margin-bottom:6px;line-height:1.4}}
.report-card .desc{{font-size:12.5px;color:var(--text2);line-height:1.5;flex:1}}
.report-card .arrow{{color:var(--accent2);font-size:13px;margin-top:8px;font-weight:600}}
.footer{{text-align:center;padding:32px;color:var(--text2);font-size:12px;border-top:1px solid var(--border);margin-top:20px}}
@media(max-width:600px){{.report-grid{{grid-template-columns:1fr}}.stats{{gap:16px}}}}
</style>
</head>
<body>
<div class="container">

<div class="header">
<h1>跨市场复盘报告</h1>
<div class="subtitle">美股复盘 · A股复盘 · 盘前分析</div>
<div class="badge">自动同步 · 每日更新</div>
<div class="stats">
<div class="stat"><div class="num">{total}</div><div class="label">报告总数</div></div>
<div class="stat"><div class="num">{days}</div><div class="label">交易日</div></div>
<div class="stat"><div class="num">{mkt}</div><div class="label">市场</div></div>
</div>
</div>

{cards_html}

<div class="footer">
<p>market-review-suite · 跨市场复盘工具集</p>
<p>数据时点：{datetime.now().strftime('%Y-%m-%d %H:%M')} · 基于公开数据生成，不构成投资建议</p>
</div>

</div>
</body>
</html>'''

    outpath = os.path.join(ROOT, 'index.html')
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f'✓ index.html 已生成 — {total} 个报告, {days} 个交易日, {mkt} 个市场')


if __name__ == '__main__':
    generate()