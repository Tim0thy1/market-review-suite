#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
右侧选股引擎 - 核心筛选脚本
Right-side Stock Selection Engine - Core Screener

Usage:
    python screener.py --phase candidates --data-dir <path> [--industry <name>] [--exclude-300] [--exclude-688] [--exclude-bj]
    python screener.py --phase screen --data-dir <path> --stocks sh600519,sz000651
    python screener.py --phase full --data-dir <path> [--industry <name>]
"""

import argparse
import json
import subprocess
import sys
import os
import math
import re
from datetime import datetime
from pathlib import Path

# ============================================================
# 默认配置
# ============================================================
DEFAULT_CONFIG = {
    "version": "1.0",
    "last_updated": "",
    "screening": {
        "target_count": 15,
        "lookback_days": 60,
        "min_amount": 150000000,
        "exclude_st": True,
        "exclude_300": False,
        "exclude_688": False,
        "exclude_bj": True
    },
    "weights": {
        "trend_filter": 1.5,
        "right_side": 2.0,
        "volume": 1.2,
        "sector_resonance": 1.3,
        "fundamental_risk": 1.5,
        "risk_planning": 1.0,
        "holding_period": 0.5,
        "final_score": 1.0
    },
    "thresholds": {
        "box_consolidation_days": 15,
        "breakout_volume_ratio": 1.3,
        "ma60_slope_days": 5,
        "ma60_slope_threshold": 0.001,
        "higher_lows_window": 20,
        "sector_outperform_days": 3,
        "max_loss_pct": -6.0,
        "take_profit_pct": 8.0,
        "max_holding_days": 20,
        "min_holding_days": 10,
        "high_rally_threshold": 30.0,
        "box_volatility_threshold": 0.08
    },
    "learning": {
        "enabled": True,
        "min_samples": 5,
        "adjustment_rate": 0.05,
        "max_weight_change": 0.2,
        "max_threshold_change": 0.1
    }
}

WESTOCK_CMD = ["npx", "-y", "westock-data-skillhub@1.0.5"]

# ============================================================
# 工具函数
# ============================================================

def run_westock(args, raw=True, timeout=60):
    """执行 westock-data 命令并返回解析后的结果"""
    cmd = WESTOCK_CMD + args
    if raw and "--raw" not in args:
        cmd.append("--raw")
    try:
        # Windows 下 npx 需要通过 shell 调用
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            encoding='utf-8', errors='replace', shell=True
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr[:500]}
        output = result.stdout.strip()
        # 尝试 JSON 解析
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            # 尝试从输出中提取 JSON 数组
            json_match = re.search(r'\[.*\]', output, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            # 尝试从输出中提取 JSON 对象
            json_match = re.search(r'\{.*\}', output, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass
            return {"success": False, "error": "非JSON输出", "raw": output[:500]}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "命令超时"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def load_config(data_dir):
    """加载配置文件，不存在则创建默认配置"""
    config_path = os.path.join(data_dir, "config.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    config = DEFAULT_CONFIG.copy()
    config["last_updated"] = datetime.now().strftime("%Y-%m-%d")
    save_config(data_dir, config)
    return config


def save_config(data_dir, config):
    """保存配置文件"""
    config_path = os.path.join(data_dir, "config.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def ensure_dirs(data_dir):
    """确保数据目录结构存在"""
    for sub in ["", "history", "reports", "learning"]:
        path = os.path.join(data_dir, sub) if sub else data_dir
        os.makedirs(path, exist_ok=True)


def get_today():
    """获取今天日期"""
    return datetime.now().strftime("%Y-%m-%d")


def safe_float(val, default=None):
    """安全转换为浮点数"""
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val, default=None):
    """安全转换为整数"""
    try:
        return int(val)
    except (ValueError, TypeError):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return default


# ============================================================
# 技术指标计算
# ============================================================

def calculate_ma(closes, period):
    """简单移动平均"""
    if len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def calculate_ma_series(closes, period):
    """计算 MA 序列（返回列表，长度与 closes 相同，前面不足部分为 None）"""
    result = [None] * len(closes)
    for i in range(period - 1, len(closes)):
        result[i] = sum(closes[i - period + 1: i + 1]) / period
    return result


def calculate_ema_series(values, period):
    """计算 EMA 序列"""
    if len(values) < period:
        return [None] * len(values)
    result = [None] * (period - 1)
    # 第一个 EMA = 前 period 个值的 SMA
    sma = sum(values[:period]) / period
    result.append(sma)
    multiplier = 2 / (period + 1)
    for i in range(period, len(values)):
        ema = values[i] * multiplier + result[-1] * (1 - multiplier)
        result.append(ema)
    return result


def calculate_macd(closes, fast=12, slow=26, signal=9):
    """计算 MACD（DIF, DEA, MACD柱）"""
    if len(closes) < slow + signal:
        return {"dif": None, "dea": None, "macd": None, "history": []}
    ema_fast = calculate_ema_series(closes, fast)
    ema_slow = calculate_ema_series(closes, slow)
    dif_series = []
    for i in range(len(closes)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            dif_series.append(ema_fast[i] - ema_slow[i])
        else:
            dif_series.append(None)
    # DEA = EMA(DIF, signal)
    valid_dif = [d for d in dif_series if d is not None]
    if len(valid_dif) < signal:
        return {"dif": None, "dea": None, "macd": None, "history": []}
    dea_series = calculate_ema_series(valid_dif, signal)
    # 对齐
    dif_val = valid_dif[-1] if valid_dif else None
    dea_val = dea_series[-1] if dea_series and dea_series[-1] is not None else None
    macd_val = 2 * (dif_val - dea_val) if dif_val is not None and dea_val is not None else None
    return {
        "dif": round(dif_val, 4) if dif_val is not None else None,
        "dea": round(dea_val, 4) if dea_val is not None else None,
        "macd": round(macd_val, 4) if macd_val is not None else None,
        "dif_above_dea": dif_val > dea_val if dif_val is not None and dea_val is not None else False,
        "history": [{"dif": round(d, 4) if d else None, "dea": None} for d in valid_dif[-10:]]
    }


def calculate_kdj(highs, lows, closes, n=9, m1=3, m2=3):
    """计算 KDJ"""
    if len(closes) < n:
        return {"k": None, "d": None, "j": None}
    k, d = 50.0, 50.0
    for i in range(n - 1, len(closes)):
        period_high = max(highs[i - n + 1: i + 1])
        period_low = min(lows[i - n + 1: i + 1])
        if period_high == period_low:
            rsv = 50
        else:
            rsv = (closes[i] - period_low) / (period_high - period_low) * 100
        k = (m1 - 1) / m1 * k + 1 / m1 * rsv
        d = (m2 - 1) / m2 * d + 1 / m2 * k
    j = 3 * k - 2 * d
    return {
        "k": round(k, 2),
        "d": round(d, 2),
        "j": round(j, 2),
        "oversold": k < 20 and d < 20,
        "overbought": k > 80 and d > 80
    }


def calculate_rsi(closes, period=6):
    """计算 RSI"""
    if len(closes) < period + 1:
        return None
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calculate_boll(closes, period=20, std_dev=2):
    """计算布林带"""
    if len(closes) < period:
        return {"upper": None, "mid": None, "lower": None, "width": None}
    ma = sum(closes[-period:]) / period
    variance = sum((c - ma) ** 2 for c in closes[-period:]) / period
    std = math.sqrt(variance)
    upper = ma + std_dev * std
    lower = ma - std_dev * std
    return {
        "upper": round(upper, 2),
        "mid": round(ma, 2),
        "lower": round(lower, 2),
        "width": round((upper - lower) / ma, 4) if ma > 0 else None,
        "price_position": "upper" if closes[-1] > upper else "lower" if closes[-1] < lower else "mid"
    }


def calculate_ma_slope(closes, period=60, lookback=5):
    """计算 MA 斜率（判断走平/向上/向下）"""
    if len(closes) < period + lookback:
        return {"direction": "unknown", "slope": 0}
    ma_current = sum(closes[-period:]) / period
    ma_past = sum(closes[-period - lookback: -lookback]) / period
    if ma_past == 0:
        return {"direction": "unknown", "slope": 0}
    slope = (ma_current - ma_past) / ma_past / lookback
    if slope > 0.001:
        direction = "up"
    elif slope < -0.001:
        direction = "down"
    else:
        direction = "flat"
    return {"direction": direction, "slope": round(slope, 6)}


def check_higher_lows(lows, window=20):
    """检查低点是否逐步抬高"""
    if len(lows) < window:
        return False
    recent_lows = lows[-window:]
    # 找出局部低点
    swing_lows = []
    for i in range(1, len(recent_lows) - 1):
        if recent_lows[i] < recent_lows[i - 1] and recent_lows[i] < recent_lows[i + 1]:
            swing_lows.append(recent_lows[i])
    if len(swing_lows) < 2:
        # 至少不应该创新低
        return recent_lows[-1] >= min(recent_lows[:-5]) if len(recent_lows) > 5 else True
    # 检查是否逐步抬高
    ascending = all(swing_lows[i] <= swing_lows[i + 1] for i in range(len(swing_lows) - 1))
    return ascending


def identify_box(closes, volumes, min_days=15, volatility_threshold=0.08):
    """
    识别箱体震荡形态
    返回: {is_box, box_high, box_low, consolidation_days, shrinking_volume}
    """
    if len(closes) < min_days:
        return {"is_box": False, "box_high": None, "box_low": None,
                "consolidation_days": 0, "shrinking_volume": False}

    # 从最近往前找箱体
    for start in range(len(closes) - min_days, -1, -1):
        segment = closes[start:]
        seg_high = max(segment)
        seg_low = min(segment)
        if seg_low == 0:
            continue
        volatility = (seg_high - seg_low) / seg_low
        if volatility <= volatility_threshold:
            days = len(segment)
            # 检查缩量
            if volumes and len(volumes) >= days:
                seg_volumes = volumes[start:]
                avg_vol_first_half = sum(seg_volumes[:days // 2]) / max(days // 2, 1)
                avg_vol_second_half = sum(seg_volumes[days // 2:]) / max(days - days // 2, 1)
                shrinking = avg_vol_second_half < avg_vol_first_half * 0.9
            else:
                shrinking = False
            # 检查是否突破上沿
            current_close = closes[-1]
            breakout = current_close > seg_high * 0.98  # 接近或突破上沿
            return {
                "is_box": True,
                "box_high": round(seg_high, 2),
                "box_low": round(seg_low, 2),
                "consolidation_days": days,
                "shrinking_volume": shrinking,
                "breakout": breakout
            }
    return {"is_box": False, "box_high": None, "box_low": None,
            "consolidation_days": 0, "shrinking_volume": False, "breakout": False}


def identify_pullback_start(closes, volumes, ma20):
    """
    识别多头回踩启动形态
    返回: {is_pullback_start, details}
    """
    if ma20 is None or len(closes) < 30:
        return {"is_pullback_start": False, "details": "数据不足"}

    # MA20 向上（与5日前比较）
    if len(closes) < 25:
        return {"is_pullback_start": False, "details": "数据不足"}
    ma20_5days_ago = sum(closes[-25:-5]) / 20
    ma20_upward = ma20 > ma20_5days_ago

    # 回调过程中未有效跌破 MA20（近10日内最低价 >= MA20 * 0.97）
    recent_lows = [min(closes[i], closes[i - 1]) for i in range(max(1, len(closes) - 10), len(closes))]
    # 用 close 近似
    recent_closes = closes[-10:]
    min_recent = min(recent_closes)
    not_broken_ma20 = min_recent >= ma20 * 0.97

    # 重新放量收阳线（最后一根阳线且量比 > 1.2）
    last_close = closes[-1]
    prev_close = closes[-2] if len(closes) >= 2 else last_close
    is_bullish = last_close > prev_close
    if volumes and len(volumes) >= 21:
        avg_vol_20 = sum(volumes[-21:-1]) / 20
        current_vol = volumes[-1]
        volume_ratio = current_vol / avg_vol_20 if avg_vol_20 > 0 else 0
        re_volume = volume_ratio > 1.2
    else:
        volume_ratio = 0
        re_volume = False

    is_pullback = ma20_upward and not_broken_ma20 and is_bullish and re_volume
    return {
        "is_pullback_start": is_pullback,
        "details": {
            "ma20_upward": ma20_upward,
            "not_broken_ma20": not_broken_ma20,
            "bullish_candle": is_bullish,
            "re_volume": re_volume,
            "volume_ratio": round(volume_ratio, 2)
        }
    }


def calculate_volume_ratio(volumes, period=20):
    """计算量比（当日成交量 / N日均量）"""
    if len(volumes) < period + 1:
        return 0
    avg_vol = sum(volumes[-period - 1: -1]) / period
    current_vol = volumes[-1]
    return round(current_vol / avg_vol, 2) if avg_vol > 0 else 0


def calculate_avg_amount(amounts, period=20):
    """计算N日平均成交额"""
    if len(amounts) < period:
        return sum(amounts) / len(amounts) if amounts else 0
    return sum(amounts[-period:]) / period


def calculate_recent_rally(closes, days=10):
    """计算近N日涨幅"""
    if len(closes) < days + 1:
        return 0
    return round((closes[-1] / closes[-days - 1] - 1) * 100, 2)


# ============================================================
# 数据解析
# ============================================================

def parse_kline(data):
    """解析 K 线数据（westock-data 返回直接 JSON 数组）"""
    if not data:
        return []
    # westock-data --raw 返回直接 JSON 数组
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("data", data.get("items", data.get("klines", [])))
        if not isinstance(items, list):
            return []
    else:
        return []
    result = []
    for item in items:
        if isinstance(item, dict):
            result.append({
                "date": item.get("date", item.get("time", "")),
                "open": safe_float(item.get("open", item.get("Open", 0))),
                "close": safe_float(item.get("last", item.get("close", item.get("Close", item.get("last_close", 0))))),
                "high": safe_float(item.get("high", item.get("High", 0))),
                "low": safe_float(item.get("low", item.get("Low", 0))),
                "volume": safe_float(item.get("volume", item.get("Volume", 0))),
                "amount": safe_float(item.get("amount", item.get("Amount", item.get("turnover", 0))))
            })
        elif isinstance(item, list) and len(item) >= 6:
            result.append({
                "date": str(item[0]),
                "open": safe_float(item[1]),
                "close": safe_float(item[2]) if len(item) > 2 else safe_float(item[1]),
                "high": safe_float(item[3]) if len(item) > 3 else safe_float(item[1]),
                "low": safe_float(item[4]) if len(item) > 4 else safe_float(item[1]),
                "volume": safe_float(item[5]) if len(item) > 5 else 0,
                "amount": safe_float(item[6]) if len(item) > 6 else 0
            })
    # 反转使日期从旧到新
    if result and result[0].get("date", "") > result[-1].get("date", ""):
        result.reverse()
    return result


def parse_profile(data):
    """解析公司简况"""
    if not data or not isinstance(data, dict):
        return {}
    info = data.get("data", data)
    if isinstance(info, list) and info:
        info = info[0]
    return {
        "name": info.get("name", info.get("Name", "")),
        "industry": info.get("industry", info.get("Industry", "")),
        "sector": info.get("sector", info.get("Sector", "")),
        "market_cap": safe_float(info.get("market_cap", info.get("MarketCap", 0))),
        "circ_market_cap": safe_float(info.get("circ_market_cap", info.get("CircMarketCap", 0)))
    }


def parse_fund_flow(data):
    """解析资金流向（westock-data 返回直接 JSON 数组）"""
    if not data:
        return {}
    # westock-data --raw 返回直接 JSON 数组
    if isinstance(data, list):
        info = data[0] if data and isinstance(data[0], dict) else {}
    elif isinstance(data, dict):
        info = data.get("data", data)
        if isinstance(info, list) and info:
            info = info[0] if isinstance(info[0], dict) else {}
        elif not isinstance(info, dict):
            info = {}
    else:
        info = {}
    return {
        "main_net_flow": safe_float(info.get("MainNetFlow", info.get("main_net_flow", 0))),
        "main_net_flow_5d": safe_float(info.get("MainNetFlow5D", info.get("main_net_flow_5d", 0))),
        "main_net_flow_10d": safe_float(info.get("MainNetFlow10D", info.get("main_net_flow_10d", 0))),
        "main_net_flow_20d": safe_float(info.get("MainNetFlow20D", info.get("main_net_flow_20d", 0))),
        "main_inflow_rank": info.get("MainInflowRank", ""),
        "main_inflow_industry_rank": info.get("MainInflowIndustryRank", ""),
        "close_price": safe_float(info.get("ClosePrice", 0))
    }


def parse_risk(data):
    """解析风险事件（westock-data 返回直接 JSON 数组，字段名为中文）"""
    if not data:
        return {"has_risk": False, "details": []}
    # westock-data --raw 返回直接 JSON 数组
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("data", data.get("items", []))
        if not isinstance(items, list):
            items = []
    else:
        items = []
    risks = []
    for item in items:
        if isinstance(item, dict):
            # 中文键映射
            keys = list(item.keys())
            risk_type = "unknown"
            if any("质押" in k for k in keys):
                risk_type = "pledge"
            elif any("解禁" in k for k in keys):
                risk_type = "unlock"
            elif any("ST" in k or "special" in k.lower() for k in keys):
                risk_type = "specialtrade"
            elif any("诉讼" in k for k in keys):
                risk_type = "lawsuit"
            elif any("增发" in k for k in keys):
                risk_type = "seasonedissue"
            elif any("高管" in k for k in keys):
                risk_type = "executivetransfer"
            risks.append({
                "type": risk_type,
                "description": json.dumps(item, ensure_ascii=False)[:200],
                "date": item.get("日期", item.get("date", ""))
            })
    return {"has_risk": len(risks) > 0, "details": risks}


def parse_quote(data):
    """解析实时行情"""
    if not data or not isinstance(data, dict):
        return {}
    items = data.get("data", data.get("items", []))
    if isinstance(items, list) and items:
        info = items[0]
    elif isinstance(items, dict):
        info = items
    else:
        info = data.get("data", {})
    return {
        "close": safe_float(info.get("last", info.get("close", info.get("Last", 0)))),
        "change_pct": safe_float(info.get("change_pct", info.get("ChangePct", 0))),
        "amount": safe_float(info.get("amount", info.get("Amount", 0))),
        "volume": safe_float(info.get("volume", info.get("Volume", 0))),
        "market_cap": safe_float(info.get("market_cap", info.get("MarketCap", 0)))
    }


# ============================================================
# 八维信号检查
# ============================================================

def check_trend_filter(kline, config):
    """一、大趋势过滤"""
    if len(kline) < 30:
        return {"pass": False, "reason": "K线数据不足30日", "details": {}}

    closes = [k["close"] for k in kline if k["close"]]
    lows = [k["low"] for k in kline if k["low"]]

    ma20 = calculate_ma(closes, 20)
    ma20_slope = calculate_ma_slope(closes, 20, config["thresholds"]["ma60_slope_days"])
    above_ma20 = closes[-1] > ma20 if ma20 else False
    higher_lows = check_higher_lows(lows, config["thresholds"]["higher_lows_window"])

    # 非下降趋势：MA5 > MA20 或 MA20 斜率非向下
    ma5 = calculate_ma(closes, 5)
    not_downtrend = (ma5 > ma20 if ma5 and ma20 else True)

    passed = (ma20_slope["direction"] in ["flat", "up"]) and above_ma20 and higher_lows and not_downtrend

    return {
        "pass": passed,
        "reason": "" if passed else "趋势过滤未通过",
        "details": {
            "ma20": round(ma20, 2) if ma20 else None,
            "ma20_direction": ma20_slope["direction"],
            "ma20_slope": ma20_slope["slope"],
            "above_ma20": above_ma20,
            "higher_lows": higher_lows,
            "not_downtrend": not_downtrend,
            "ma5": round(ma5, 2) if ma5 else None
        }
    }


def check_right_side(kline, config):
    """二、右侧确认形态（二选一）"""
    if len(kline) < 30:
        return {"pass": False, "reason": "K线数据不足", "pattern": None, "details": {}}

    closes = [k["close"] for k in kline if k["close"]]
    volumes = [k["volume"] for k in kline if k["volume"]]
    ma20 = calculate_ma(closes, 20)

    # 方案A：箱体突破
    box = identify_box(
        closes, volumes,
        min_days=config["thresholds"]["box_consolidation_days"],
        volatility_threshold=config["thresholds"]["box_volatility_threshold"]
    )
    vol_ratio = calculate_volume_ratio(volumes)
    box_breakout_pass = (
        box["is_box"] and
        box["breakout"] and
        vol_ratio >= config["thresholds"]["breakout_volume_ratio"] and
        box["shrinking_volume"]
    )

    # 方案B：多头回踩启动
    pullback = identify_pullback_start(closes, volumes, ma20)
    pullback_pass = pullback["is_pullback_start"]

    if box_breakout_pass:
        return {
            "pass": True,
            "pattern": "box_breakout",
            "reason": "",
            "details": {
                "box_high": box["box_high"],
                "box_low": box["box_low"],
                "consolidation_days": box["consolidation_days"],
                "shrinking_volume": box["shrinking_volume"],
                "volume_ratio": vol_ratio,
                "breakout_volume_ratio_required": config["thresholds"]["breakout_volume_ratio"]
            }
        }
    elif pullback_pass:
        return {
            "pass": True,
            "pattern": "pullback_start",
            "reason": "",
            "details": pullback["details"]
        }
    else:
        return {
            "pass": False,
            "pattern": None,
            "reason": "无箱体突破或回踩启动信号",
            "details": {
                "box_detected": box["is_box"],
                "box_breakout": box["breakout"],
                "volume_ratio": vol_ratio,
                "pullback_check": pullback["details"]
            }
        }


def check_volume(kline, config):
    """三、量能硬性标准"""
    if len(kline) < 25:
        return {"pass": False, "reason": "数据不足", "details": {}}

    closes = [k["close"] for k in kline if k["close"]]
    volumes = [k["volume"] for k in kline if k["volume"]]

    # 启动阳线放量
    last_close = closes[-1]
    prev_close = closes[-2]
    is_bullish = last_close > prev_close
    vol_ratio = calculate_volume_ratio(volumes)
    launch_volume = is_bullish and vol_ratio >= config["thresholds"]["breakout_volume_ratio"]

    # 无量虚拉检查：近3日平均量比 < 0.8 视为无量虚拉
    if len(volumes) >= 23:
        recent_avg_vol = sum(volumes[-3:]) / 3
        base_avg_vol = sum(volumes[-23:-3]) / 20
        no_virtual_rally = recent_avg_vol >= base_avg_vol * 0.7
    else:
        no_virtual_rally = True

    passed = launch_volume and no_virtual_rally

    return {
        "pass": passed,
        "reason": "" if passed else "量能不达标",
        "details": {
            "is_bullish": is_bullish,
            "volume_ratio": vol_ratio,
            "launch_volume": launch_volume,
            "no_virtual_rally": no_virtual_rally
        }
    }


def check_sector_resonance(stock_data, config):
    """四、板块 & 市场环境共振"""
    # 此项需要板块数据，由 Agent 补充或从 sector ranking 获取
    # screener.py 做基础判断，Agent 可覆盖
    industry = stock_data.get("industry", "")
    sector = stock_data.get("sector", "")
    fund_flow = stock_data.get("fund_flow", {})

    # 主力资金近5日净流入为正 → 板块资金面支撑
    main_5d = fund_flow.get("main_net_flow_5d", 0)
    sector_capital_support = main_5d > 0

    # 默认通过（Agent 可根据板块排行数据覆盖）
    return {
        "pass": True,
        "reason": "",
        "details": {
            "industry": industry,
            "sector": sector,
            "main_net_flow_5d": main_5d,
            "sector_capital_support": sector_capital_support,
            "note": "Agent需根据板块排行数据确认板块是否强于大盘"
        },
        "agent_override": True
    }


def check_fundamental_risk(stock_data, config):
    """五、基本面 & 流动性避雷（满足任意一条直接放弃）"""
    risk_data = stock_data.get("risk", {})
    quote = stock_data.get("quote", {})
    kline = stock_data.get("kline", [])

    risks = []
    risk_details = risk_data.get("details", [])

    # 检查风险事件
    for r in risk_details:
        r_type = r.get("type", "").lower()
        if "unlock" in r_type or "解禁" in r_type:
            risks.append("存在解禁风险")
        if "executive" in r_type or "减持" in r_type:
            risks.append("存在高管减持")
        if "st" in r_type or "specialtrade" in r_type:
            risks.append("ST个股")

    # ST 检查（从名称）
    name = stock_data.get("name", "")
    if "ST" in name or "*ST" in name:
        risks.append("ST个股")

    # 日均成交额检查
    amounts = [k["amount"] for k in kline if k.get("amount")]
    avg_amount = calculate_avg_amount(amounts, 20) if len(amounts) >= 20 else (sum(amounts) / len(amounts) if amounts else 0)
    if avg_amount < config["screening"]["min_amount"]:
        risks.append("日均成交额不足1.5亿")

    # 短期连续拉升超30%
    closes = [k["close"] for k in kline if k.get("close")]
    rally_10d = calculate_recent_rally(closes, 10)
    rally_20d = calculate_recent_rally(closes, 20) if len(closes) > 20 else 0
    max_rally = max(rally_10d, rally_20d)
    if max_rally > config["thresholds"]["high_rally_threshold"]:
        risks.append("短期涨幅超30%")

    passed = len(risks) == 0
    return {
        "pass": passed,
        "reason": "；".join(risks) if risks else "",
        "details": {
            "avg_amount": round(avg_amount, 0),
            "rally_10d": rally_10d,
            "rally_20d": rally_20d,
            "risk_events": risk_details
        },
        "exclusion": not passed
    }


def check_risk_planning(kline, config):
    """六、风控提前规划"""
    if len(kline) < 20:
        return {"pass": False, "reason": "数据不足", "details": {}}

    closes = [k["close"] for k in kline if k["close"]]
    lows = [k["low"] for k in kline if k["low"]]

    current_close = closes[-1]
    ma20 = calculate_ma(closes, 20)

    # 防守支撑位：近期低点或 MA20
    recent_low = min(lows[-20:]) if len(lows) >= 20 else min(lows)
    support_level = max(recent_low, ma20 * 0.97) if ma20 else recent_low

    # 测算最大亏损
    max_loss_pct = round((support_level / current_close - 1) * 100, 2)
    max_loss_threshold = config["thresholds"]["max_loss_pct"]

    # 止盈目标
    take_profit_target = round(current_close * (1 + config["thresholds"]["take_profit_pct"] / 100), 2)

    # 盈亏比
    profit_pct = config["thresholds"]["take_profit_pct"]
    loss_pct = abs(max_loss_pct)
    risk_reward = round(profit_pct / loss_pct, 2) if loss_pct > 0 else 999

    passed = max_loss_pct >= max_loss_threshold

    return {
        "pass": passed,
        "reason": "" if passed else f"最大亏损{max_loss_pct}%超过{max_loss_threshold}%",
        "details": {
            "current_close": round(current_close, 2),
            "support_level": round(support_level, 2),
            "stop_loss": round(support_level, 2),
            "max_loss_pct": max_loss_pct,
            "max_loss_threshold": max_loss_threshold,
            "take_profit_target": take_profit_target,
            "take_profit_pct": config["thresholds"]["take_profit_pct"],
            "risk_reward": risk_reward,
            "good_risk_reward": risk_reward >= 1.5
        }
    }


def check_holding_period(config):
    """七、持仓时间约束"""
    return {
        "pass": True,
        "reason": "",
        "details": {
            "min_days": config["thresholds"]["min_holding_days"],
            "max_days": config["thresholds"]["max_holding_days"],
            "take_profit_pct": config["thresholds"]["take_profit_pct"],
            "max_loss_pct": config["thresholds"]["max_loss_pct"],
            "rule": "满20个交易日未达止盈目标无条件离场"
        }
    }


def final_scoring(checks, config):
    """八、最终综合打分"""
    weights = config["weights"]
    max_score = sum(weights.values())
    score = 0
    score_details = {}

    for category, check in checks.items():
        weight = weights.get(category, 1.0)
        if check.get("pass", False):
            score += weight
            score_details[category] = {"weight": weight, "passed": True, "contribution": weight}
        else:
            score_details[category] = {"weight": weight, "passed": False, "contribution": 0}

    # 转换为 0-100 分
    final_score = round(score / max_score * 100, 1) if max_score > 0 else 0

    # 盈亏比加分
    risk_planning = checks.get("risk_planning", {})
    risk_reward = risk_planning.get("details", {}).get("risk_reward", 0)
    bonus = 0
    if risk_reward >= 3:
        bonus = 5
    elif risk_reward >= 2:
        bonus = 3
    elif risk_reward >= 1.5:
        bonus = 1

    final_score = min(100, final_score + bonus)

    # 信号共振度：通过的核心维度数量
    core_categories = ["trend_filter", "right_side", "volume", "fundamental_risk"]
    core_passed = sum(1 for c in core_categories if checks.get(c, {}).get("pass", False))
    resonance = "强共振" if core_passed == 4 else "中共振" if core_passed >= 3 else "弱共振"

    return {
        "pass": final_score >= 60 and core_passed >= 3,
        "score": final_score,
        "resonance": resonance,
        "bonus": bonus,
        "details": score_details
    }


# ============================================================
# 单只股票完整筛查
# ============================================================

def screen_stock(code, config):
    """对单只股票执行完整八维筛查"""
    lookback = config["screening"]["lookback_days"]

    # 1. 采集数据（quote 命令不存在，用 K线最后一根获取当前价/成交额）
    kline_data = run_westock(["kline", code, "--period", "day", "--limit", str(lookback + 10)], raw=True)
    profile_data = run_westock(["profile", code], raw=True)
    flow_data = run_westock(["fund", "flow", code], raw=True)
    risk_data = run_westock(["risk", code], raw=True)

    # 2. 解析数据
    kline = parse_kline(kline_data)
    if len(kline) < 20:
        return {
            "code": code,
            "screened": False,
            "reason": "K线数据不足",
            "checks": {},
            "indicators": {}
        }

    profile = parse_profile(profile_data)
    fund_flow = parse_fund_flow(flow_data)
    risk = parse_risk(risk_data)

    # 从 K线最后一根获取当前行情
    last_bar = kline[-1] if kline else {}
    quote = {
        "close": last_bar.get("close", 0),
        "amount": last_bar.get("amount", 0),
        "volume": last_bar.get("volume", 0)
    }

    stock_data = {
        "code": code,
        "name": profile.get("name", ""),
        "industry": profile.get("industry", ""),
        "sector": profile.get("sector", ""),
        "kline": kline,
        "fund_flow": fund_flow,
        "risk": risk,
        "quote": quote
    }

    # 3. 计算技术指标
    closes = [k["close"] for k in kline if k["close"]]
    highs = [k["high"] for k in kline if k["high"]]
    lows = [k["low"] for k in kline if k["low"]]
    volumes = [k["volume"] for k in kline if k["volume"]]
    amounts = [k["amount"] for k in kline if k["amount"]]

    indicators = {
        "ma5": round(calculate_ma(closes, 5), 2) if len(closes) >= 5 else None,
        "ma10": round(calculate_ma(closes, 10), 2) if len(closes) >= 10 else None,
        "ma20": round(calculate_ma(closes, 20), 2) if len(closes) >= 20 else None,
        "ma60": round(calculate_ma(closes, 60), 2) if len(closes) >= 60 else None,
        "macd": calculate_macd(closes),
        "kdj": calculate_kdj(highs, lows, closes),
        "rsi6": calculate_rsi(closes, 6),
        "rsi12": calculate_rsi(closes, 12),
        "boll": calculate_boll(closes),
        "volume_ratio": calculate_volume_ratio(volumes),
        "avg_amount_20d": round(calculate_avg_amount(amounts, 20), 0),
        "rally_10d": calculate_recent_rally(closes, 10),
        "rally_20d": calculate_recent_rally(closes, 20) if len(closes) > 20 else 0,
        "close": round(closes[-1], 2),
        "ma20_slope": calculate_ma_slope(closes, 20, config["thresholds"]["ma60_slope_days"])
    }

    # 4. 执行八维检查
    checks = {
        "trend_filter": check_trend_filter(kline, config),
        "right_side": check_right_side(kline, config),
        "volume": check_volume(kline, config),
        "sector_resonance": check_sector_resonance(stock_data, config),
        "fundamental_risk": check_fundamental_risk(stock_data, config),
        "risk_planning": check_risk_planning(kline, config),
        "holding_period": check_holding_period(config)
    }

    # 5. 综合打分
    checks["final_score"] = final_scoring(checks, config)

    # 6. 判断是否通过
    # 核心维度必须全部通过
    core_pass = (
        checks["trend_filter"]["pass"] and
        checks["right_side"]["pass"] and
        checks["fundamental_risk"]["pass"] and
        checks["risk_planning"]["pass"]
    )
    screened = core_pass and checks["final_score"]["pass"]

    return {
        "code": code,
        "name": stock_data["name"],
        "industry": stock_data["industry"],
        "sector": stock_data["sector"],
        "close": indicators["close"],
        "indicators": indicators,
        "fund_flow": fund_flow,
        "checks": checks,
        "signal_type": checks["right_side"].get("pattern", ""),
        "score": checks["final_score"]["score"],
        "resonance": checks["final_score"]["resonance"],
        "stop_loss": checks["risk_planning"]["details"].get("stop_loss"),
        "take_profit_target": checks["risk_planning"]["details"].get("take_profit_target"),
        "max_loss_pct": checks["risk_planning"]["details"].get("max_loss_pct"),
        "risk_reward": checks["risk_planning"]["details"].get("risk_reward"),
        "screened": screened,
        "reason": "" if screened else _get_fail_reason(checks)
    }


def _get_fail_reason(checks):
    """获取未通过的主要原因"""
    for category in ["trend_filter", "right_side", "volume", "fundamental_risk", "risk_planning"]:
        check = checks.get(category, {})
        if not check.get("pass", False):
            return check.get("reason", f"{category}未通过")
    return "综合打分不足"


# ============================================================
# 候选池生成
# ============================================================

def generate_candidates(config, filters=None):
    """多源融合生成候选池"""
    filters = filters or {}
    candidates = set()

    # 来源1：板块龙头
    print("[候选池] 采集板块龙头...", file=sys.stderr)
    ranking = run_westock(["sector", "ranking"], raw=True)
    if ranking.get("success", True):
        sectors = ranking.get("data", {}).get("industry_ranking", [])
        if not isinstance(sectors, list):
            sectors = ranking.get("data", {}).get("sectors", [])
        for sector in sectors[:5]:
            if isinstance(sector, dict):
                sector_code = sector.get("code", sector.get("SectorCode", ""))
                if sector_code:
                    constituents = run_westock(["sector", "constituent", sector_code], raw=True)
                    if constituents.get("success", True):
                        stocks = constituents.get("data", {}).get("constituents", [])
                        if not isinstance(stocks, list):
                            stocks = constituents.get("data", [])
                        for stock in stocks[:5]:
                            if isinstance(stock, dict):
                                code = stock.get("code", stock.get("Code", ""))
                                if code:
                                    candidates.add(code)

    # 来源2：龙虎榜
    print("[候选池] 采集龙虎榜...", file=sys.stderr)
    lhb = run_westock(["lhb", "--type", "institution,hotmoney"], raw=True)
    if lhb.get("success", True):
        lhb_stocks = lhb.get("data", {}).get("stocks", [])
        if not isinstance(lhb_stocks, list):
            lhb_stocks = lhb.get("data", [])
        for stock in lhb_stocks[:20]:
            if isinstance(stock, dict):
                code = stock.get("code", stock.get("Code", ""))
                if code:
                    candidates.add(code)

    # 应用过滤
    filtered = []
    for code in candidates:
        if not code:
            continue
        if filters.get("exclude_300") and code.startswith("sz300"):
            continue
        if filters.get("exclude_688") and code.startswith("sh688"):
            continue
        if filters.get("exclude_bj") and code.startswith("bj"):
            continue
        if filters.get("industry"):
            # 行业过滤在 screen 阶段处理
            pass
        filtered.append(code)

    return filtered


# ============================================================
# 主函数
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="右侧选股引擎 - 核心筛选脚本")
    parser.add_argument("--phase", choices=["candidates", "screen", "full"], required=True,
                        help="执行阶段：candidates=生成候选池，screen=逐只筛查，full=完整流程")
    parser.add_argument("--data-dir", required=True, help="数据目录路径")
    parser.add_argument("--stocks", help="逗号分隔的股票代码列表（screen阶段使用）")
    parser.add_argument("--industry", help="指定行业过滤")
    parser.add_argument("--exclude-300", action="store_true", help="排除创业板")
    parser.add_argument("--exclude-688", action="store_true", help="排除科创板")
    parser.add_argument("--exclude-bj", action="store_true", help="排除北交所")
    parser.add_argument("--min-amount", type=float, help="最小日均成交额")
    parser.add_argument("--target-count", type=int, help="目标选股数量")
    parser.add_argument("--lookback", type=int, help="回看天数")
    parser.add_argument("--output", help="输出文件路径")

    args = parser.parse_args()

    # 确保目录存在
    ensure_dirs(args.data_dir)

    # 加载配置
    config = load_config(args.data_dir)

    # 应用命令行覆盖
    if args.min_amount:
        config["screening"]["min_amount"] = args.min_amount
    if args.target_count:
        config["screening"]["target_count"] = args.target_count
    if args.lookback:
        config["screening"]["lookback_days"] = args.lookback

    filters = {
        "exclude_300": args.exclude_300 or config["screening"].get("exclude_300", False),
        "exclude_688": args.exclude_688 or config["screening"].get("exclude_688", False),
        "exclude_bj": args.exclude_bj or config["screening"].get("exclude_bj", True),
        "industry": args.industry
    }

    today = get_today()
    result = {
        "run_date": today,
        "run_time": datetime.now().isoformat(),
        "config_version": config["version"],
        "phase": args.phase,
        "filters": filters
    }

    if args.phase in ["candidates", "full"]:
        candidates = generate_candidates(config, filters)
        result["candidates"] = candidates
        result["candidates_count"] = len(candidates)
        print(f"[候选池] 共生成 {len(candidates)} 只候选股票", file=sys.stderr)

        if args.phase == "candidates":
            # 仅输出候选池
            stocks_to_screen = candidates
        else:
            stocks_to_screen = candidates
    else:
        # screen 阶段，使用 --stocks
        if not args.stocks:
            print("错误：screen阶段需要 --stocks 参数", file=sys.stderr)
            sys.exit(1)
        stocks_to_screen = [s.strip() for s in args.stocks.split(",") if s.strip()]

    if args.phase in ["screen", "full"]:
        # 逐只筛查
        screened_results = []
        excluded_results = []
        total = len(stocks_to_screen)

        for i, code in enumerate(stocks_to_screen):
            print(f"[筛查] ({i+1}/{total}) 正在筛查 {code}...", file=sys.stderr)
            stock_result = screen_stock(code, config)

            # 行业过滤
            if filters.get("industry") and stock_result.get("industry"):
                if filters["industry"] not in stock_result["industry"]:
                    stock_result["screened"] = False
                    stock_result["reason"] = f"行业不匹配（目标: {filters['industry']}）"
                    excluded_results.append(stock_result)
                    continue

            if stock_result["screened"]:
                screened_results.append(stock_result)
            else:
                excluded_results.append(stock_result)

        # 按评分排序
        screened_results.sort(key=lambda x: x.get("score", 0), reverse=True)

        # 截取目标数量
        target = config["screening"]["target_count"]
        if len(screened_results) > target:
            overflow = screened_results[target:]
            screened_results = screened_results[:target]
            for item in overflow:
                item["screened"] = False
                item["reason"] = "评分排名超出目标数量"
                excluded_results.append(item)

        result["results"] = screened_results
        result["excluded"] = excluded_results
        result["screened_count"] = len(screened_results)
        result["excluded_count"] = len(excluded_results)
        result["candidates_total"] = total

        # 保存跟踪记录
        history_dir = os.path.join(args.data_dir, "history", today.replace("-", ""))
        os.makedirs(history_dir, exist_ok=True)
        history_path = os.path.join(history_dir, "selection.json")
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["history_path"] = history_path
        print(f"[保存] 跟踪记录已保存到 {history_path}", file=sys.stderr)

    # 输出结果
    output_json = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"[输出] 结果已保存到 {args.output}", file=sys.stderr)
    else:
        print(output_json)


if __name__ == "__main__":
    main()

