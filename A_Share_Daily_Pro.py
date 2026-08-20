#!/usr/bin/env python3
"""
A_Share_Daily_Pro.py - A股每日数据采集增强版
数据源架构：
  - 财联社电报：实时资讯
  - 东方财富API：板块资金流、龙虎榜、北向资金
  - WeStock Data：指数/个股/宏观/涨停板/美股

用法：
  python A_Share_Daily_Pro.py                    # 默认运行全部
  python A_Share_Daily_Pro.py --date 2026-08-01  # 指定日期
  python A_Share_Daily_Pro.py -o output.xlsx     # 指定输出文件
  python A_Share_Daily_Pro.py --skip-cls         # 跳过财联社
  python A_Share_Daily_Pro.py --skip-eastmoney    # 跳过东方财富
  python A_Share_Daily_Pro.py --skip-westock      # 跳过WeStock
  python A_Share_Daily_Pro.py --quick             # 快速模式（只采集核心数据）
"""

import requests, urllib3, json, time, os, argparse, subprocess, re
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 全局SSL验证设置（开发环境代理可能拦截SSL）
REQUESTS_VERIFY = False
import pandas as pd
from datetime import datetime, timedelta, timezone

# ============================================================
# 全局配置
# ============================================================
DEFAULT_DATE = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d')
WORKSPACE = r'd:\AI\trae work\stock\美股'
TEMP_DIR = r'c:\Users\yongtian.zhao.KFLY\.trae-cn\work\6a6ded10b7f31fde2906ba9e'

# 个股池配置（核心个股 + 医药CRO/创新药）
STOCK_POOL = {
    'core': [
        'sh600519', 'sh600036', 'sh601318', 'sh600900', 'sh601012',
        'sz000858', 'sz002415', 'sz300750', 'sz000333', 'sz002594',
        'sh600887', 'sh601166', 'sh600585', 'sh600276', 'sh600309',
        'sh601398', 'sh601288', 'sh600030', 'sh601688', 'sh600196'
    ],
    'pharma': [
        'sh600276',  # 恒瑞医药
        'sz300760',  # 迈瑞医疗
        'sh603259',  # 药明康德
        'sh600196',  # 复星医药
        'sz002821',  # 凯莱英
        'sz300347',  # 泰格医药
        'sh688180',  # 君实生物
        'sh688185',  # 康希诺
        'sz300122',  # 智飞生物
        'sh600763',  # 通策医疗
        'sz000661',  # 长春高新
        'sh603392',  # 万泰生物
        'sz300529',  # 健帆生物
        'sh600085',  # 同仁堂
        'sz300015',  # 爱尔眼科
    ],
    'tech_ai': [
        'sh688981',  # 中芯国际
        'sz002049',  # 紫光国微
        'sh603986',  # 兆易创新
        'sz300782',  # 卓胜微
        'sh688012',  # 中微公司
        'sz300661',  # 圣邦股份
        'sh688008',  # 澜起科技
        'sz002230',  # 科大讯飞
        'sh603019',  # 中科曙光
        'sz300502',  # 新易盛
    ],
    'index_codes': {
        'sh000001': '上证指数',
        'sz399001': '深证成指',
        'sz399006': '创业板指',
        'sh000688': '科创50',
        'sh000016': '上证50',
        'sh000300': '沪深300',
        'sh000852': '中证1000',
        'sh000905': '中证500',
        'sh000922': '中证红利',
        'sh000300': '沪深300',
    }
}

# 全球AI链传导配置（动态调整）
AI_CHAIN = {
    'us_stocks': ['usNVDA.OQ', 'usAMD.OQ', 'usAVGO.OQ', 'usMSFT.OQ', 'usGOOGL.OQ'],
    'kr_stocks': ['KRX.005930', 'KRX.000660'],  # 三星电子, SK海力士
    'cn_chain': {
        'hbm': ['sh688981', 'sz002049'],
        '算力': ['sh603019', 'sz300502'],
        'ai应用': ['sz002230', 'sh688256'],
    }
}

# ============================================================
# Part 1: 财联社电报采集
# ============================================================

