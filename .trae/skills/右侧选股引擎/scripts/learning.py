#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧选股引擎 - 自学习模块
Right-side Stock Selection Engine - Self-Learning Module

根据历史选股的后续表现，自适应调整八维清单的权重和阈值。

Usage:
    python learning.py --data-dir <path>
    python learning.py --data-dir <path> --dry-run  # 仅分析不更新配置
"""

import argparse
import json
import subprocess
import sys
import os
import math
from datetime import datetime, timedelta
from pathlib import Path

# 导入 screener 的工具函数
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from screener import (
    run_westock, load_config, save_config, ensure_dirs, get_today,
    safe_float, parse_kline, DEFAULT_CONFIG
)


def load_history(data_dir):
    """加载所有历史选股记录"""
    history_dir = os.path.join(data_dir, "history")
    if not os.path.exists(history_dir):
        return []

    records = []
    for date_folder in sorted(os.listdir(history_dir)):
        folder_path = os.path.join(history_dir, date_folder)
        if not os.path.isdir(folder_path):
            continue
        selection_path = os.path.join(folder_path, "selection.json")
        if not os.path.exists(selection_path):
            continue
        try:
            with open(selection_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            records.append(data)
        except Exception as e:
            print(f"[警告] 读取 {selection_path} 失败: {e}", file=sys.stderr)

    return records


def get_stock_performance(code, selection_date, config):
    """
    获取从选股日到当前的股价表现
    返回: {status, max_gain_pct, max_loss_pct, holding_days, current_close}
    """
    # 计算交易日（粗略估算：日历日 * 5/7）
    selection_dt = datetime.strptime(selection_date, "%Y-%m-%d")
    today_dt = datetime.now()
    calendar_days = (today_dt - selection_dt).days
    trading_days = max(0, int(calendar_days * 5 / 7))

    if trading_days < 1:
        return {"status": "too_early", "max_gain_pct": 0, "max_loss_pct": 0,
                "holding_days": 0, "current_close": None}

    # 获取K线数据（从选股日到现在）
    kline_data = run_westock([
        "kline", code, "--period", "day",
        "--start", selection_date,
        "--limit", "30"
    ], raw=True)

    kline = parse_kline(kline_data)
    if len(kline) < 2:
        return {"status": "no_data", "max_gain_pct": 0, "max_loss_pct": 0,
                "holding_days": 0, "current_close": None}

    entry_price = kline[0]["close"]
    current_close = kline[-1]["close"]
    highs = [k["high"] for k in kline if k.get("high")]
    lows = [k["low"] for k in kline if k.get("low")]

    max_high = max(highs) if highs else entry_price
    min_low = min(lows) if lows else entry_price

    max_gain_pct = round((max_high / entry_price - 1) * 100, 2) if entry_price > 0 else 0
    max_loss_pct = round((min_low / entry_price - 1) * 100, 2) if entry_price > 0 else 0

    take_profit = config["thresholds"]["take_profit_pct"]
    max_loss = config["thresholds"]["max_loss_pct"]
    max_holding = config["thresholds"]["max_holding_days"]

    holding_days = len(kline)

    # 判定状态
    if max_gain_pct >= take_profit:
        status = "take_profit"
    elif max_loss_pct <= max_loss:
        status = "stop_loss"
    elif holding_days >= max_holding:
        status = "timeout"
        # 超时后看最终盈亏
        final_return = round((current_close / entry_price - 1) * 100, 2)
        if final_return > 0:
            status = "timeout_profit"
        else:
            status = "timeout_loss"
    else:
        status = "holding"

    return {
        "status": status,
        "max_gain_pct": max_gain_pct,
        "max_loss_pct": max_loss_pct,
        "holding_days": holding_days,
        "current_close": round(current_close, 2),
        "entry_price": round(entry_price, 2),
        "final_return_pct": round((current_close / entry_price - 1) * 100, 2) if entry_price > 0 else 0
    }


def analyze_performance(history_records, config):
    """
    分析历史选股表现
    返回: {total, analyzed, by_category, by_status, hit_rate}
    """
    min_samples = config["learning"]["min_samples"]
    total_selections = 0
    analyzed = 0
    by_status = {"take_profit": 0, "stop_loss": 0, "timeout_profit": 0,
                 "timeout_loss": 0, "holding": 0, "too_early": 0, "no_data": 0}

    # 按维度统计
    categories = ["trend_filter", "right_side", "volume", "sector_resonance",
                  "fundamental_risk", "risk_planning", "holding_period", "final_score"]
    by_category = {}
    for cat in categories:
        by_category[cat] = {
            "passed_total": 0, "passed_win": 0,
            "failed_total": 0, "failed_win": 0,
            "pass_hit_rate": 0, "fail_hit_rate": 0
        }

    stock_performances = []

    for record in history_records:
        selections = record.get("results", [])
        run_date = record.get("run_date", record.get("date", ""))

        for sel in selections:
            total_selections += 1
            code = sel.get("code", "")
            if not code or not run_date:
                continue

            # 获取后续表现
            perf = get_stock_performance(code, run_date, config)
            stock_performances.append({
                "code": code,
                "name": sel.get("name", ""),
                "run_date": run_date,
                "performance": perf
            })

            if perf["status"] in ["too_early", "no_data"]:
                by_status[perf["status"]] += 1
                continue

            analyzed += 1
            by_status[perf["status"]] = by_status.get(perf["status"], 0) + 1

            # 判定是否盈利
            is_win = perf["status"] in ["take_profit", "timeout_profit"]

            # 按维度统计
            checks = sel.get("checks", {})
            for cat in categories:
                check = checks.get(cat, {})
                passed = check.get("pass", False)
                if passed:
                    by_category[cat]["passed_total"] += 1
                    if is_win:
                        by_category[cat]["passed_win"] += 1
                else:
                    by_category[cat]["failed_total"] += 1
                    if is_win:
                        by_category[cat]["failed_win"] += 1

    # 计算命中率
    for cat in categories:
        d = by_category[cat]
        d["pass_hit_rate"] = round(d["passed_win"] / d["passed_total"] * 100, 1) if d["passed_total"] > 0 else 0
        d["fail_hit_rate"] = round(d["failed_win"] / d["failed_total"] * 100, 1) if d["failed_total"] > 0 else 0

    overall_hit_rate = 0
    wins = by_status.get("take_profit", 0) + by_status.get("timeout_profit", 0)
    if analyzed > 0:
        overall_hit_rate = round(wins / analyzed * 100, 1)

    return {
        "total_selections": total_selections,
        "analyzed": analyzed,
        "by_status": by_status,
        "by_category": by_category,
        "overall_hit_rate": overall_hit_rate,
        "stock_performances": stock_performances,
        "min_samples_met": analyzed >= min_samples
    }


def adjust_config(config, analysis):
    """
    根据分析结果调整配置
    返回: {config, adjustments}
    """
    if not analysis["min_samples_met"]:
        return {
            "config": config,
            "adjustments": [],
            "message": f"样本数不足（{analysis['analyzed']}/{config['learning']['min_samples']}），跳过调整"
        }

    adjustment_rate = config["learning"]["adjustment_rate"]
    max_weight_change = config["learning"]["max_weight_change"]
    max_threshold_change = config["learning"]["max_threshold_change"]
    adjustments = []

    # 调整权重
    for cat, stats in analysis["by_category"].items():
        if stats["passed_total"] < 3:
            continue  # 样本太少

        current_weight = config["weights"].get(cat, 1.0)
        pass_rate = stats["pass_hit_rate"]

        if pass_rate > 60:
            # 命中率高，权重上调
            change = adjustment_rate
            new_weight = current_weight * (1 + change)
            reason = f"{cat} 命中率 {pass_rate}% > 60%，权重上调"
        elif pass_rate < 40:
            # 命中率低，权重下调
            change = -adjustment_rate
            new_weight = current_weight * (1 + change)
            reason = f"{cat} 命中率 {pass_rate}% < 40%，权重下调"
        else:
            continue

        # 约束调整幅度
        original_weight = DEFAULT_CONFIG["weights"].get(cat, 1.0)
        max_weight = original_weight * (1 + max_weight_change)
        min_weight = original_weight * (1 - max_weight_change)
        new_weight = max(min_weight, min(max_weight, new_weight))
        new_weight = round(new_weight, 3)

        if new_weight != current_weight:
            config["weights"][cat] = new_weight
            adjustments.append({
                "type": "weight",
                "category": cat,
                "old_value": current_weight,
                "new_value": new_weight,
                "change_pct": round((new_weight / current_weight - 1) * 100, 1),
                "reason": reason,
                "hit_rate": pass_rate
            })

    # 调整阈值（基于整体表现）
    overall_rate = analysis["overall_hit_rate"]
    if overall_rate < 40 and analysis["analyzed"] >= 5:
        # 整体命中率低，放宽阈值
        old_box_days = config["thresholds"]["box_consolidation_days"]
        new_box_days = max(10, int(old_box_days * (1 - max_threshold_change)))
        if new_box_days != old_box_days:
            config["thresholds"]["box_consolidation_days"] = new_box_days
            adjustments.append({
                "type": "threshold",
                "name": "box_consolidation_days",
                "old_value": old_box_days,
                "new_value": new_box_days,
                "reason": f"整体命中率 {overall_rate}% < 40%，放宽箱体天数阈值"
            })

        old_vol_ratio = config["thresholds"]["breakout_volume_ratio"]
        new_vol_ratio = round(max(1.1, old_vol_ratio * (1 - max_threshold_change)), 2)
        if new_vol_ratio != old_vol_ratio:
            config["thresholds"]["breakout_volume_ratio"] = new_vol_ratio
            adjustments.append({
                "type": "threshold",
                "name": "breakout_volume_ratio",
                "old_value": old_vol_ratio,
                "new_value": new_vol_ratio,
                "reason": f"整体命中率 {overall_rate}% < 40%，放宽带量比阈值"
            })

    elif overall_rate > 70 and analysis["analyzed"] >= 5:
        # 整体命中率高，收紧阈值（提高标准）
        old_box_days = config["thresholds"]["box_consolidation_days"]
        new_box_days = min(20, int(old_box_days * (1 + max_threshold_change)))
        if new_box_days != old_box_days:
            config["thresholds"]["box_consolidation_days"] = new_box_days
            adjustments.append({
                "type": "threshold",
                "name": "box_consolidation_days",
                "old_value": old_box_days,
                "new_value": new_box_days,
                "reason": f"整体命中率 {overall_rate}% > 70%，收紧箱体天数阈值"
            })

    config["last_updated"] = get_today()

    return {
        "config": config,
        "adjustments": adjustments,
        "message": f"完成 {len(adjustments)} 项调整" if adjustments else "无需调整"
    }


def main():
    parser = argparse.ArgumentParser(description="右侧选股引擎 - 自学习模块")
    parser.add_argument("--data-dir", required=True, help="数据目录路径")
    parser.add_argument("--dry-run", action="store_true", help="仅分析不更新配置")

    args = parser.parse_args()

    ensure_dirs(args.data_dir)
    config = load_config(args.data_dir)

    print(f"[自学习] 加载历史记录...", file=sys.stderr)
    history = load_history(args.data_dir)
    print(f"[自学习] 共找到 {len(history)} 次历史选股记录", file=sys.stderr)

    if not history:
        result = {
            "run_date": get_today(),
            "status": "no_history",
            "message": "无历史选股记录，跳过自学习",
            "adjustments": []
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"[自学习] 分析历史表现...", file=sys.stderr)
    analysis = analyze_performance(history, config)

    print(f"[自学习] 已分析 {analysis['analyzed']} 只标的", file=sys.stderr)
    print(f"[自学习] 整体命中率: {analysis['overall_hit_rate']}%", file=sys.stderr)

    if args.dry_run:
        adjustment_result = {
            "config": config,
            "adjustments": [],
            "message": "dry-run 模式，不更新配置"
        }
    else:
        print(f"[自学习] 调整配置...", file=sys.stderr)
        adjustment_result = adjust_config(config, analysis)

        if adjustment_result["adjustments"]:
            save_config(args.data_dir, adjustment_result["config"])
            print(f"[自学习] 配置已更新，共 {len(adjustment_result['adjustments'])} 项调整", file=sys.stderr)

    # 保存学习日志
    learning_log = {
        "run_date": get_today(),
        "run_time": datetime.now().isoformat(),
        "status": "completed" if analysis["min_samples_met"] else "insufficient_samples",
        "total_selections": analysis["total_selections"],
        "analyzed": analysis["analyzed"],
        "overall_hit_rate": analysis["overall_hit_rate"],
        "by_status": analysis["by_status"],
        "by_category": analysis["by_category"],
        "adjustments": adjustment_result["adjustments"],
        "message": adjustment_result["message"],
        "stock_performances": analysis["stock_performances"][-20:]  # 保留最近20条
    }

    log_path = os.path.join(args.data_dir, "learning", "learning_log.json")
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(learning_log, f, ensure_ascii=False, indent=2)

    print(f"[自学习] 学习日志已保存到 {log_path}", file=sys.stderr)

    # 输出摘要
    output = {
        "run_date": learning_log["run_date"],
        "status": learning_log["status"],
        "total_selections": learning_log["total_selections"],
        "analyzed": learning_log["analyzed"],
        "overall_hit_rate": learning_log["overall_hit_rate"],
        "by_status": learning_log["by_status"],
        "adjustments": learning_log["adjustments"],
        "message": learning_log["message"]
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
