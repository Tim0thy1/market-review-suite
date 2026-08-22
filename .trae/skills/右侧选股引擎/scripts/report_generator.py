#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧选股引擎 - HTML 报告生成器
Right-side Stock Selection Engine - Report Generator

读取 screener.py 输出的 JSON 结果，生成自包含 HTML 报告。

Usage:
    python report_generator.py --input <screener输出JSON> --data-dir <数据目录>
"""

import argparse
import json
import sys
import os
from datetime import datetime
from pathlib import Path


def load_json(path):
    """加载 JSON 文件"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_html(data, learning_log=None):
    """生成自包含 HTML 报告"""
    run_date = data.get("run_date", "")
    results = data.get("results", [])
    excluded = data.get("excluded", [])
    candidates_total = data.get("candidates_total", 0)
    screened_count = data.get("screened_count", 0)
    excluded_count = data.get("excluded_count", 0)
    filters = data.get("filters", {})

    # 汇总统计
    signal_types = {}
    industries = {}
    for r in results:
        sig = r.get("signal_type", "未知")
        signal_types[sig] = signal_types.get(sig, 0) + 1
        ind = r.get("industry", "未知")
        industries[ind] = industries.get(ind, 0) + 1

    # 淘汰原因统计
    exclude_reasons = {}
    for e in excluded:
        reason = e.get("reason", "未知")
        exclude_reasons[reason] = exclude_reasons.get(reason, 0) + 1

    # 学习日志摘要
    learning_section = ""
    if learning_log:
        adjustments = learning_log.get("adjustments", [])
        adj_html = ""
        for adj in adjustments:
            if adj["type"] == "weight":
                change_symbol = "↑" if adj["change_pct"] > 0 else "↓"
                change_color = "#dc2626" if adj["change_pct"] > 0 else "#16a34a"
                adj_html += f"""
                <tr>
                    <td>{adj['category']}</td>
                    <td>权重</td>
                    <td>{adj['old_value']}</td>
                    <td>{adj['new_value']}</td>
                    <td style="color:{change_color}">{change_symbol} {abs(adj['change_pct'])}%</td>
                    <td>{adj.get('reason', '')}</td>
                </tr>"""
            else:
                adj_html += f"""
                <tr>
                    <td>{adj['name']}</td>
                    <td>阈值</td>
                    <td>{adj['old_value']}</td>
                    <td>{adj['new_value']}</td>
                    <td>-</td>
                    <td>{adj.get('reason', '')}</td>
                </tr>"""

        learning_section = f"""
        <section class="learning-section">
            <h2>自学习状态</h2>
            <div class="learning-summary">
                <div class="stat-card">
                    <div class="stat-value">{learning_log.get('analyzed', 0)}</div>
                    <div class="stat-label">已分析标的</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{learning_log.get('overall_hit_rate', 0)}%</div>
                    <div class="stat-label">整体命中率</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{len(adjustments)}</div>
                    <div class="stat-label">本次调整数</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">{learning_log.get('total_selections', 0)}</div>
                    <div class="stat-label">历史选股总数</div>
                </div>
            </div>
            {f'<table class="learning-table"><tr><th>维度</th><th>类型</th><th>旧值</th><th>新值</th><th>变化</th><th>原因</th></tr>{adj_html}</table>' if adj_html else '<p class="no-adjustment">本次无需调整</p>'}
            <p class="learning-message">{learning_log.get('message', '')}</p>
        </section>"""

    # 选中的标的卡片
    stock_cards = ""
    for i, r in enumerate(results, 1):
        checks = r.get("checks", {})
        indicators = r.get("indicators", {})

        # 八维通过情况
        check_items = ""
        check_config = [
            ("trend_filter", "趋势过滤", True),
            ("right_side", "右侧确认", True),
            ("volume", "量能确认", False),
            ("sector_resonance", "板块共振", False),
            ("fundamental_risk", "基本面避雷", True),
            ("risk_planning", "风控规划", True),
            ("holding_period", "持仓周期", False),
            ("final_score", "综合打分", True)
        ]
        for key, label, is_core in check_config:
            check = checks.get(key, {})
            passed = check.get("pass", False)
            icon = "✅" if passed else "❌"
            core_tag = ' <span class="core-tag">核心</span>' if is_core else ""
            check_items += f'<div class="check-item {"passed" if passed else "failed"}">{icon} {label}{core_tag}</div>'

        # 信号类型标签
        sig_type = r.get("signal_type", "")
        sig_label = "箱体突破" if sig_type == "box_breakout" else "回踩启动" if sig_type == "pullback_start" else "未知"
        sig_color = "#dc2626" if sig_type == "box_breakout" else "#1e40af"

        # MACD 状态
        macd = indicators.get("macd", {})
        macd_status = "金叉" if macd.get("dif_above_dea") else "死叉"
        macd_color = "#dc2626" if macd.get("dif_above_dea") else "#16a34a"

        kdj = indicators.get("kdj", {})
        boll = indicators.get("boll", {})

        stock_cards += f"""
        <div class="stock-card">
            <div class="stock-header">
                <div class="stock-rank">#{i}</div>
                <div class="stock-info">
                    <span class="stock-code">{r.get('code', '')}</span>
                    <span class="stock-name">{r.get('name', '')}</span>
                    <span class="stock-industry">{r.get('industry', '')}</span>
                </div>
                <div class="stock-score">
                    <div class="score-value">{r.get('score', 0)}</div>
                    <div class="score-label">评分</div>
                </div>
            </div>
            <div class="stock-meta">
                <span class="meta-tag" style="background:{sig_color}">{sig_label}</span>
                <span class="meta-tag resonance">{r.get('resonance', '')}</span>
                <span class="meta-tag">收盘 {r.get('close', 0)}</span>
                <span class="meta-tag">止损 {r.get('stop_loss', '-')}</span>
                <span class="meta-tag">止盈 {r.get('take_profit_target', '-')}</span>
                <span class="meta-tag">最大亏损 {r.get('max_loss_pct', '-')}%</span>
                <span class="meta-tag">盈亏比 {r.get('risk_reward', '-')}</span>
            </div>
            <div class="stock-indicators">
                <div class="ind-item">MA5: <b>{indicators.get('ma5', '-')}</b></div>
                <div class="ind-item">MA20: <b>{indicators.get('ma20', '-')}</b></div>
                <div class="ind-item">MA60: <b>{indicators.get('ma60', '-')}</b></div>
                <div class="ind-item">MA60方向: <b>{indicators.get('ma60_slope', {}).get('direction', '-')}</b></div>
                <div class="ind-item">MACD: <b style="color:{macd_color}">{macd_status}</b></div>
                <div class="ind-item">KDJ: <b>K={kdj.get('k', '-')} D={kdj.get('d', '-')} J={kdj.get('j', '-')}</b></div>
                <div class="ind-item">RSI6: <b>{indicators.get('rsi6', '-')}</b></div>
                <div class="ind-item">量比: <b>{indicators.get('volume_ratio', '-')}</b></div>
                <div class="ind-item">10日涨幅: <b>{indicators.get('rally_10d', '-')}%</b></div>
                <div class="ind-item">20日均额: <b>{round(indicators.get('avg_amount_20d', 0) / 100000000, 2)}亿</b></div>
            </div>
            <div class="stock-checks">
                {check_items}
            </div>
        </div>"""

    # 淘汰原因分布
    exclude_html = ""
    if exclude_reasons:
        exclude_items = ""
        for reason, count in sorted(exclude_reasons.items(), key=lambda x: -x[1]):
            pct = round(count / max(excluded_count, 1) * 100, 1)
            exclude_items += f"""
            <tr>
                <td>{reason}</td>
                <td>{count}</td>
                <td>{pct}%</td>
            </tr>"""
        exclude_html = f"""
        <section>
            <h2>淘汰分析</h2>
            <p class="section-desc">候选池 {candidates_total} 只 → 通过 {screened_count} 只 → 淘汰 {excluded_count} 只</p>
            <table class="exclude-table">
                <tr><th>淘汰原因</th><th>数量</th><th>占比</th></tr>
                {exclude_items}
            </table>
        </section>"""

    # 行业分布
    industry_html = ""
    if industries:
        ind_items = ""
        for ind, count in sorted(industries.items(), key=lambda x: -x[1]):
            ind_items += f'<div class="ind-bar"><span class="ind-name">{ind}</span><span class="ind-count">{count}</span></div>'
        industry_html = f"""
        <section>
            <h2>选中标的行业分布</h2>
            <div class="industry-distribution">{ind_items}</div>
        </section>"""

    # 信号类型分布
    signal_html = ""
    if signal_types:
        sig_items = ""
        for sig, count in signal_types.items():
            label = "箱体突破" if sig == "box_breakout" else "回踩启动" if sig == "pullback_start" else sig
            sig_items += f'<div class="signal-bar"><span class="signal-name">{label}</span><span class="signal-count">{count}</span></div>'
        signal_html = f"""
        <section>
            <h2>信号类型分布</h2>
            <div class="signal-distribution">{sig_items}</div>
        </section>"""

    # 过滤条件
    filter_html = ""
    if filters:
        filter_items = []
        if filters.get("industry"):
            filter_items.append(f"行业: {filters['industry']}")
        if filters.get("exclude_300"):
            filter_items.append("排除创业板")
        if filters.get("exclude_688"):
            filter_items.append("排除科创板")
        if filters.get("exclude_bj"):
            filter_items.append("排除北交所")
        if filter_items:
            filter_html = f'<div class="filter-tags">筛选条件: {" · ".join(filter_items)}</div>'

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>右侧选股报告 - {run_date}</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, 'Noto Sans CJK SC', 'Microsoft YaHei', sans-serif;
               background: #f8fafc; color: #1e293b; line-height: 1.6; padding: 20px; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        header {{ text-align: center; padding: 30px 0 20px; border-bottom: 2px solid #e2e8f0; margin-bottom: 30px; }}
        header h1 {{ font-size: 28px; color: #0f172a; margin-bottom: 8px; }}
        header .date {{ color: #64748b; font-size: 14px; }}

        .tldr {{ background: linear-gradient(135deg, #1e3a5f, #1e40af); color: white;
                border-radius: 12px; padding: 24px 28px; margin-bottom: 30px;
                box-shadow: 0 4px 12px rgba(30,64,175,0.2); }}
        .tldr h2 {{ font-size: 18px; margin-bottom: 12px; opacity: 0.9; }}
        .tldr .verdict {{ font-size: 22px; font-weight: 700; margin-bottom: 8px; }}
        .tldr .detail {{ font-size: 14px; opacity: 0.85; line-height: 1.8; }}

        section {{ background: white; border-radius: 10px; padding: 24px; margin-bottom: 24px;
                   box-shadow: 0 1px 3px rgba(0,0,0,0.06); }}
        section h2 {{ font-size: 18px; color: #0f172a; margin-bottom: 16px;
                      padding-bottom: 10px; border-bottom: 1px solid #e2e8f0; }}
        .section-desc {{ color: #64748b; font-size: 13px; margin-bottom: 12px; }}

        .stat-row {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
        .stat-card {{ flex: 1; min-width: 120px; background: #f1f5f9; border-radius: 8px;
                      padding: 16px; text-align: center; }}
        .stat-value {{ font-size: 28px; font-weight: 700; color: #1e40af; }}
        .stat-label {{ font-size: 12px; color: #64748b; margin-top: 4px; }}

        .stock-card {{ border: 1px solid #e2e8f0; border-radius: 10px; padding: 20px;
                       margin-bottom: 16px; transition: box-shadow 0.2s; }}
        .stock-card:hover {{ box-shadow: 0 2px 8px rgba(0,0,0,0.08); }}
        .stock-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 12px;
                         padding-bottom: 10px; border-bottom: 1px solid #f1f5f9; }}
        .stock-rank {{ background: #1e40af; color: white; width: 36px; height: 36px;
                       border-radius: 50%; display: flex; align-items: center;
                       justify-content: center; font-weight: 700; font-size: 14px; }}
        .stock-info {{ flex: 1; }}
        .stock-code {{ font-family: monospace; font-size: 14px; color: #64748b; margin-right: 8px; }}
        .stock-name {{ font-size: 16px; font-weight: 600; margin-right: 8px; }}
        .stock-industry {{ font-size: 12px; color: #64748b; background: #f1f5f9;
                           padding: 2px 8px; border-radius: 4px; }}
        .stock-score {{ text-align: center; }}
        .score-value {{ font-size: 24px; font-weight: 700; color: #dc2626; }}
        .score-label {{ font-size: 11px; color: #64748b; }}

        .stock-meta {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }}
        .meta-tag {{ font-size: 12px; padding: 3px 10px; border-radius: 4px;
                     background: #f1f5f9; color: #475569; }}
        .meta-tag.resonance {{ background: #fef3c7; color: #92400e; font-weight: 600; }}

        .stock-indicators {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px;
                              padding: 10px; background: #f8fafc; border-radius: 6px; }}
        .ind-item {{ font-size: 12px; color: #475569; }}
        .ind-item b {{ color: #1e293b; }}

        .stock-checks {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                         gap: 6px; }}
        .check-item {{ font-size: 12px; padding: 4px 8px; border-radius: 4px; }}
        .check-item.passed {{ background: #f0fdf4; color: #166534; }}
        .check-item.failed {{ background: #fef2f2; color: #991b1b; }}
        .core-tag {{ font-size: 10px; background: #dc2626; color: white; padding: 1px 4px;
                     border-radius: 3px; margin-left: 4px; }}

        .exclude-table, .learning-table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
        .exclude-table th, .exclude-table td, .learning-table th, .learning-table td {{
            padding: 8px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        .exclude-table th, .learning-table th {{ background: #f8fafc; font-weight: 600; color: #475569; }}

        .industry-distribution, .signal-distribution {{ display: flex; flex-direction: column; gap: 6px; }}
        .ind-bar, .signal-bar {{ display: flex; justify-content: space-between;
                                  padding: 8px 12px; background: #f8fafc; border-radius: 6px;
                                  font-size: 13px; }}
        .ind-name, .signal-name {{ color: #475569; }}
        .ind-count, .signal-count {{ font-weight: 600; color: #1e40af; }}

        .learning-summary {{ display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }}
        .learning-message {{ font-size: 13px; color: #64748b; margin-top: 8px; font-style: italic; }}
        .no-adjustment {{ color: #64748b; font-style: italic; }}

        .filter-tags {{ font-size: 13px; color: #64748b; margin-bottom: 16px;
                        padding: 8px 12px; background: #f1f5f9; border-radius: 6px; }}

        footer {{ text-align: center; padding: 30px 0; color: #94a3b8; font-size: 12px;
                  border-top: 1px solid #e2e8f0; margin-top: 30px; }}

        @media (max-width: 768px) {{
            .stat-card {{ min-width: 100px; }}
            .stock-checks {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <h1>右侧选股报告</h1>
        <div class="date">{run_date} · 中线右侧信号筛选</div>
    </header>

    <div class="tldr">
        <h2>首屏结论</h2>
        <div class="verdict">筛选完成：{screened_count} 只标的通过八维右侧信号核查</div>
        <div class="detail">
            候选池 {candidates_total} 只 → 通过筛查 {screened_count} 只 → 淘汰 {excluded_count} 只。
            适配规则：持仓 10~20 交易日，止盈 8%~11%，单笔最大亏损 ≤ -6%。
            每只标的均已逐条核对右侧信号清单，核心维度（趋势/右侧确认/基本面/风控）全部通过。
            请结合市场环境和个人风险偏好，进一步筛选后决策。
        </div>
    </div>

    {filter_html}

    <section>
        <h2>筛选概况</h2>
        <div class="stat-row">
            <div class="stat-card">
                <div class="stat-value">{candidates_total}</div>
                <div class="stat-label">候选池总数</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#dc2626">{screened_count}</div>
                <div class="stat-label">通过筛查</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="color:#64748b">{excluded_count}</div>
                <div class="stat-label">淘汰数量</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">{round(screened_count / max(candidates_total, 1) * 100, 1)}%</div>
                <div class="stat-label">通过率</div>
            </div>
        </div>
    </section>

    <section>
        <h2>选中标的详情</h2>
        {stock_cards if stock_cards else '<p class="no-adjustment">本次无标的通过筛查</p>'}
    </section>

    {industry_html}
    {signal_html}
    {exclude_html}
    {learning_section}

    <footer>
        <p>本报告由右侧选股引擎自动生成，仅提供基于技术信号的客观筛选结果，不构成投资建议。</p>
        <p>数据可能有延迟，以交易所官方为准。投资有风险，决策需谨慎。</p>
        <p>生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
    </footer>
</div>

<script>
    // 信号类型分布图（如果数据存在）
    var signalData = {json.dumps([{"name": ("箱体突破" if k == "box_breakout" else "回踩启动" if k == "pullback_start" else k), "value": v} for k, v in signal_types.items()])};
    if (signalData.length > 0 && document.getElementById('signalChart')) {{
        var chart = echarts.init(document.getElementById('signalChart'));
        chart.setOption({{
            tooltip: {{ trigger: 'item' }},
            series: [{{
                type: 'pie',
                radius: ['40%', '70%'],
                data: signalData,
                itemStyle: {{ borderRadius: 6, borderColor: '#fff', borderWidth: 2 }}
            }}]
        }});
    }}
</script>
</body>
</html>"""

    return html


def main():
    parser = argparse.ArgumentParser(description="右侧选股引擎 - HTML 报告生成器")
    parser.add_argument("--input", required=True, help="screener 输出的 JSON 文件路径")
    parser.add_argument("--data-dir", required=True, help="数据目录路径")
    parser.add_argument("--output", help="输出 HTML 文件路径（默认自动生成）")

    args = parser.parse_args()

    # 加载选股结果
    data = load_json(args.input)
    print(f"[报告] 加载选股结果: {args.input}", file=sys.stderr)

    # 加载学习日志（如果存在）
    learning_log = None
    log_path = os.path.join(args.data_dir, "learning", "learning_log.json")
    if os.path.exists(log_path):
        try:
            learning_log = load_json(log_path)
            print(f"[报告] 加载学习日志: {log_path}", file=sys.stderr)
        except Exception:
            pass

    # 生成 HTML
    html = generate_html(data, learning_log)

    # 确定输出路径
    if args.output:
        output_path = args.output
    else:
        run_date = data.get("run_date", datetime.now().strftime("%Y-%m-%d")).replace("-", "")
        reports_dir = os.path.join(args.data_dir, "reports")
        os.makedirs(reports_dir, exist_ok=True)
        output_path = os.path.join(reports_dir, f"选股报告_{run_date}.html")

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[报告] HTML 报告已保存到 {output_path}", file=sys.stderr)
    print(output_path)


if __name__ == "__main__":
    main()