class CLSNewsCollector:
    """财联社电报采集器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://www.cls.cn/telegraph',
            'Origin': 'https://www.cls.cn',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        }
        self.base_url = 'https://www.cls.cn'
        self.api_url = 'https://www.cls.cn/api/cache'
    
    def _init_session(self):
        """初始化session，获取必要cookie"""
        try:
            self.session.get(f'{self.base_url}/telegraph', headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            return True
        except Exception as e:
            print(f'[财联社] Session初始化失败: {e}')
            return False
    
    def get_telegraph(self, last_time=None, limit=30):
        """
        获取财联社电报
        Args:
            last_time: Unix时间戳，获取该时间之后的数据（None=获取最新）
            limit: 返回条数上限
        Returns:
            list of dict: 电报列表
        """
        if last_time is None:
            last_time = int(time.time())
        
        params = {
            'lastTime': last_time,
            'name': 'refreshTenTelegraph'
        }
        
        try:
            r = self.session.get(self.api_url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            if r.status_code != 200:
                print(f'[财联社] API请求失败: HTTP {r.status_code}')
                return []
            
            data = r.json()
            if data.get('errno') != 0:
                print(f'[财联社] API返回错误: {data}')
                return []
            
            items = data.get('data', {}).get('l', {})
            if not items:
                return []
            
            result = []
            for k, v in items.items():
                result.append({
                    'id': v.get('id'),
                    'title': v.get('title', ''),
                    'content': v.get('content', ''),
                    'type': v.get('type'),
                    'ctime': v.get('ctime'),
                    'level': v.get('level', ''),
                    'subjects': [s['subject_name'] for s in v.get('subjects', [])],
                    'time': datetime.fromtimestamp(v.get('ctime', 0), 
                                                    tz=timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S') if v.get('ctime') else '',
                })
            
            # 按时间倒序排列
            result.sort(key=lambda x: x['ctime'] or 0, reverse=True)
            return result[:limit]
            
        except Exception as e:
            print(f'[财联社] 采集异常: {e}')
            return []
    
    def collect(self, date_str=None, limit=50):
        """
        对外采集接口
        Args:
            date_str: 日期字符串 YYYY-MM-DD，None=今天
            limit: 返回条数
        Returns:
            pd.DataFrame: 电报数据
        """
        print('[财联社] 开始采集电报...')
        if not self._init_session():
            return pd.DataFrame()
        
        # 获取目标日期的时间戳
        if date_str:
            target_dt = datetime.strptime(date_str, '%Y-%m-%d')
            target_start = int(target_dt.timestamp())
            target_end = int((target_dt + timedelta(days=1)).timestamp())
        else:
            target_start = 0
            target_end = int(time.time())
        
        # 分页采集，直到获取足够数据或没有更多数据
        all_items = []
        last_time = target_end
        
        while len(all_items) < limit:
            items = self.get_telegraph(last_time=last_time, limit=limit)
            if not items:
                break
            
            # 过滤目标日期范围内的数据
            for item in items:
                if item['ctime'] and item['ctime'] >= target_start and item['ctime'] <= target_end:
                    all_items.append(item)
            
            # 更新last_time为最旧条目的ctime
            oldest = min(items, key=lambda x: x['ctime'] or 0)
            new_last_time = oldest['ctime']
            
            if new_last_time == last_time or new_last_time <= target_start:
                break
            last_time = new_last_time - 1
            
            time.sleep(0.5)  # 避免请求过快
        
        if not all_items:
            print('[财联社] 未采集到数据')
            return pd.DataFrame()
        
        df = pd.DataFrame(all_items)
        # 按时间正序排列
        df = df.sort_values('ctime').reset_index(drop=True)
        print(f'[财联社] 采集完成，共 {len(df)} 条')
        return df


# ============================================================
# Part 2: 东方财富数据采集
# ============================================================

class EastMoneyCollector:
    """东方财富数据采集器（板块/资金/龙虎榜/北向/韩股）"""
    
    def __init__(self):
        self.session = requests.Session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://data.eastmoney.com/',
        }
    
    def get_sector_ranking(self):
        """获取行业板块涨跌幅排行"""
        print('[东方财富] 采集行业板块排行...')
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': 1, 'pz': 20, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'm:90+t:2',
            'fields': 'f2,f3,f4,f12,f14,f104,f105,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124'
        }
        try:
            r = self.session.get(url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            data = r.json()
            items = data.get('data', {}).get('diff', [])
            result = []
            for item in items:
                result.append({
                    '代码': item.get('f12'),
                    '名称': item.get('f14'),
                    '最新价': item.get('f2', 0),
                    '涨跌幅': item.get('f3', 0),
                    '涨跌额': item.get('f4', 0),
                    '成交额': item.get('f62', 0),
                    '主力净流入': item.get('f204', 0),
                    '主力净流入占比': item.get('f205', 0),
                })
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[东方财富] 行业板块排行采集失败: {e}')
            return pd.DataFrame()
    
    def get_concept_ranking(self):
        """获取概念板块涨跌幅排行"""
        print('[东方财富] 采集概念板块排行...')
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': 1, 'pz': 20, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'm:90+t:3',
            'fields': 'f2,f3,f4,f12,f14,f104,f105,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124'
        }
        try:
            r = self.session.get(url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            data = r.json()
            items = data.get('data', {}).get('diff', [])
            result = []
            for item in items:
                result.append({
                    '代码': item.get('f12'),
                    '名称': item.get('f14'),
                    '最新价': item.get('f2', 0),
                    '涨跌幅': item.get('f3', 0),
                    '涨跌额': item.get('f4', 0),
                    '成交额': item.get('f62', 0),
                    '主力净流入': item.get('f204', 0),
                    '主力净流入占比': item.get('f205', 0),
                })
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[东方财富] 概念板块排行采集失败: {e}')
            return pd.DataFrame()
    
    def get_sector_fund_flow(self, top_n=10):
        """获取行业板块资金流向TOP"""
        print('[东方财富] 采集板块资金流向...')
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': 1, 'pz': top_n, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f62',
            'fs': 'm:90+t:2',
            'fields': 'f12,f14,f3,f62,f204,f205,f184,f66,f69,f72,f75,f78,f81,f84,f87,f124'
        }
        try:
            r = self.session.get(url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            data = r.json()
            items = data.get('data', {}).get('diff', [])
            result = []
            for item in items:
                result.append({
                    '名称': item.get('f14'),
                    '涨跌幅': item.get('f3', 0),
                    '成交额': item.get('f62', 0),
                    '主力净流入': item.get('f204', 0),
                    '主力净流入占比': item.get('f205', 0),
                    '超大单净流入': item.get('f184', 0),
                    '大单净流入': item.get('f66', 0),
                    '中单净流入': item.get('f69', 0),
                    '小单净流入': item.get('f72', 0),
                })
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[东方财富] 板块资金流向采集失败: {e}')
            return pd.DataFrame()
    
    def get_limitup_data(self, top_n=30):
        """获取涨停板数据"""
        print('[东方财富] 采集涨停板数据...')
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': 1, 'pz': top_n, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f3',
            'fs': 'b:DLMK',  # 涨停板
            'fields': 'f2,f3,f4,f12,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f37,f38,f50,f62,f115,f128,f140,f141,f136,f152,f153'
        }
        try:
            r = self.session.get(url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            data = r.json()
            items = data.get('data', {}).get('diff', [])
            result = []
            for item in items:
                result.append({
                    '代码': item.get('f12'),
                    '名称': item.get('f14'),
                    '最新价': item.get('f2', 0),
                    '涨跌幅': item.get('f3', 0),
                    '涨跌额': item.get('f4', 0),
                    '成交额': item.get('f62', 0),
                    '换手率': item.get('f38', 0),
                    '封单金额': item.get('f136', 0),
                    '连板数': item.get('f153', 0),
                    '涨停原因': '',
                })
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[东方财富] 涨停板采集失败: {e}')
            return pd.DataFrame()
    
    def get_north_flow(self):
        """获取北向资金流向"""
        print('[东方财富] 采集北向资金流向...')
        try:
            # 北向资金实时数据
            url = 'https://push2.eastmoney.com/api/qt/kamt.kline/get'
            params = {
                'fields1': 'f1,f2,f3',
                'fields2': 'f51,f52,f53,f54,f55',
                'klt': 1,
                'lmt': 10,
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            }
            r = self.session.get(url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            data = r.json()
            d = data.get('data', {})
            result = []
            # 解析hk2sh（港股通沪）和hk2sz（港股通深）
            for key, label in [('hk2sh', '沪股通'), ('hk2sz', '深股通')]:
                items = d.get(key, [])
                for item in items if isinstance(items, list) else [items]:
                    parts = str(item).split(',')
                    if len(parts) >= 5:
                        result.append({
                            '时间': parts[0],
                            '方向': label,
                            '当日资金流入': float(parts[1]) if parts[1] else 0,
                            '当日成交净买额': float(parts[2]) if parts[2] else 0,
                            '当日余额': float(parts[3]) if parts[3] else 0,
                            '领涨股': parts[4] if len(parts) > 4 else '',
                        })
            # 汇总
            if result:
                return pd.DataFrame(result)
            return pd.DataFrame()
        except Exception as e:
            print(f'[东方财富] 北向资金采集失败: {e}')
            return pd.DataFrame()
    
    def get_margin_data(self, days=10):
        """获取融资融券数据（杠杆资金指标）"""
        print('[东方财富] 采集融资融券数据...')
        url = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
        params = {
            'reportName': 'RPTA_WEB_RZRQ',
            'columns': 'ALL',
            'source': 'WEB',
            'p': 1,
            'pageSize': days,
            'sortColumns': 'RZRQJYE',
            'sortTypes': '-1',
        }
        try:
            r = self.session.get(url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            data = r.json()
            rows = data.get('result', {}).get('data', [])
            if not rows:
                print('[东方财富] 融资融券数据为空，尝试备用接口...')
                # 备用接口：沪市+深市汇总
                return self._get_margin_fallback()
            result = []
            for item in rows:
                result.append({
                    '日期': item.get('RZRQJYE', ''),
                    '融资余额': round(item.get('RZYE', 0) / 1e8, 2) if item.get('RZYE') else 0,
                    '融券余额': round(item.get('RQYE', 0) / 1e8, 2) if item.get('RQYE') else 0,
                    '融资融券余额': round(item.get('RZRQJYE', 0) / 1e8, 2) if item.get('RZRQJYE') else 0,
                    '融资买入额': round(item.get('RZMRE', 0) / 1e8, 2) if item.get('RZMRE') else 0,
                    '融资偿还额': round(item.get('RZCHE', 0) / 1e8, 2) if item.get('RZCHE') else 0,
                    '融券卖出量': item.get('RQMCL', 0),
                    '融券偿还量': item.get('RQCHL', 0),
                    '融资净买入': round((item.get('RZMRE', 0) - item.get('RZCHE', 0)) / 1e8, 2),
                })
            df = pd.DataFrame(result)
            if not df.empty:
                # 计算杠杆倍数 = 融资融券余额 / 两市成交额
                df['杠杆倍数'] = df['融资融券余额']  # 简化：直接用余额作为杠杆规模参考
                print(f'[东方财富] 融资融券数据采集成功，{len(df)}条记录')
            return df
        except Exception as e:
            print(f'[东方财富] 融资融券采集失败: {e}')
            return self._get_margin_fallback()

    def _get_margin_fallback(self):
        """融资融券备用采集（沪市+深市分别采集）"""
        print('[东方财富] 使用备用接口采集融资融券...')
        result = []
        for market, mkt_name in [('sh', '沪市'), ('sz', '深市')]:
            try:
                url = f'https://datacenter-web.eastmoney.com/api/data/v1/get'
                params = {
                    'reportName': f'RPTA_WEB_RZRQ_{market.upper()}',
                    'columns': 'ALL',
                    'source': 'WEB',
                    'p': 1,
                    'pageSize': 5,
                    'sortColumns': 'RZRQJYE',
                    'sortTypes': '-1',
                }
                r = self.session.get(url, params=params, headers=self.headers, timeout=10, verify=REQUESTS_VERIFY)
                data = r.json()
                rows = data.get('result', {}).get('data', [])
                for item in rows:
                    result.append({
                        '日期': item.get('RZRQJYE', ''),
                        '市场': mkt_name,
                        '融资余额': round(item.get('RZYE', 0) / 1e8, 2) if item.get('RZYE') else 0,
                        '融券余额': round(item.get('RQYE', 0) / 1e8, 2) if item.get('RQYE') else 0,
                        '融资融券余额': round(item.get('RZRQJYE', 0) / 1e8, 2) if item.get('RZRQJYE') else 0,
                    })
            except Exception as e:
                print(f'[东方财富] {mkt_name}融资融券采集失败: {e}')
        if result:
            print(f'[东方财富] 备用融资融券采集成功，{len(result)}条记录')
        return pd.DataFrame(result)

    def get_individual_stock_flow(self, stock_codes, top_n=20):
        """获取个股资金流向排行"""
        print('[东方财富] 采集个股资金流向...')
        url = 'https://push2.eastmoney.com/api/qt/clist/get'
        params = {
            'pn': 1, 'pz': top_n, 'po': 1, 'np': 1,
            'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
            'fltt': 2, 'invt': 2, 'fid': 'f62',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048',
            'fields': 'f2,f3,f4,f12,f14,f62,f184,f66,f69,f72,f78,f204,f205,f152'
        }
        try:
            r = self.session.get(url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            data = r.json()
            items = data.get('data', {}).get('diff', [])
            result = []
            for item in items:
                result.append({
                    '代码': item.get('f12'),
                    '名称': item.get('f14'),
                    '涨跌幅': item.get('f3', 0),
                    '成交额': item.get('f62', 0),
                    '主力净流入': item.get('f204', 0),
                    '主力净流入占比': item.get('f205', 0),
                    '超大单净流入': item.get('f184', 0),
                    '大单净流入': item.get('f66', 0),
                    '中单净流入': item.get('f69', 0),
                    '小单净流入': item.get('f72', 0),
                })
            return pd.DataFrame(result[:top_n])
        except Exception as e:
            print(f'[东方财富] 个股资金流向采集失败: {e}')
            return pd.DataFrame()
    
    def get_korea_market(self):
        """获取韩股KOSPI指数行情（通过WeStock数据）"""
        print('[东方财富] 采集韩股KOSPI指数...')
        try:
            # 尝试通过WeStock API获取KOSPI数据
            url = 'https://push2.eastmoney.com/api/qt/stock/get'
            params = {
                'secid': '95.1001',  # KOSPI指数
                'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
                'fields': 'f43,f44,f45,f46,f47,f48,f50,f57,f58,f60,f116,f117,f170,f171,f169'
            }
            r = self.session.get(url, params=params, headers=self.headers, timeout=15, verify=REQUESTS_VERIFY)
            data = r.json()
            item = data.get('data')
            if not item:
                return pd.DataFrame()
            result = [{
                '名称': 'KOSPI指数',
                '最新价': item.get('f43', 0) / 100 if item.get('f43') else 0,
                '最高价': item.get('f44', 0) / 100 if item.get('f44') else 0,
                '最低价': item.get('f45', 0) / 100 if item.get('f45') else 0,
                '开盘价': item.get('f46', 0) / 100 if item.get('f46') else 0,
                '昨收价': item.get('f47', 0) / 100 if item.get('f47') else 0,
                '涨跌幅': item.get('f170', 0) / 100 if item.get('f170') else 0,
                '涨跌额': item.get('f169', 0) / 100 if item.get('f169') else 0,
                '成交额': item.get('f60', 0),
            }]
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[东方财富] 韩股KOSPI采集失败(将跳过): {e}')
            return pd.DataFrame()
    
    def collect(self, date_str=None):
        """对外采集接口，采集所有东方财富数据"""
        print('[东方财富] 开始采集...')
        result = {}
        
        result['sector_ranking'] = self.get_sector_ranking()
        result['concept_ranking'] = self.get_concept_ranking()
        result['sector_fund_flow'] = self.get_sector_fund_flow()
        result['limitup_data'] = self.get_limitup_data()
        result['north_flow'] = self.get_north_flow()
        result['margin_data'] = self.get_margin_data()
        result['stock_fund_flow'] = self.get_individual_stock_flow(None)
        result['korea_market'] = self.get_korea_market()
        
        print('[东方财富] 采集完成')
        return result


# ============================================================
# Part 3: WeStock Data 采集
# ============================================================

class WeStockCollector:
    """WeStock Data采集器（指数/个股/宏观/龙虎榜/涨停板/美股）"""
    
    def __init__(self):
        self.cli_base = 'npx -y westock-data-skillhub@1.0.5'
    
    def _run_command(self, cmd):
        """执行WeStock CLI命令"""
        full_cmd = f'{self.cli_base} {cmd}'
        try:
            r = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=60)
            output = r.stdout.strip()
            if r.returncode != 0:
                print(f'[WeStock] 命令执行失败: {cmd[:60]}...')
                print(f'[WeStock] 错误: {r.stderr[:200]}')
                return None
            return output
        except subprocess.TimeoutExpired:
            print(f'[WeStock] 命令超时: {cmd[:60]}...')
            return None
        except Exception as e:
            print(f'[WeStock] 命令异常: {e}')
            return None
    
    def get_index_quotes(self):
        """获取核心指数行情"""
        print('[WeStock] 采集指数行情...')
        codes = 'sh000001,sz399001,sz399006,sh000688,sh000016,sh000300,sh000852,sh000905,sh000922,bj899050'
        output = self._run_command(f'quote {codes} --raw')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            result = []
            for item in data if isinstance(data, list) else [data]:
                result.append({
                    '代码': item.get('code', ''),
                    '名称': item.get('name', ''),
                    '最新价': item.get('price', 0),
                    '涨跌幅': item.get('chgPct', 0),
                    '涨跌额': item.get('chg', 0),
                    '成交额': item.get('amount', 0),
                    '成交量': item.get('volume', 0),
                    '换手率': item.get('turnoverRate', 0),
                    '市盈率': item.get('pe', 0),
                })
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[WeStock] 指数行情解析失败: {e}')
            return pd.DataFrame()
    
    def get_stock_quotes(self, codes):
        """获取个股行情"""
        if not codes:
            return pd.DataFrame()
        codes_str = ','.join(codes)
        print(f'[WeStock] 采集个股行情 ({len(codes)}只)...')
        output = self._run_command(f'quote {codes_str} --raw')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            result = []
            for item in data if isinstance(data, list) else [data]:
                result.append({
                    '代码': item.get('code', ''),
                    '名称': item.get('name', ''),
                    '最新价': item.get('price', 0),
                    '涨跌幅': item.get('chgPct', 0),
                    '涨跌额': item.get('chg', 0),
                    '成交额': item.get('amount', 0),
                    '成交量': item.get('volume', 0),
                    '换手率': item.get('turnoverRate', 0),
                    '市盈率': item.get('pe', 0),
                    '总市值': item.get('totalMarketCap', 0),
                })
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[WeStock] 个股行情解析失败: {e}')
            return pd.DataFrame()
    
    def get_market_overview(self):
        """获取市场总览"""
        print('[WeStock] 采集市场总览...')
        output = self._run_command('market-overview --raw')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                return pd.DataFrame([data])
            return pd.DataFrame(data)
        except Exception as e:
            print(f'[WeStock] 市场总览解析失败: {e}')
            return pd.DataFrame()
    
    def get_changedist(self):
        """获取涨跌分布"""
        print('[WeStock] 采集涨跌分布...')
        output = self._run_command('changedist --raw')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                return pd.DataFrame([data])
            return pd.DataFrame(data)
        except Exception as e:
            print(f'[WeStock] 涨跌分布解析失败: {e}')
            return pd.DataFrame()
    
    def get_sector_ranking(self):
        """获取板块排行"""
        print('[WeStock] 采集板块排行...')
        output = self._run_command('sector ranking --raw')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            result = []
            if isinstance(data, dict) and 'data' in data:
                result.append(pd.DataFrame([data]))
            else:
                for item in data if isinstance(data, list) else [data]:
                    result.append(pd.DataFrame([item]) if isinstance(item, dict) else pd.DataFrame())
            if result:
                return pd.concat(result, ignore_index=True) if len(result) > 1 else result[0]
            return pd.DataFrame()
        except Exception as e:
            print(f'[WeStock] 板块排行解析失败: {e}')
            return pd.DataFrame()
    
    def get_lhb_data(self):
        """获取龙虎榜数据"""
        print('[WeStock] 采集龙虎榜...')
        output = self._run_command('lhb --type institution,hotmoney --raw')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                return pd.DataFrame([data])
            return pd.DataFrame(data)
        except Exception as e:
            print(f'[WeStock] 龙虎榜解析失败: {e}')
            return pd.DataFrame()
    
    def get_macro_indicators(self):
        """获取宏观指标"""
        print('[WeStock] 采集宏观指标...')
        output = self._run_command('macro indicator core_indicators_cur')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                return pd.DataFrame([data])
            return pd.DataFrame(data)
        except Exception as e:
            print(f'[WeStock] 宏观指标解析失败: {e}')
            return pd.DataFrame()
    
    def get_us_stock_quotes(self):
        """获取美股主要指数"""
        print('[WeStock] 采集美股指数...')
        codes = 'us.IXIC,us.INX,us.DJI'
        output = self._run_command(f'quote {codes} --raw')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            result = []
            for item in data if isinstance(data, list) else [data]:
                result.append({
                    '代码': item.get('code', ''),
                    '名称': item.get('name', ''),
                    '最新价': item.get('price', 0),
                    '涨跌幅': item.get('chgPct', 0),
                    '涨跌额': item.get('chg', 0),
                    '成交额': item.get('amount', 0),
                })
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[WeStock] 美股指数解析失败: {e}')
            return pd.DataFrame()
    
    def get_us_ai_stocks(self):
        """获取美股AI核心个股行情"""
        print('[WeStock] 采集美股AI个股...')
        codes = 'usNVDA.OQ,usAMD.OQ,usAVGO.OQ,usMSFT.OQ,usGOOGL.OQ'
        output = self._run_command(f'quote {codes} --raw')
        if not output:
            return pd.DataFrame()
        try:
            data = json.loads(output)
            result = []
            for item in data if isinstance(data, list) else [data]:
                result.append({
                    '代码': item.get('code', ''),
                    '名称': item.get('name', ''),
                    '最新价': item.get('price', 0),
                    '涨跌幅': item.get('chgPct', 0),
                    '涨跌额': item.get('chg', 0),
                    '成交额': item.get('amount', 0),
                    '总市值': item.get('totalMarketCap', 0),
                })
            return pd.DataFrame(result)
        except Exception as e:
            print(f'[WeStock] 美股AI个股解析失败: {e}')
            return pd.DataFrame()
    
    def collect(self, date_str=None):
        """对外采集接口"""
        print('[WeStock] 开始采集...')
        result = {}
        
        result['index_quotes'] = self.get_index_quotes()
        result['market_overview'] = self.get_market_overview()
        result['changedist'] = self.get_changedist()
        result['sector_ranking'] = self.get_sector_ranking()
        result['lhb_data'] = self.get_lhb_data()
        result['macro_indicators'] = self.get_macro_indicators()
        result['us_index'] = self.get_us_stock_quotes()
        result['us_ai_stocks'] = self.get_us_ai_stocks()
        
        # 采集核心个股行情
        all_stocks = STOCK_POOL['core'] + STOCK_POOL['pharma'] + STOCK_POOL['tech_ai']
        result['stock_quotes'] = self.get_stock_quotes(all_stocks)
        
        print('[WeStock] 采集完成')
        return result


# ============================================================
# Part 4: 跨市场联动分析
# ============================================================

class CrossMarketAnalyzer:
    """跨市场联动分析器（美股+韩股→A股传导）"""
    
    def __init__(self):
        self.cli_base = 'npx -y westock-data-skillhub@1.0.5'
    
    def _run_command(self, cmd):
        """执行WeStock CLI命令"""
        full_cmd = f'{self.cli_base} {cmd}'
        try:
            r = subprocess.run(full_cmd, shell=True, capture_output=True, text=True, timeout=60)
            if r.returncode != 0:
                return None
            return r.stdout.strip()
        except Exception as e:
            return None
    
    def analyze(self, date_str=None):
        """
        跨市场联动分析
        返回: dict with 'us_market', 'ai_chain', 'summary'
        """
        print('[跨市场] 开始跨市场联动分析...')
        result = {}
        
        # 1. 美股市场数据
        print('[跨市场] 采集美股市场数据...')
        us_codes = 'us.IXIC,us.INX,us.DJI'
        us_output = self._run_command(f'quote {us_codes} --raw')
        if us_output:
            try:
                data = json.loads(us_output)
                us_rows = []
                for item in data if isinstance(data, list) else [data]:
                    us_rows.append({
                        '代码': item.get('code', ''),
                        '名称': item.get('name', ''),
                        '最新价': item.get('price', 0),
                        '涨跌幅': item.get('chgPct', 0),
                    })
                result['us_market'] = pd.DataFrame(us_rows) if us_rows else pd.DataFrame()
            except Exception:
                result['us_market'] = pd.DataFrame()
        
        # 2. AI产业链核心个股
        print('[跨市场] 采集AI产业链数据...')
        ai_us_codes = 'usNVDA.OQ,usAMD.OQ,usAVGO.OQ,usMSFT.OQ,usGOOGL.OQ'
        ai_output = self._run_command(f'quote {ai_us_codes} --raw')
        if ai_output:
            try:
                data = json.loads(ai_output)
                ai_rows = []
                for item in data if isinstance(data, list) else [data]:
                    ai_rows.append({
                        '代码': item.get('code', ''),
                        '名称': item.get('name', ''),
                        '最新价': item.get('price', 0),
                        '涨跌幅': item.get('chgPct', 0),
                        '总市值': item.get('totalMarketCap', 0),
                    })
                result['ai_chain'] = pd.DataFrame(ai_rows) if ai_rows else pd.DataFrame()
            except Exception:
                result['ai_chain'] = pd.DataFrame()
        
        # 3. 韩股数据（通过东方财富已有数据）
        # 在Part 2中已采集KOSPI，这里留空由外部填充
        
        # 4. 联动分析摘要
        summary_rows = [{
            '分析维度': '美股→A股传导',
            '说明': '美股科技股涨跌通过A股科技AI链传导',
            '传导路径': '美股NVDA/AMD→韩股三星/SK海力士→A股HBM/算力/光模块',
            '关注重点': 'NVDA/AMD盘后涨跌幅、A股半导体/光模块次日开盘',
            '时间差': '美股收盘在A股次日开盘前，韩股在A股开盘前交易',
        }]
        result['summary'] = pd.DataFrame(summary_rows)
        
        print('[跨市场] 跨市场联动分析完成')
        return result


# ============================================================
# Part 5: 数据汇总、Excel保存与主函数
# ============================================================

class DataExporter:
    """数据汇总与Excel导出"""
    
    def __init__(self, output_path=None):
        self.output_path = output_path
        self.sheet_names = {
            'cls_news': '财联社电报',
            'index_quotes': '指数行情',
            'sector_ranking': '行业板块排行',
            'concept_ranking': '概念板块排行',
            'limitup_data': '涨停板数据',
            'lhb_data': '龙虎榜',
            'north_flow': '北向资金',
            'stock_fund_flow': '主力资金流向',
            'macro_indicators': '宏观指标',
            'core_stocks': '核心个股行情',
            'pharma_stocks': '医药个股',
            'us_index': '美股指数',
            'us_ai_stocks': '美股AI个股',
            'korea_market': '韩股数据',
            'cross_market_us': '跨市场美股',
            'cross_market_ai': 'AI产业链',
            'cross_market_summary': '跨市场联动摘要',
            'market_overview': '市场总览',
            'changedist': '涨跌分布',
            'config': '配置参数',
        }
    
    def _safe_df(self, data_or_dict, key):
        """安全地从dict中提取DataFrame"""
        if isinstance(data_or_dict, dict):
            df = data_or_dict.get(key, pd.DataFrame())
        else:
            df = data_or_dict
        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            return pd.DataFrame({'提示': [f'{key} 数据未采集到']})
        return df
    
    def export_excel(self, all_data, output_path=None):
        """将所有数据导出到Excel文件"""
        path = output_path or self.output_path
        if not path:
            date_str = DEFAULT_DATE
            path = os.path.join(WORKSPACE, f'A_Share_Market_Data_{date_str}.xlsx')
        
        print(f'[导出] 正在写入Excel: {path}')
        
        # 确保目录存在
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        
        # 打开Excel写入器
        with pd.ExcelWriter(path, engine='openpyxl') as writer:
            # 1. 财联社电报
            sheet1 = self._safe_df(all_data.get('cls_news', {}), 'cls_news') if isinstance(all_data.get('cls_news'), dict) else self._safe_df({'cls_news': all_data.get('cls_news')}, 'cls_news')
            sheet1.to_excel(writer, sheet_name='财联社电报', index=False)
            self._auto_width(writer, '财联社电报', sheet1)
            
            # 2. 指数行情
            sheet2 = self._safe_df(all_data.get('westock', {}), 'index_quotes')
            sheet2.to_excel(writer, sheet_name='指数行情', index=False)
            self._auto_width(writer, '指数行情', sheet2)
            
            # 3. 行业板块排行
            em_data = all_data.get('eastmoney', {})
            sheet3 = self._safe_df(em_data, 'sector_ranking')
            sheet3.to_excel(writer, sheet_name='行业板块排行', index=False)
            self._auto_width(writer, '行业板块排行', sheet3)
            
            # 4. 概念板块排行
            sheet4 = self._safe_df(em_data, 'concept_ranking')
            sheet4.to_excel(writer, sheet_name='概念板块排行', index=False)
            self._auto_width(writer, '概念板块排行', sheet4)
            
            # 5. 涨停板数据
            sheet5 = self._safe_df(em_data, 'limitup_data')
            sheet5.to_excel(writer, sheet_name='涨停板数据', index=False)
            self._auto_width(writer, '涨停板数据', sheet5)
            
            # 6. 龙虎榜
            ws_data = all_data.get('westock', {})
            sheet6 = self._safe_df(ws_data, 'lhb_data')
            sheet6.to_excel(writer, sheet_name='龙虎榜', index=False)
            self._auto_width(writer, '龙虎榜', sheet6)
            
            # 7. 北向资金
            sheet7 = self._safe_df(em_data, 'north_flow')
            sheet7.to_excel(writer, sheet_name='北向资金', index=False)
            self._auto_width(writer, '北向资金', sheet7)
            
            # 7.5 融资融券数据（杠杆资金指标）
            sheet_margin = self._safe_df(em_data, 'margin_data')
            sheet_margin.to_excel(writer, sheet_name='融资融券', index=False)
            self._auto_width(writer, '融资融券', sheet_margin)
            
            # 8. 主力资金流向
            sheet8 = self._safe_df(em_data, 'stock_fund_flow')
            sheet8.to_excel(writer, sheet_name='主力资金流向', index=False)
            self._auto_width(writer, '主力资金流向', sheet8)
            
            # 9. 宏观指标
            sheet9 = self._safe_df(ws_data, 'macro_indicators')
            sheet9.to_excel(writer, sheet_name='宏观指标', index=False)
            self._auto_width(writer, '宏观指标', sheet9)
            
            # 10. 核心个股行情
            sheet10 = self._safe_df(ws_data, 'stock_quotes')
            # 只保留核心个股（非医药和非AI）
            if not sheet10.empty and '代码' in sheet10.columns:
                core_codes = STOCK_POOL['core']
                sheet10 = sheet10[sheet10['代码'].isin(core_codes)].reset_index(drop=True)
            sheet10.to_excel(writer, sheet_name='核心个股行情', index=False)
            self._auto_width(writer, '核心个股行情', sheet10)
            
            # 11. 医药个股
            sheet11 = self._safe_df(ws_data, 'stock_quotes')
            if not sheet11.empty and '代码' in sheet11.columns:
                pharma_codes = STOCK_POOL['pharma']
                sheet11 = sheet11[sheet11['代码'].isin(pharma_codes)].reset_index(drop=True)
            sheet11.to_excel(writer, sheet_name='医药个股', index=False)
            self._auto_width(writer, '医药个股', sheet11)
            
            # 12. 美股指数
            sheet12 = self._safe_df(ws_data, 'us_index')
            sheet12.to_excel(writer, sheet_name='美股指数', index=False)
            self._auto_width(writer, '美股指数', sheet12)
            
            # 13. 美股AI个股
            sheet13 = self._safe_df(ws_data, 'us_ai_stocks')
            sheet13.to_excel(writer, sheet_name='美股AI个股', index=False)
            self._auto_width(writer, '美股AI个股', sheet13)
            
            # 14. 韩股数据
            sheet14 = self._safe_df(em_data, 'korea_market')
            sheet14.to_excel(writer, sheet_name='韩股数据', index=False)
            self._auto_width(writer, '韩股数据', sheet14)
            
            # 15. 跨市场美股
            cm_data = all_data.get('cross_market', {})
            sheet15 = self._safe_df(cm_data, 'us_market')
            sheet15.to_excel(writer, sheet_name='跨市场美股', index=False)
            self._auto_width(writer, '跨市场美股', sheet15)
            
            # 16. AI产业链
            sheet16 = self._safe_df(cm_data, 'ai_chain')
            sheet16.to_excel(writer, sheet_name='AI产业链', index=False)
            self._auto_width(writer, 'AI产业链', sheet16)
            
            # 17. 跨市场联动摘要
            sheet17 = self._safe_df(cm_data, 'summary')
            sheet17.to_excel(writer, sheet_name='跨市场联动摘要', index=False)
            self._auto_width(writer, '跨市场联动摘要', sheet17)
            
            # 18. 市场总览
            sheet18 = self._safe_df(ws_data, 'market_overview')
            if not sheet18.empty:
                sheet18.to_excel(writer, sheet_name='市场总览', index=False)
                self._auto_width(writer, '市场总览', sheet18)
            
            # 19. 涨跌分布
            sheet19 = self._safe_df(ws_data, 'changedist')
            if not sheet19.empty:
                sheet19.to_excel(writer, sheet_name='涨跌分布', index=False)
                self._auto_width(writer, '涨跌分布', sheet19)
            
            # 20. 配置参数
            config_data = pd.DataFrame([
                {'参数': '采集日期', '值': DEFAULT_DATE},
                {'参数': '核心个股数', '值': len(STOCK_POOL['core'])},
                {'参数': '医药个股数', '值': len(STOCK_POOL['pharma'])},
                {'参数': '科技AI个股数', '值': len(STOCK_POOL['tech_ai'])},
                {'参数': '美股AI链', '值': ','.join(AI_CHAIN['us_stocks'])},
                {'参数': '韩股AI链', '值': ','.join(AI_CHAIN['kr_stocks'])},
                {'参数': '数据源', '值': '财联社 + 东方财富 + WeStock Data'},
            ])
            config_data.to_excel(writer, sheet_name='配置参数', index=False)
            self._auto_width(writer, '配置参数', config_data)
        
        print(f'[导出] Excel写入完成: {path}')
        print(f'[导出] 共 {len(self.sheet_names)} 个Sheet')
        return path
    
    def _auto_width(self, writer, sheet_name, df):
        """自动调整列宽"""
        try:
            worksheet = writer.sheets[sheet_name]
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(str(col))) + 2
                max_len = min(max_len, 50)  # 限制最大宽度
                worksheet.column_dimensions[chr(65 + idx) if idx < 26 else 'A' + chr(65 + idx - 26)].width = max_len
        except Exception:
            pass


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='A股每日数据采集工具')
    parser.add_argument('--date', type=str, default=DEFAULT_DATE,
                       help=f'交易日期 (YYYY-MM-DD)，默认 {DEFAULT_DATE}')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='输出Excel文件路径')
    parser.add_argument('--skip-cls', action='store_true',
                       help='跳过财联社电报采集')
    parser.add_argument('--skip-eastmoney', action='store_true',
                       help='跳过东方财富数据采集')
    parser.add_argument('--skip-westock', action='store_true',
                       help='跳过WeStock数据采集')
    parser.add_argument('--skip-cross-market', action='store_true',
                       help='跳过跨市场联动分析')
    parser.add_argument('--quick', action='store_true',
                       help='快速模式（只采集核心数据）')
    return parser.parse_args()


def main():
    """主函数"""
    args = parse_args()
    date_str = args.date
    output_path = args.output
    
    print('=' * 60)
    print(f'  A股每日数据采集 - {date_str}')
    print('=' * 60)
    print()
    
    all_data = {}
    
    # 1. 财联社电报
    if not args.skip_cls:
        print('[主流程] 步骤1/5: 采集财联社电报...')
        cls = CLSNewsCollector()
        all_data['cls_news'] = cls.collect(date_str=date_str)
        print()
    
    # 2. 东方财富数据
    if not args.skip_eastmoney:
        print('[主流程] 步骤2/5: 采集东方财富数据...')
        em = EastMoneyCollector()
        all_data['eastmoney'] = em.collect(date_str=date_str)
        print()
    
    # 3. WeStock数据
    if not args.skip_westock:
        print('[主流程] 步骤3/5: 采集WeStock Data...')
        ws = WeStockCollector()
        all_data['westock'] = ws.collect(date_str=date_str)
        print()
    
    # 4. 跨市场联动
    if not args.skip_cross_market:
        print('[主流程] 步骤4/5: 跨市场联动分析...')
        cm = CrossMarketAnalyzer()
        all_data['cross_market'] = cm.analyze(date_str=date_str)
        print()
    
    # 5. 导出Excel
    print('[主流程] 步骤5/5: 导出Excel...')
    exporter = DataExporter()
    saved_path = exporter.export_excel(all_data, output_path=output_path)
    
    print()
    print('=' * 60)
    print(f'  采集完成!')
    print(f'  输出文件: {saved_path}')
    print('=' * 60)
    
    return saved_path


if __name__ == '__main__':
    main()