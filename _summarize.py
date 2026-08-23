import pandas as pd
import json

f = r'd:\AI\trae work\stock\美股\result\US_Market_Pro_2026-08-19.xlsx'
out = {}

# 指数
df = pd.read_excel(f, sheet_name='指数_K线')
idx_data = {}
for idx in df['指数名称'].unique():
    sub = df[df['指数名称'] == idx].sort_values('date')
    d19 = sub[sub['date'] == '2026-08-19'].iloc[0]
    d18 = sub[sub['date'] == '2026-08-18'].iloc[0]
    d13 = sub[sub['date'] == '2026-08-13'].iloc[0]
    pct1d = (d19['last'] / d18['last'] - 1) * 100
    pct5d = (d19['last'] / d13['last'] - 1) * 100
    idx_data[idx] = {
        'last': round(d19['last'], 2), 'pct1d': round(pct1d, 2), 'pct5d': round(pct5d, 2),
        'high': round(d19['high'], 2), 'low': round(d19['low'], 2), 'vol': int(d19['volume'])
    }
out['index'] = idx_data

# MAG7
df = pd.read_excel(f, sheet_name='七巨头_K线')
mag_data = {}
for code in df['股票代码'].unique():
    sub = df[df['股票代码'] == code].sort_values('date')
    d19 = sub[sub['date'] == '2026-08-19'].iloc[0]
    d18 = sub[sub['date'] == '2026-08-18'].iloc[0]
    pct = (d19['last'] / d18['last'] - 1) * 100
    mag_data[code] = {'last': round(d19['last'], 2), 'pct1d': round(pct, 2)}
out['mag7'] = mag_data

# 行业ETF
df = pd.read_excel(f, sheet_name='行业ETF_K线')
etf_data = {}
for etf in df['ETF名称'].unique():
    sub = df[df['ETF名称'] == etf].sort_values('date')
    d19 = sub[sub['date'] == '2026-08-19'].iloc[0]
    d18 = sub[sub['date'] == '2026-08-18'].iloc[0]
    pct = (d19['last'] / d18['last'] - 1) * 100
    etf_data[etf] = {'last': round(d19['last'], 2), 'pct1d': round(pct, 2)}
out['etf'] = etf_data

# 期权墙 MAG7
df = pd.read_excel(f, sheet_name='期权墙_科技巨头')
mags = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOG', 'GOOGL', 'META', 'TSLA']
walls = df[df['symbol'].isin(mags)][['symbol', 'current_price', 'call_wall', 'call_wall_oi', 'put_wall', 'put_wall_oi', 'zero_gamma', 'gamma_env', 'dist_to_zg_pct']]
out['walls_mag7'] = walls.to_dict('records')

# 期权情绪 MAG7
df = pd.read_excel(f, sheet_name='期权情绪指标')
sent = df[df['symbol'].isin(mags)][['symbol', 'current_price', 'call_oi', 'put_oi', 'put_call_oi_ratio', 'max_call_oi_strike', 'max_put_oi_strike']]
out['sentiment_mag7'] = sent.to_dict('records')

# Gamma 分布
df = pd.read_excel(f, sheet_name='期权墙_科技巨头')
out['gamma_dist'] = df['gamma_env'].value_counts().to_dict()

# 半导体个股
df = pd.read_excel(f, sheet_name='半导体个股_K线')
semi = {}
for code in df['股票代码'].unique():
    sub = df[df['股票代码'] == code].sort_values('date')
    d19 = sub[sub['date'] == '2026-08-19'].iloc[0]
    d18 = sub[sub['date'] == '2026-08-18'].iloc[0]
    pct = (d19['last'] / d18['last'] - 1) * 100
    semi[code] = {'last': round(d19['last'], 2), 'pct1d': round(pct, 2)}
out['semi'] = semi

# 加密概念股
df = pd.read_excel(f, sheet_name='加密概念股_K线')
crypto = {}
for code in df['股票代码'].unique():
    sub = df[df['股票代码'] == code].sort_values('date')
    d19 = sub[sub['date'] == '2026-08-19'].iloc[0]
    d18 = sub[sub['date'] == '2026-08-18'].iloc[0]
    pct = (d19['last'] / d18['last'] - 1) * 100
    crypto[code] = {'last': round(d19['last'], 2), 'pct1d': round(pct, 2)}
out['crypto'] = crypto

# 医疗个股
df = pd.read_excel(f, sheet_name='医疗个股_K线')
med = {}
for code in df['股票代码'].unique():
    sub = df[df['股票代码'] == code].sort_values('date')
    d19 = sub[sub['date'] == '2026-08-19'].iloc[0]
    d18 = sub[sub['date'] == '2026-08-18'].iloc[0]
    pct = (d19['last'] / d18['last'] - 1) * 100
    med[code] = {'last': round(d19['last'], 2), 'pct1d': round(pct, 2)}
out['med'] = med

# AI基础设施
df = pd.read_excel(f, sheet_name='AI基础设施_K线')
ai = {}
for code in df['股票代码'].unique():
    sub = df[df['股票代码'] == code].sort_values('date')
    d19 = sub[sub['date'] == '2026-08-19'].iloc[0]
    d18 = sub[sub['date'] == '2026-08-18'].iloc[0]
    pct = (d19['last'] / d18['last'] - 1) * 100
    ai[code] = {'last': round(d19['last'], 2), 'pct1d': round(pct, 2)}
out['ai'] = ai

# 金融/能源
for sheet, key in [('金融个股_K线', 'fin'), ('能源个股_K线', 'en')]:
    df = pd.read_excel(f, sheet_name=sheet)
    col = df.columns[0]
    d = {}
    for code in df[col].unique():
        sub = df[df[col] == code].sort_values('date')
        d19 = sub[sub['date'] == '2026-08-19'].iloc[0]
        d18 = sub[sub['date'] == '2026-08-18'].iloc[0]
        pct = (d19['last'] / d18['last'] - 1) * 100
        d[code] = {'last': round(d19['last'], 2), 'pct1d': round(pct, 2)}
    out[key] = d

with open(r'd:\AI\trae work\stock\美股\_report_data.json', 'w', encoding='utf-8') as fp:
    json.dump(out, fp, ensure_ascii=False, indent=2)
print('JSON saved')
print(json.dumps(out, ensure_ascii=False, indent=2))
