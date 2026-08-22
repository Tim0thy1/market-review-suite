#!/usr/bin/env python3
"""
Sentinel_Daily_Pro.py - 美股每日数据采集增强版
双数据源架构：
  - Moomoo API：行业板块、概念板块、24小时新闻、要闻
  - WeStock Data：指数/ETF/个股K线、技术指标、宏观数据

用法：
  python Sentinel_Daily_Pro.py                    # 默认运行全部
  python Sentinel_Daily_Pro.py --date 2026-07-31     # 指定交易日期
  python Sentinel_Daily_Pro.py -o output.xlsx      # 指定输出文件
  python Sentinel_Daily_Pro.py --skip-moomoo         # 跳过moomoo数据（只用westock）
  python Sentinel_Daily_Pro.py --skip-westock       # 跳过westock数据（只用moomoo）
"""

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import json
import hashlib
import hmac
import time
import os
import argparse
import subprocess
import math
import pandas as pd
import random
from datetime import datetime, timezone, timedelta
import pytz

# ============================================================
# Part 1: Moomoo API 相关函数 (行业/概念/新闻)
# ============================================================

def hmac_encrypt(text, key):
    """HMAC-SHA512加密"""
    return hmac.new(key.encode('utf-8'), text.encode('utf-8'), hashlib.sha512).hexdigest()

