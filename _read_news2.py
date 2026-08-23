import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 300)
f = r'd:\AI\trae work\stock\美股\result\US_Market_Pro_2026-08-19.xlsx'
df = pd.read_excel(f, sheet_name='Day_News_快讯')
df['time'] = pd.to_datetime(df['time_us_eastern'].str.replace(' EDT', ''), errors='coerce')
d19 = df[(df['time'] >= '2026-08-19 09:30') & (df['time'] <= '2026-08-19 17:00')]
print(f'=== 8/19 09:30-17:00 快讯 {len(d19)} 条 ===')
for _, r in d19.head(55).iterrows():
    print(f"[{r['time_us_eastern']}] {r['title']}")
