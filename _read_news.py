import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', 300)
f = r'd:\AI\trae work\stock\美股\result\US_Market_Pro_2026-08-19.xlsx'
df = pd.read_excel(f, sheet_name='Important_News_要闻')
print('=== 要闻 8/19（美东） ===')
for _, r in df.head(40).iterrows():
    print(f"[{r['time_us_eastern']}] {r['title']}")