def sha256_hash(text):
    """SHA256哈希"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def n_function(e, visited=None):
    """实现JavaScript中的N函数，正确处理循环引用和数组转换"""
    if visited is None:
        visited = set()
    obj_id = id(e)
    if obj_id in visited:
        return "[object Object]"
    visited.add(obj_id)
    t = {}
    for n in e:
        if n in e and e[n] is not None:
            r = e[n]
            if isinstance(r, dict):
                t[n] = "[object Object]"
            elif isinstance(r, list):
                array_str = ','.join(str(item) if item is not None else '' for item in r)
                t[n] = array_str
            else:
                t[n] = str(r)
    visited.remove(obj_id)
    return json.dumps(t, separators=(',', ':'))

def sss(e):
    """实现JavaScript中的sss函数"""
    data_str = json.dumps(e.get('data')) if e.get('data') is not None else None
    if not data_str:
        data_str = n_function(e.get('params', {}))
    if not data_str:
        data_str = "{}"
    if len(data_str) <= 0:
        data_str = "quote"
    t = hmac_encrypt(data_str, "quote_web")
    return sha256_hash(t[:10])[:10]

def get_plate_stock_token(params):
    """专门用于获取plate-stock的token"""
    aa = {
        "transitional": {"silentJSONParsing": True, "forcedJSONParsing": True, "clarifyTimeoutError": False},
        "adapter": ["xhr", "http"],
        "transformRequest": [None],
        "transformResponse": [None],
        "timeout": 5000,
        "xsrfCookieName": "XSRF-TOKEN",
        "xsrfHeaderName": "X-XSRF-TOKEN",
        "maxContentLength": -1,
        "maxBodyLength": -1,
        "env": {},
        "headers": {"Accept": "application/json, text/plain, */*", "futu-x-csrf-token": "cd1zage106rT3rMaO8V7P4Cx"},
        "baseURL": "/quote-api/quote-v2",
        "params": params,
        "method": "get",
        "url": "/get-plate-stock"
    }
    return sss(aa)

def get_plate_list_token(params):
    """专门用于获取plate-list的token (用于概念)"""
    aa = {
        "transitional": {"silentJSONParsing": True, "forcedJSONParsing": True, "clarifyTimeoutError": False},
        "adapter": ["xhr", "http"],
        "transformRequest": [None],
        "transformResponse": [None],
        "timeout": 5000,
        "xsrfCookieName": "XSRF-TOKEN",
        "xsrfHeaderName": "X-XSRF-TOKEN",
        "maxContentLength": -1,
        "maxBodyLength": -1,
        "env": {},
        "headers": {"Accept": "application/json, text/plain, */*", "futu-x-csrf-token": "cd1zage106rT3rMaO8V7P4Cx"},
        "baseURL": "/quote-api/quote-v2",
        "params": params,
        "method": "get",
        "url": "/get-plate-list"
    }
    return sss(aa)

def get_heatmap_token(params):
    """专门用于获取heatmap的token"""
    aa = {
        "transitional": {"silentJSONParsing": True, "forcedJSONParsing": True, "clarifyTimeoutError": False},
        "adapter": ["xhr", "http"],
        "transformRequest": [None],
        "transformResponse": [None],
        "timeout": 5000,
        "xsrfCookieName": "XSRF-TOKEN",
        "xsrfHeaderName": "X-XSRF-TOKEN",
        "maxContentLength": -1,
        "maxBodyLength": -1,
        "env": {},
        "headers": {"Accept": "application/json, text/plain, */*", "futu-x-csrf-token": "cd1zage106rT3rMaO8V7P4Cx"},
        "baseURL": "/quote-api/quote-v2",
        "params": params,
        "method": "get",
        "url": "/get-heatmap-industry-data"
    }
    return sss(aa)

def fetch_stocks_for_plates(plates, headers, plate_id_key='stockId', plate_name_key='plateName', type_name='Industry'):
    """获取板块成份股列表"""
    all_data = []
    for idx, plate in enumerate(plates):
        plate_id = plate.get(plate_id_key)
        plate_name = plate.get(plate_name_key, 'Unknown')
        if 'allName' in plate and 'strContext' in plate['allName']:
            for ctx in plate['allName']['strContext']:
                if ctx.get('languageId') == 0:
                    plate_name = ctx.get('context')
                    break
        elif plate_name == 'Unknown':
             plate_name = plate.get('plateName', plate.get('enName', 'Unknown'))
        print(f"[{idx+1}/{len(plates)} Fetching stocks for {type_name}: {plate_name} ({plate_id})...")
        stock_params = {
            "marketType": "2",
            "plateId": str(plate_id),
            "page": "0",
            "pageSize": "30",
            "_": str(int(time.time() * 1000))
        }
        stock_token = get_plate_stock_token(stock_params)
        stock_headers = headers.copy()
        stock_headers['quote-token'] = stock_token
        stock_url = "https://www.moomoo.com/quote-api/quote-v2/get-plate-stock"
        try:
            time.sleep(0.5)
            stock_response = requests.get(stock_url, params=stock_params, headers=stock_headers, timeout=10, verify=False)
            if stock_response.status_code == 200:
                stock_data = stock_response.json()
                if stock_data.get('code') == 0 and 'data' in stock_data and 'list' in stock_data['data']:
                    stock_list = stock_data['data']['list']
                    for stock in stock_list:
                        all_data.append({
                            f'{type_name}ID': plate_id,
                            f'{type_name}Name': plate_name,
                            'StockCode': stock.get('stockCode', ''),
                            'StockName': stock.get('stockName', ''),
                            'ChangeRatio': stock.get('changeRatio', '0%'),
                            'Price': stock.get('price', '0')
                        })
                else:
                    print(f"  -> No stock data found or error: {stock_data.get('message')}")
            else:
                print(f"  -> HTTP Error {stock_response.status_code}")
        except Exception as e:
            print(f"  -> Error fetching stocks: {e}")
    return all_data

def get_target_time_range():
    """获取目标时间范围 (根据北京时间)"""
    beijing = pytz.timezone('Asia/Shanghai')
    now_bj = datetime.now(beijing)
    weekday = now_bj.weekday()
    if weekday == 0:
        hours = 72 + 10
    elif weekday == 6:
        hours = 48 + 10
    else:
        hours = 24 + 10
    start_time = now_bj - timedelta(hours=hours)
    ts_start = int(start_time.timestamp())
    ts_end = int(now_bj.timestamp())
    return ts_start, ts_end

def ts_to_us_eastern(ts_str):
    """把Unix时间戳转为美东时间"""
    try:
        ts = int(ts_str)
        dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        eastern = pytz.timezone("America/New_York")
        dt_est = dt_utc.astimezone(eastern)
        return dt_est.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception:
        return ""

def fetch_futu_news(limit=10000):
    """获取富途快讯"""
    URL = "https://news.futunn.com/news-site-api/main/get-flash-list"
    PAGE_SIZE = 50
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Referer": "https://news.futunn.com/",
        "Accept": "application/json, text/plain, */*",
    }
    all_news = []
    seq_mark = ""
    retry = 0
    ts_start, ts_end = get_target_time_range()
    print(f"🎯 快讯目标时间范围: {datetime.fromtimestamp(ts_start)} 至 {datetime.fromtimestamp(ts_end)}")
    while len(all_news) < limit:
        params = {"pageSize": PAGE_SIZE, "_t": int(time.time() * 1000)}
        if seq_mark:
            params["seqMark"] = seq_mark
        try:
            resp = requests.get(URL, headers=HEADERS, params=params, timeout=10, verify=False)
            if resp.status_code != 200:
                print(f"❌ 请求失败 HTTP {resp.status_code}")
                break
            if not resp.text.strip():
                retry += 1
                if retry > 3:
                    print("⚠️ 连续返回空响应，放弃。")
                    break
                print(f"⚠️ 空响应，第 {retry} 次重试 ...")
                time.sleep(2 + random.random())
                continue
            data = resp.json()
            items = data.get("data", {}).get("data", {}).get("news", [])
            seq_mark = data.get("data", {}).get("data", {}).get("seqMark")
            if not items:
                print("⚠️ 没有更多数据或被屏蔽。")
                break
            last_item_time = int(items[-1].get("time"))
            for item in items:
                item_time = int(item.get("time"))
                if ts_start <= item_time < ts_end:
                    all_news.append(item)
            print(f"✅ 已抓取 {len(all_news)} 条符合条件的快讯 (当前批次最旧时间: {datetime.fromtimestamp(last_item_time)}) ...")
            if last_item_time < ts_start:
                print("🏁 已到达目标时间之前的数据，停止抓取。")
                break
            if not data.get("data", {}).get("data", {}).get("hasMore"):
                break
            time.sleep(1.2 + random.random() * 0.8)
        except Exception as e:
            print(f"⚠️ 抓取异常: {e}")
            time.sleep(2)
            continue
    return all_news

def fetch_futu_market_news(limit=1000):
    """获取富途要闻"""
    URL = "https://news.futunn.com/news-site-api/main/get-market-list"
    PAGE_SIZE = 50
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Referer": "https://news.futunn.com/",
        "Accept": "application/json, text/plain, */*",
    }
    all_news = []
    seq_mark = ""
    retry = 0
    ts_start, ts_end = get_target_time_range()
    print(f"🎯 要闻目标时间范围: {datetime.fromtimestamp(ts_start)} 至 {datetime.fromtimestamp(ts_end)}")
    while len(all_news) < limit:
        params = {"size": PAGE_SIZE, "isSupportWebp": "true", "_t": int(time.time() * 1000)}
        if seq_mark:
            params["seqMark"] = seq_mark
        try:
            resp = requests.get(URL, headers=HEADERS, params=params, timeout=10, verify=False)
            if resp.status_code != 200:
                print(f"❌ 请求失败 HTTP {resp.status_code}")
                break
            data = resp.json()
            if data.get("code") != 0:
                print(f"❌ API Error: {data.get('message')}")
                break
            items = data.get("data", {}).get("list", [])
            seq_mark = data.get("data", {}).get("seqMark")
            has_more = data.get("data", {}).get("hasMore")
            if not items:
                print("⚠️ 没有更多数据。")
                break
            last_item_time = int(items[-1].get("timestamp", 0))
            for item in items:
                item_time = int(item.get("timestamp", 0))
                if ts_start <= item_time < ts_end:
                    all_news.append(item)
            print(f"✅ 已抓取 {len(all_news)} 条符合条件的要闻 (当前批次最旧时间: {datetime.fromtimestamp(last_item_time)}) ...")
            if last_item_time < ts_start:
                print("🏁 要闻已到达目标时间之前的数据，停止抓取。")
                break
            if not has_more:
                break
            time.sleep(1.2 + random.random() * 0.8)
        except Exception as e:
            print(f"⚠️ 抓取异常: {e}")
            time.sleep(2)
            continue
    return all_news


# ============================================================
# Part 2: WeStock Data 相关函数 (K线/技术指标/宏观)
# ============================================================

WESTOCK_CMD = "npx -y westock-data-skillhub@1.0.5"

def run_westock(cmd_args):
    """运行westock命令并返回解析后的JSON"""
    full_cmd = f"{WESTOCK_CMD} {cmd_args} --raw"
    try:
        result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=120)
        output = result.stdout.strip()
        if not output:
            return None
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('[') or line.startswith('{'):
                    try:
                        return json.loads(line)
                    except:
                        continue
            return None
    except Exception as e:
        print(f"  Error running westock command: {e}")
        return None

def get_kline(code, period="day", limit=20):
    """获取单只标的K线"""
    data = run_westock(f"kline {code} --period {period} --limit {limit}")
    return data

def get_technical(code, indicator="macd,rsi,kdj,boll,ma"):
    """获取技术指标"""
    data = run_westock(f"technical {code} --indicator {indicator}")
    return data

def get_macro_us(date_str):
    """获取美国宏观数据"""
    data = run_westock(f"macro indicator us_core --date {date_str}")
    return data

# 核心标的配置
INDEX_CODES = {
    "纳斯达克": "usIXIC",
    "标普500": "usINX",
    "道琼斯": "usDJI",
    "罗素2000": "usRUT",
    "VIX恐慌指数": "usVIX",
}

MAG7_CODES = {
    "AAPL": "usAAPL.OQ",
    "MSFT": "usMSFT.OQ",
    "GOOGL": "usGOOGL.OQ",
    "AMZN": "usAMZN.OQ",
    "META": "usMETA.OQ",
    "NVDA": "usNVDA.OQ",
    "TSLA": "usTSLA.OQ",
}

ETF_CODES = {
    "QQQ(纳指100)": "usQQQ.OQ",
    "SOXX(半导体)": "usSOXX.OQ",
    "SMH(半导体)": "usSMH.OQ",
    "XLK(科技)": "usXLK.OQ",
    "XLF(金融)": "usXLF.OQ",
    "XLE(能源)": "usXLE.OQ",
    "XLV(医疗)": "usXLV.OQ",
    "XLU(公用事业)": "usXLU.OQ",
    "XLP(必需消费)": "usXLP.OQ",
    "XLY(可选消费)": "usXLY.OQ",
    "XLI(工业)": "usXLI.OQ",
    "XLB(材料)": "usXLB.OQ",
    "XLRE(房地产)": "usXLRE.OQ",
    "XLC(通信)": "usXLC.OQ",
    "IWM(小盘)": "usIWM.A",
    "SOXL(半导体3x多)": "usSOXL.OQ",
    "SOXS(半导体3x空)": "usSOXS.OQ",
    "TQQQ(纳指3x多)": "usTQQQ.OQ",
    "SQQQ(纳指3x空)": "usSQQQ.OQ",
    "ARKK(创新)": "usARKK.OQ",
    "IBB(生物科技)": "usIBB.OQ",
    "XBI(生物科技)": "usXBI.OQ",
    "GLD(黄金)": "usGLD.OQ",
    "GDX(金矿)": "usGDX.OQ",
    "USO(原油)": "usUSO.OQ",
}

SEMICONDUCTOR_STOCKS = {
    "AMD": "usAMD.OQ",
    "AVGO": "usAVGO.OQ",
    "ARM": "usARM.OQ",
    "MU": "usMU.OQ",
    "INTC": "usINTC.OQ",
    "AMAT": "usAMAT.OQ",
    "LRCX": "usLRCX.OQ",
    "KLAC": "usKLAC.OQ",
    "QCOM": "usQCOM.OQ",
    "MRVL": "usMRVL.OQ",
    "TSM": "usTSM.N",
    "TXN": "usTXN.OQ",
    "NVDA": "usNVDA.OQ",
}

AI_INFRA_STOCKS = {
    "PLTR": "usPLTR.N",
    "COIN": "usCOIN.OQ",
    "SMCI": "usSMCI.OQ",
    "DELL": "usDELL.N",
    "NOW": "usNOW.N",
    "DDOG": "usDDOG.OQ",
    "CRM": "usCRM.N",
    "ORCL": "usORCL.N",
    "ADBE": "usADBE.OQ",
    "NFLX": "usNFLX.OQ",
}

FINANCIAL_STOCKS = {
    "JPM": "usJPM.N",
    "BAC": "usBAC.N",
    "GS": "usGS.N",
    "MS": "usMS.N",
    "BLK": "usBLK.N",
}

ENERGY_STOCKS = {
    "XOM": "usXOM.N",
    "CVX": "usCVX.N",
    "COP": "usCOP.N",
}

HEALTHCARE_STOCKS = {
    "LLY": "usLLY.N",
    "JNJ": "usJNJ.N",
    "UNH": "usUNH.N",
    "PFE": "usPFE.N",
    "MRK": "usMRK.N",
}

CRYPTO_STOCKS = {
    "COIN": "usCOIN.OQ",
    "MARA": "usMARA.OQ",
    "RIOT": "usRIOT.OQ",
    "MSTR": "usMSTR.OQ",
}

def fetch_all_klines(codes_dict, name_prefix="", limit=20):
    """批量获取K线数据，带限流控制"""
    results = {}
    total = len(codes_dict)
    count = 0
    for name, code in codes_dict.items():
        count += 1
        print(f"[{count}/{total}] Fetching {name_prefix}{name} ({code})...")
        data = get_kline(code, limit=limit)
        if data and isinstance(data, list) and len(data) > 0:
            results[name] = data
        else:
            print(f"  -> No data or error")
        if count % 3 == 0:
            time.sleep(1)
    return results


# ============================================================
# Part 2.5: CBOE 期权链采集 (自选股 + 指数期权映射)
# ============================================================

# 自选股文件路径（工作区根目录）
# 2026-08-22 起：期权链默认仅采集核心标的（MAG7+AI科技巨头+股指ETF，26只），
# 全量144只采集耗时且分析冗余；如需全量，运行时传 --watchlist stock.list
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock.options.core.list")
WATCHLIST_FILE_FULL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stock.list")

# 指数期权映射：CBOE 不支持指数期权(SPX/IXIC/DJI)，映射到对应ETF
INDEX_OPTION_MAP = {
    "^SPX": "SPY",   # 标普500 -> SPY ETF
    "^IXIC": "QQQ",  # 纳指 -> QQQ ETF
    "^DJI": "DIA",   # 道指 -> DIA ETF
}

def load_watchlist(path=None):
    """读取自选股列表文件"""
    if path is None:
        path = WATCHLIST_FILE
    if not os.path.exists(path):
        print(f"⚠️ 自选股文件不存在: {path}")
        return []
    symbols = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            sym = line.strip().upper()
            if sym and not sym.startswith("#"):
                symbols.append(sym)
    return symbols

def parse_cboe_option_code(code):
    """解析 CBOE 期权代码: AAPL260819C00300000 -> (symbol, expiry, type, strike)"""
    # 从右往左: 8位行权价 + 1位C/P + 6位日期 + 标的
    if not code or len(code) < 15:
        return None
    strike_str = code[-8:]
    opt_type = code[-9]
    date_str = code[-15:-9]
    symbol = code[:-15]
    if opt_type not in ("C", "P"):
        return None
    try:
        strike = int(strike_str) / 1000.0
        exp_date = datetime.strptime(date_str, "%y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        return None
    return symbol, exp_date, "call" if opt_type == "C" else "put", strike

def fetch_cboe_options(symbol, max_age_days=365, max_retries=3):
    """获取单只标的的 CBOE 期权链，仅保留前后1年行权期（带重试机制）"""
    url = f"https://cdn.cboe.com/api/global/delayed_quotes/options/{symbol}.json"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
               "Accept": "application/json"}
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                d = data.get("data", {})
                opts = d.get("options", [])
                today = datetime.now().date()
                parsed = []
                for o in opts:
                    p = parse_cboe_option_code(o.get("option", ""))
                    if not p:
                        continue
                    _, exp_date, opt_type, strike = p
                    exp = datetime.strptime(exp_date, "%Y-%m-%d").date()
                    age_days = (exp - today).days
                    if age_days < -max_age_days or age_days > max_age_days:
                        continue
                    parsed.append({
                        "option_code": o.get("option"),
                        "symbol": symbol,
                        "expiration": exp_date,
                        "type": opt_type,
                        "strike": strike,
                        "bid": o.get("bid"),
                        "ask": o.get("ask"),
                        "last": o.get("last_trade_price"),
                        "change": o.get("change"),
                        "iv": o.get("iv"),
                        "open_interest": o.get("open_interest"),
                        "volume": o.get("volume"),
                        "delta": o.get("delta"),
                        "gamma": o.get("gamma"),
                        "vega": o.get("vega"),
                        "theta": o.get("theta"),
                        "theo": o.get("theo"),
                    })
                return {
                    "symbol": d.get("symbol", symbol),
                    "current_price": d.get("current_price"),
                    "options": parsed,
                }
            elif resp.status_code == 403:
                # 403 = 被限流/封禁，等待后重试
                wait = 5 * (attempt + 1)
                print(f"  ⚠️ {symbol} 被限流(403)，{wait}秒后重试 ({attempt+1}/{max_retries})...")
                time.sleep(wait)
            else:
                print(f"  ⚠️ {symbol} HTTP {resp.status_code}，重试 ({attempt+1}/{max_retries})...")
                time.sleep(3)
        except Exception as e:
            print(f"  ⚠️ 获取 {symbol} 期权链失败: {e}，重试 ({attempt+1}/{max_retries})...")
            time.sleep(3)
    return None

def calculate_option_sentiment(option_data):
    """计算期权情绪指标"""
    if not option_data or not option_data.get("options"):
        return None
    opts = option_data["options"]
    calls = [o for o in opts if o["type"] == "call"]
    puts = [o for o in opts if o["type"] == "put"]

    def safe_sum(items, key):
        return sum(x.get(key) or 0 for x in items)

    def weighted_iv(items):
        total_vol = safe_sum(items, "volume")
        if total_vol == 0:
            return None
        return sum((x.get("iv") or 0) * (x.get("volume") or 0) for x in items) / total_vol

    def max_oi_strike(items):
        if not items:
            return None
        return max(items, key=lambda x: x.get("open_interest") or 0).get("strike")

    call_oi = safe_sum(calls, "open_interest")
    put_oi = safe_sum(puts, "open_interest")
    call_vol = safe_sum(calls, "volume")
    put_vol = safe_sum(puts, "volume")
    call_wiv = weighted_iv(calls)
    put_wiv = weighted_iv(puts)

    return {
        "symbol": option_data["symbol"],
        "current_price": option_data.get("current_price"),
        "call_oi": call_oi,
        "put_oi": put_oi,
        "put_call_oi_ratio": round(put_oi / call_oi, 4) if call_oi else None,
        "call_volume": call_vol,
        "put_volume": put_vol,
        "put_call_volume_ratio": round(put_vol / call_vol, 4) if call_vol else None,
        "call_weighted_iv": round(call_wiv, 4) if call_wiv else None,
        "put_weighted_iv": round(put_wiv, 4) if put_wiv else None,
        "max_call_oi_strike": max_oi_strike(calls),
        "max_put_oi_strike": max_oi_strike(puts),
        "total_contracts": len(opts),
    }

def calculate_option_walls(option_data, r=0.04):
    """计算期权墙（Call Wall / Put Wall）和 Zero Gamma / Gamma 环境"""
    if not option_data or not option_data.get("options"):
        return None
    opts = option_data["options"]
    current_price = option_data.get("current_price")
    if not current_price or current_price <= 0:
        return None

    today = datetime.now().date()

    # 按行权价聚合：OI、volume、加权IV、平均到期时间
    calls_by_strike = {}
    puts_by_strike = {}

    for o in opts:
        strike = o.get("strike")
        if strike is None:
            continue
        oi = o.get("open_interest") or 0
        vol = o.get("volume") or 0
        iv = o.get("iv") or 0
        exp_str = o.get("expiration", "")
        try:
            exp = datetime.strptime(exp_str, "%Y-%m-%d").date()
            T = max((exp - today).days / 365.0, 0.001)
        except (ValueError, TypeError):
            T = 0.1

        target = calls_by_strike if o["type"] == "call" else puts_by_strike
        if strike not in target:
            target[strike] = {"oi": 0, "volume": 0, "iv_sum": 0, "iv_count": 0, "T_sum": 0, "T_count": 0}
        target[strike]["oi"] += oi
        target[strike]["volume"] += vol
        if iv and iv > 0:
            target[strike]["iv_sum"] += iv
            target[strike]["iv_count"] += 1
        target[strike]["T_sum"] += T
        target[strike]["T_count"] += 1

    # Call Wall / Put Wall（最大 OI 行权价）
    call_wall = max(calls_by_strike.items(), key=lambda x: x[1]["oi"])[0] if calls_by_strike else None
    put_wall = max(puts_by_strike.items(), key=lambda x: x[1]["oi"])[0] if puts_by_strike else None
    call_wall_oi = calls_by_strike.get(call_wall, {}).get("oi", 0) if call_wall else 0
    put_wall_oi = puts_by_strike.get(put_wall, {}).get("oi", 0) if put_wall else 0

    all_strikes = sorted(set(list(calls_by_strike.keys()) + list(puts_by_strike.keys())))
    if not all_strikes:
        return None

    def _bs_gamma(S, K, T, sigma):
        """Black-Scholes gamma"""
        if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
            return 0.0
        try:
            sqrt_t = math.sqrt(T)
            d1 = (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * sqrt_t)
            pdf = math.exp(-0.5 * d1 * d1) / math.sqrt(2 * math.pi)
            return pdf / (S * sigma * sqrt_t)
        except (ValueError, ZeroDivisionError):
            return 0.0

    def total_gamma_at(S):
        """市场总 gamma：call 贡献为正、put 贡献为负"""
        total = 0.0
        for K in all_strikes:
            c = calls_by_strike.get(K)
            p = puts_by_strike.get(K)
            if c and c["oi"] > 0:
                iv = c["iv_sum"] / c["iv_count"] if c["iv_count"] else 0.3
                T = c["T_sum"] / c["T_count"] if c["T_count"] else 0.1
                total += _bs_gamma(S, K, T, iv) * c["oi"] * 100
            if p and p["oi"] > 0:
                iv = p["iv_sum"] / p["iv_count"] if p["iv_count"] else 0.3
                T = p["T_sum"] / p["T_count"] if p["T_count"] else 0.1
                total -= _bs_gamma(S, K, T, iv) * p["oi"] * 100
        return total

    # 二分搜索 Zero Gamma
    lo = current_price * 0.5
    hi = current_price * 1.5
    g_lo = total_gamma_at(lo)
    g_hi = total_gamma_at(hi)
    for _ in range(10):
        if g_lo * g_hi <= 0:
            break
        lo *= 0.8
        hi *= 1.2
        g_lo = total_gamma_at(lo)
        g_hi = total_gamma_at(hi)

    zero_gamma = current_price
    if g_lo * g_hi <= 0:
        for _ in range(50):
            mid = (lo + hi) / 2
            g_mid = total_gamma_at(mid)
            if abs(g_mid) < 1e-6:
                zero_gamma = mid
                break
            if g_mid * g_lo <= 0:
                hi = mid
            else:
                lo = mid
                g_lo = g_mid
        zero_gamma = (lo + hi) / 2
    else:
        # 无零交叉，用 OI 加权平均行权价近似
        num = 0.0
        den = 0.0
        for K in all_strikes:
            net = calls_by_strike.get(K, {}).get("oi", 0) - puts_by_strike.get(K, {}).get("oi", 0)
            num += net * K
            den += abs(net)
        zero_gamma = num / den if den > 0 else current_price

    # Gamma 环境判断
    gamma_env = "Long Gamma" if current_price > zero_gamma else "Short Gamma"
    dist_pct = (current_price - zero_gamma) / current_price * 100

    return {
        "symbol": option_data["symbol"],
        "current_price": current_price,
        "call_wall": call_wall,
        "call_wall_oi": call_wall_oi,
        "put_wall": put_wall,
        "put_wall_oi": put_wall_oi,
        "zero_gamma": round(zero_gamma, 2),
        "gamma_env": gamma_env,
        "dist_to_zg_pct": round(dist_pct, 2),
    }

def fetch_options_data(watchlist_path=None, skip=False):
    """采集自选股期权链 + 期权情绪指标 + 期权墙"""
    if skip:
        print("\n⏭️  跳过期权链采集")
        return {'chains': {}, 'sentiment': [], 'walls': []}

    print("\n" + "="*60)
    print("📊 [CBOE] Step: 自选股期权链采集")
    print("="*60)

    symbols = load_watchlist(watchlist_path)
    if not symbols:
        print("⚠️ 自选股列表为空，跳过期权链采集")
        return {'chains': {}, 'sentiment': [], 'walls': []}

    # 指数映射为ETF并去重
    mapped = [INDEX_OPTION_MAP.get(sym, sym) for sym in symbols]
    unique_symbols = list(dict.fromkeys(mapped))

    print(f"自选股 {len(symbols)} 只 -> 去重后 {len(unique_symbols)} 只（指数已映射为ETF）")
    print(f"映射说明: ^SPX→SPY, ^IXIC→QQQ, ^DJI→DIA")

    chains = {}
    sentiment = []
    walls = []
    total = len(unique_symbols)
    for idx, sym in enumerate(unique_symbols):
        print(f"[{idx+1}/{total}] 获取 {sym} 期权链...")
        data = fetch_cboe_options(sym)
        if data and data.get("options"):
            chains[sym] = data
            senti = calculate_option_sentiment(data)
            if senti:
                sentiment.append(senti)
            wall = calculate_option_walls(data)
            if wall:
                walls.append(wall)
            print(f"  ✅ {sym}: {len(data['options'])} 条合约, 现价={data.get('current_price')}")
        else:
            print(f"  ⚠️ {sym}: 无期权数据或获取失败")
        # 限流控制：每只间隔0.8秒，每10只额外暂停3秒
        time.sleep(0.8)
        if (idx + 1) % 10 == 0:
            print(f"  ... 批量暂停3秒（限流控制）")
            time.sleep(3)

    print(f"\n期权链采集完成: {len(chains)} 只标的有数据, {len(sentiment)} 只计算了情绪指标, {len(walls)} 只计算了期权墙")
    return {'chains': chains, 'sentiment': sentiment, 'walls': walls}


# ============================================================
# Part 2.6: FRED 信用利差采集 (CDS 信用风险代理)
# ============================================================

# FRED API key（环境变量 FRED_API_KEY，免费注册: https://fred.stlouisfed.org/docs/api/api_key.html）
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")

# ICE BofA 信用利差系列（CDS 信用风险代理指标）
FRED_CREDIT_SERIES = {
    "BAMLC0A0CM": "投资级信用利差(IG OAS)",
    "BAMLH0A0HYM2": "高收益信用利差(HY OAS)",
    "BAMLC0A4CBBB": "BBB级信用利差(BBB OAS)",
    "BAMLCC0A0CM": "CCC级信用利差(CCC OAS)",
}

def fetch_fred_credit_spreads(api_key=None, lookback_days=30):
    """获取 FRED 信用利差数据（CDS 信用风险代理）"""
    if api_key is None:
        api_key = FRED_API_KEY
    if not api_key:
        print("\n⚠️ 未配置 FRED_API_KEY，跳过信用利差采集（免费注册: https://fred.stlouisfed.org/docs/api/api_key.html）")
        return None

    print("\n" + "="*60)
    print("📊 [FRED] Step: 信用利差采集 (CDS 信用风险代理)")
    print("="*60)

    results = {}
    for sid, name in FRED_CREDIT_SERIES.items():
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={sid}&api_key={api_key}&file_type=json&sort_order=desc&limit={lookback_days}"
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                obs = data.get("observations", [])
                rows = []
                for o in obs:
                    if o.get("value") != ".":
                        rows.append({"日期": o.get("date"), "利差": float(o.get("value"))})
                if rows:
                    rows.reverse()  # 升序
                    results[sid] = {"name": name, "rows": rows}
                    latest = rows[-1]
                    print(f"  ✅ {name}: 最新={latest['利差']}bp ({latest['日期']}), {len(rows)} 条")
                else:
                    print(f"  ⚠️ {name}: 无有效数据")
            else:
                print(f"  ⚠️ {name}: HTTP {resp.status_code}")
        except Exception as e:
            print(f"  ⚠️ {name}: Error {e}")
        time.sleep(0.5)

    print(f"\n信用利差采集完成: {len(results)} 个系列")
    return results


# ============================================================
# Part 3: 主流程
# ============================================================

def fetch_moomoo_data(headers):
    """获取Moomoo数据源：行业、概念、新闻"""
    result = {
        'industry': [],
        'concept': [],
        'day_news': [],
        'important_news': [],
    }

    # --- 行业板块 ---
    print("\n" + "="*60)
    print("📊 [Moomoo] Step 1: 行业板块热力图数据")
    print("="*60)
    try:
        heatmap_params = {
            "marketType": "2",
            "sortId": "119",
            "dataMaxCount": "50"
        }
        token = get_heatmap_token(heatmap_params)
        headers['quote-token'] = token
        heatmap_url = "https://www.moomoo.com/quote-api/quote-v2/get-heatmap-industry-data"
        response = requests.get(heatmap_url, params=heatmap_params, headers=headers, verify=False)
        response.raise_for_status()
        data = response.json()
        if data.get('code') == 0 and 'data' in data and 'result' in data['data']:
            industries = data['data']['result']
            print(f"找到 {len(industries)} 个行业板块")
            result['industry'] = fetch_stocks_for_plates(
                industries, headers,
                plate_id_key='stockId', type_name='Industry'
            )
        else:
            print("获取热力图数据失败")
    except Exception as e:
        print(f"行业板块获取错误: {e}")

    # --- 概念板块 ---
    print("\n" + "="*60)
    print("💡 [Moomoo] Step 2: 概念板块数据")
    print("="*60)
    try:
        concept_params = {
            "marketType": "2",
            "plateType": "2",
            "page": "0",
            "pageSize": "30",
            "lang": "zh-CN"
        }
        concept_token = get_plate_list_token(concept_params)
        concept_headers = headers.copy()
        concept_headers['quote-token'] = concept_token
        concept_headers['Referer'] = "https://www.moomoo.com/hans/quote/us/concepts"
        concept_url = "https://www.moomoo.com/quote-api/quote-v2/get-plate-list"
        response = requests.get(concept_url, params=concept_params, headers=concept_headers, verify=False)
        response.raise_for_status()
        data = response.json()
        if data.get('code') == 0 and 'data' in data and 'list' in data['data']:
            concepts = data['data']['list']
            df_concepts = pd.DataFrame(concepts)
            if not df_concepts.empty and 'changeRatio' in df_concepts.columns:
                df_concepts['changeRatio_num'] = df_concepts['changeRatio'].str.replace('%', '').str.replace('+', '').replace('--', '0').astype(float)
                top_concepts = df_concepts.nlargest(30, 'changeRatio_num')
                concepts_to_fetch = top_concepts.to_dict('records')
            else:
                concepts_to_fetch = concepts[:30]
            print(f"找到 Top {len(concepts_to_fetch)} 个概念板块")
            result['concept'] = fetch_stocks_for_plates(
                concepts_to_fetch, headers,
                plate_id_key='plateId', plate_name_key='plateName', type_name='Concept'
            )
        else:
            print("获取概念列表失败")
    except Exception as e:
        print(f"概念板块获取错误: {e}")

    # --- 24小时快讯 ---
    print("\n" + "="*60)
    print("📰 [Moomoo] Step 3: 24小时快讯")
    print("="*60)
    try:
        news_list = fetch_futu_news()
        for item in news_list:
            result['day_news'].append({
                "id": item.get("id"),
                "time_us_eastern": ts_to_us_eastern(item.get("time")),
                "title": item.get("title") or item.get("brief") or item.get("summary") or (item.get("content") or "").split("。")[0],
                "summary": item.get("summary") or item.get("brief") or (item.get("content") or "")[:120],
                "source": item.get("sourceName"),
                "url": item.get("detailUrl") or f"https://news.futunn.com/post/{item.get('id')}",
            })
        print(f"共获取 {len(result['day_news'])} 条快讯")
    except Exception as e:
        print(f"快讯获取错误: {e}")

    # --- 要闻 ---
    print("\n" + "="*60)
    print("🔴 [Moomoo] Step 4: 重要要闻")
    print("="*60)
    try:
        market_news = fetch_futu_market_news()
        for item in market_news:
            result['important_news'].append({
                "time_us_eastern": ts_to_us_eastern(item.get("timestamp")),
                "title": item.get("title"),
                "summary": item.get("summary") or item.get("brief") or (item.get("content") or "")[:120],
                "url": item.get("url")
            })
        print(f"共获取 {len(result['important_news'])} 条要闻")
    except Exception as e:
        print(f"要闻获取错误: {e}")

    return result


def fetch_westock_data(date_str):
    """获取WeStock数据源：指数、ETF、个股K线 + 宏观"""
    result = {
        'indices': {},
        'mag7': {},
        'etfs': {},
        'semiconductor': {},
        'ai_infra': {},
        'financial': {},
        'energy': {},
        'healthcare': {},
        'crypto': {},
        'macro': None,
    }

    # --- 指数 ---
    print("\n" + "="*60)
    print("📈 [WeStock] Step 1: 主要指数 K线")
    print("="*60)
    result['indices'] = fetch_all_klines(INDEX_CODES, "指数 ")
    time.sleep(2)

    # --- 七巨头 ---
    print("\n" + "="*60)
    print("🌟 [WeStock] Step 2: 七巨头 K线")
    print("="*60)
    result['mag7'] = fetch_all_klines(MAG7_CODES)
    time.sleep(2)

    # --- 行业ETF ---
    print("\n" + "="*60)
    print("📊 [WeStock] Step 3: 行业ETF K线")
    print("="*60)
    result['etfs'] = fetch_all_klines(ETF_CODES, "ETF ")
    time.sleep(2)

    # --- 半导体个股 ---
    print("\n" + "="*60)
    print("🔬 [WeStock] Step 4: 半导体重点个股")
    print("="*60)
    result['semiconductor'] = fetch_all_klines(SEMICONDUCTOR_STOCKS, "半导体 ")
    time.sleep(2)

    # --- AI基础设施 ---
    print("\n" + "="*60)
    print("🤖 [WeStock] Step 5: AI基础设施个股")
    print("="*60)
    result['ai_infra'] = fetch_all_klines(AI_INFRA_STOCKS, "AI ")
    time.sleep(2)

    # --- 金融股 ---
    print("\n" + "="*60)
    print("🏦 [WeStock] Step 6: 金融重点个股")
    print("="*60)
    result['financial'] = fetch_all_klines(FINANCIAL_STOCKS, "金融 ")
    time.sleep(1)

    # --- 能源股 ---
    print("\n" + "="*60)
    print("🛢️ [WeStock] Step 7: 能源重点个股")
    print("="*60)
    result['energy'] = fetch_all_klines(ENERGY_STOCKS, "能源 ")
    time.sleep(1)

    # --- 医疗股 ---
    print("\n" + "="*60)
    print("💊 [WeStock] Step 8: 医疗重点个股")
    print("="*60)
    result['healthcare'] = fetch_all_klines(HEALTHCARE_STOCKS, "医疗 ")
    time.sleep(1)

    # --- 加密货币相关 ---
    print("\n" + "="*60)
    print("₿ [WeStock] Step 9: 加密货币相关个股")
    print("="*60)
    result['crypto'] = fetch_all_klines(CRYPTO_STOCKS, "加密 ")
    time.sleep(1)

    # --- 宏观数据 ---
    print("\n" + "="*60)
    print("🌍 [WeStock] Step 10: 美国宏观数据")
    print("="*60)
    try:
        result['macro'] = get_macro_us(date_str)
        if result['macro']:
            print(f"获取宏观数据成功")
        else:
            print("宏观数据为空")
    except Exception as e:
        print(f"宏观数据获取错误: {e}")

    return result


def save_all_to_excel(moomoo_data, westock_data, output_file, options_data=None, fred_data=None):
    """将所有数据保存到单一Excel文件"""
    print("\n" + "="*60)
    print(f"💾 保存数据到: {output_file}")
    print("="*60)

    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:

        # ===== Moomoo 数据 =====
        if moomoo_data['industry']:
            df = pd.DataFrame(moomoo_data['industry'])
            df.to_excel(writer, sheet_name='行业_成份股', index=False)
            print(f"✅ 行业_成份股: {len(df)} 行")

        if moomoo_data['concept']:
            df = pd.DataFrame(moomoo_data['concept'])
            df.to_excel(writer, sheet_name='概念_成份股', index=False)
            print(f"✅ 概念_成份股: {len(df)} 行")

        if moomoo_data['day_news']:
            df = pd.DataFrame(moomoo_data['day_news'])
            df.to_excel(writer, sheet_name='Day_News_快讯', index=False)
            print(f"✅ Day_News_快讯: {len(df)} 行")

        if moomoo_data['important_news']:
            df = pd.DataFrame(moomoo_data['important_news'])
            df.to_excel(writer, sheet_name='Important_News_要闻', index=False)
            print(f"✅ Important_News_要闻: {len(df)} 行")

        # ===== WeStock K线数据 =====
        def save_klines(data_dict, sheet_name, name_col):
            """辅助函数：将K线数据保存为长表格式"""
            if not data_dict:
                return
            rows = []
            for name, klines in data_dict.items():
                for k in klines:
                    if isinstance(k, dict):
                        row = {name_col: name}
                        row.update(k)
                        rows.append(row)
            if rows:
                df = pd.DataFrame(rows)
                df.to_excel(writer, sheet_name=sheet_name, index=False)
                print(f"✅ {sheet_name}: {len(df)} 行")

        save_klines(westock_data.get('indices', {}), '指数_K线', '指数名称')
        save_klines(westock_data.get('mag7', {}), '七巨头_K线', '股票代码')
        save_klines(westock_data.get('etfs', {}), '行业ETF_K线', 'ETF名称')
        save_klines(westock_data.get('semiconductor', {}), '半导体个股_K线', '股票代码')
        save_klines(westock_data.get('ai_infra', {}), 'AI基础设施_K线', '股票代码')
        save_klines(westock_data.get('financial', {}), '金融个股_K线', '股票代码')
        save_klines(westock_data.get('energy', {}), '能源个股_K线', '股票代码')
        save_klines(westock_data.get('healthcare', {}), '医疗个股_K线', '股票代码')
        save_klines(westock_data.get('crypto', {}), '加密概念股_K线', '股票代码')

        # ===== 宏观数据 =====
        macro_data = westock_data.get('macro')
        if macro_data and isinstance(macro_data, list):
            rows = []
            for section in macro_data:
                if isinstance(section, list):
                    for item in section:
                        if isinstance(item, dict):
                            rows.append(item)
                elif isinstance(section, dict):
                    rows.append(section)
            if rows:
                df = pd.DataFrame(rows)
                df.to_excel(writer, sheet_name='宏观数据', index=False)
                print(f"✅ 宏观数据: {len(df)} 行")

        # ===== CBOE 期权链数据 =====
        if options_data:
            chains = options_data.get('chains', {})
            sentiment = options_data.get('sentiment', [])
            walls = options_data.get('walls', [])

            # 期权情绪指标
            if sentiment:
                df = pd.DataFrame(sentiment)
                df.to_excel(writer, sheet_name='期权情绪指标', index=False)
                print(f"✅ 期权情绪指标: {len(df)} 行")

            # 期权墙（Call Wall / Put Wall / Zero Gamma）
            if walls:
                df = pd.DataFrame(walls)
                df.to_excel(writer, sheet_name='期权墙_科技巨头', index=False)
                print(f"✅ 期权墙_科技巨头: {len(df)} 行")

            # 期权链明细（合并所有标的，仅保留1年行权期）
            if chains:
                all_rows = []
                for sym, data in chains.items():
                    for o in data.get('options', []):
                        row = {'标的': sym, '现价': data.get('current_price')}
                        row.update(o)
                        all_rows.append(row)
                if all_rows:
                    df = pd.DataFrame(all_rows)
                    df.to_excel(writer, sheet_name='期权链_自选股', index=False)
                    print(f"✅ 期权链_自选股: {len(df)} 行")

        # ===== FRED 信用利差数据 =====
        if fred_data:
            all_rows = []
            for sid, info in fred_data.items():
                for r in info["rows"]:
                    all_rows.append({"指标": info["name"], "系列": sid, "日期": r["日期"], "利差_bp": r["利差"]})
            if all_rows:
                df = pd.DataFrame(all_rows)
                df.to_excel(writer, sheet_name='信用利差_CDS代理', index=False)
                print(f"✅ 信用利差_CDS代理: {len(df)} 行")

        # 兜底：确保至少有一个可见Sheet
        if len(writer.book.sheetnames) == 0:
            pd.DataFrame({"提示": ["所有数据源均被跳过，无数据"]}).to_excel(writer, sheet_name='无数据', index=False)
            print("⚠️ 无任何数据写入，已创建占位Sheet")

    print(f"\n🎉 数据保存完成: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Sentinel_Daily_Pro - 美股每日数据采集增强版 (Moomoo + WeStock双数据源)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python Sentinel_Daily_Pro.py                      # 运行全部采集
  python Sentinel_Daily_Pro.py --date 2026-07-31   # 指定交易日期（用于宏观数据）
  python Sentinel_Daily_Pro.py -o my_output.xlsx       # 指定输出文件名
  python Sentinel_Daily_Pro.py --skip-moomoo         # 只跑WeStock数据
  python Sentinel_Daily_Pro.py --skip-westock    # 只跑Moomoo数据
        """
    )
    parser.add_argument('-o', '--output', type=str, help='输出Excel文件名 (默认: US_Market_Pro_YYYY-MM-DD.xlsx)')
    parser.add_argument('-d', '--date', type=str, help='交易日期 YYYY-MM-DD (默认: 今天)')
    parser.add_argument('--skip-moomoo', action='store_true', help='跳过Moomoo数据采集')
    parser.add_argument('--skip-westock', action='store_true', help='跳过WeStock数据采集')
    parser.add_argument('--skip-options', action='store_true', help='跳过CBOE期权链采集')
    parser.add_argument('--skip-fred', action='store_true', help='跳过FRED信用利差采集')
    parser.add_argument('--fred-key', type=str, help='FRED API key (默认读取环境变量 FRED_API_KEY)')
    parser.add_argument('--watchlist', type=str, help='期权链采集列表文件路径 (默认: stock.options.core.list，即MAG7+AI科技巨头+股指ETF；传stock.list恢复全量144只)')
    parser.add_argument('--output-dir', type=str, default='result', help='输出目录 (默认: result)')
    args = parser.parse_args()

    # 确定日期
    if args.date:
        target_date = args.date
    else:
        target_date = datetime.now().strftime("%Y-%m-%d")

    # 确定输出文件
    if args.output:
        excel_filename = args.output
        if not excel_filename.lower().endswith('.xlsx'):
            excel_filename += '.xlsx'
    else:
        excel_filename = f"US_Market_Pro_{target_date}.xlsx"

    output_dir = args.output_dir
    output_file = os.path.join(output_dir, excel_filename)

    # 绝对路径处理
    if not os.path.isabs(output_dir):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(script_dir, output_dir, excel_filename)

    print("\n" + "█"*60)
    print("█  Sentinel Daily Pro - 美股每日数据采集增强版")
    print("█  双数据源: Moomoo (行业/概念/新闻) + WeStock (K线/宏观)")
    print(f"█  目标日期: {target_date}")
    print(f"█  输出文件: {output_file}")
    print("█"*60)

    start_time = time.time()

    # Moomoo 通用 headers
    moomoo_headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "futu-x-csrf-token": "cd1zage106rT3rMaO8V7P4Cx",
        "Referer": "https://www.moomoo.com/quote/us",
        "Origin": "https://www.moomoo.com"
    }

    # 初始化数据容器
    moomoo_data = {'industry': [], 'concept': [], 'day_news': [], 'important_news': []}
    westock_data = {
        'indices': {}, 'mag7': {}, 'etfs': {},
        'semiconductor': {}, 'ai_infra': {},
        'financial': {}, 'energy': {},
        'healthcare': {}, 'crypto': {},
        'macro': None,
    }

    # Step 1: Moomoo 数据
    if not args.skip_moomoo:
        moomoo_data = fetch_moomoo_data(moomoo_headers)
    else:
        print("\n⏭️  跳过 Moomoo 数据采集")

    # Step 2: WeStock 数据
    if not args.skip_westock:
        westock_data = fetch_westock_data(target_date)
    else:
        print("\n⏭️  跳过 WeStock 数据采集")

    # Step 2.5: CBOE 期权链
    options_data = fetch_options_data(args.watchlist, skip=args.skip_options)

    # Step 2.6: FRED 信用利差 (CDS 代理)
    if not args.skip_fred:
        fred_data = fetch_fred_credit_spreads(api_key=args.fred_key)
    else:
        print("\n⏭️  跳过 FRED 信用利差采集")
        fred_data = None

    # Step 3: 保存到 Excel
    save_all_to_excel(moomoo_data, westock_data, output_file, options_data, fred_data)

    # 统计
    elapsed = time.time() - start_time
    print(f"\n⏱️  总耗时: {elapsed:.1f} 秒")
    print("\n✅ 全部采集完成！")


if __name__ == "__main__":
    main()
