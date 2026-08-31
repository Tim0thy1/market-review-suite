# 数据采集命令手册（自包含 · 不依赖外部 skill）

> 本文件整合了主线挖掘所需的全部数据采集命令，从 westock-data、westock-tool、neodata 三个数据通道提取。
> **硬规则**：所有行情/板块/资金数据必须从以下命令获取，禁止用 web_search / curl / 第三方 API 替代。

---

## 一、westock-data（结构化金融数据）

**调用方式**：`npx -y westock-data-skillhub@1.0.5 <命令> [参数]`
- nodejs ≥ 18，无需 npm install，需网络
- 多股对比时代码用逗号分隔写在同一条命令里

### 1.1 搜索（未知代码时先搜）

```bash
# 搜股票（默认）
npx -y westock-data-skillhub@1.0.5 search 宁德时代

# 搜板块
npx -y westock-data-skillhub@1.0.5 search 半导体 --type sector

# 搜指数
npx -y westock-data-skillhub@1.0.5 search 中证红利 --type index

# 搜ETF
npx -y westock-data-skillhub@1.0.5 search 沪深300 --type etf
```

> search 不支持批量，一次一个关键词。空结果最多换 1 种 --type 重试。

### 1.2 K线行情（指数/个股）

```bash
# 批量指数K线
npx -y westock-data-skillhub@1.0.5 kline sh000001,sz399001,sz399006,sh000688,sh000016,sh000300,sh000852,sh000905,sh000922 --period day --limit 5 --raw

# 个股K线
npx -y westock-data-skillhub@1.0.5 kline sh600519 --period day --limit 60

# 分时K线（盘中用）
npx -y westock-data-skillhub@1.0.5 kline sh510300 --period m5 --limit 30
```

### 1.3 市场总览

```bash
# 交易+轮动+估值画像
npx -y westock-data-skillhub@1.0.5 market-overview --type trade,rotation,valuation --raw

# 涨跌分布（涨停/跌停计数首选来源）
npx -y westock-data-skillhub@1.0.5 changedist --raw

# 两融余额
npx -y westock-data-skillhub@1.0.5 market-overview --type margin
```

### 1.4 板块排行

```bash
# 行业涨幅 + 概念涨幅 + 资金流入
npx -y westock-data-skillhub@1.0.5 sector ranking --raw

# 板块成份股
npx -y westock-data-skillhub@1.0.5 sector constituent pt01801080

# 板块估值
npx -y westock-data-skillhub@1.0.5 sector valuation pt01801080

# 板块财报聚合
npx -y westock-data-skillhub@1.0.5 sector finance pt01801780
```

### 1.5 资金流向

```bash
# 个股资金流向（支持批量）
npx -y westock-data-skillhub@1.0.5 fund flow sh600519,sz000651

# 板块资金流向
npx -y westock-data-skillhub@1.0.5 fund flow pt01801080

# 北向持股
npx -y westock-data-skillhub@1.0.5 fund north-holding sh600519
```

### 1.6 财务/技术指标

```bash
# 多股三大表
npx -y westock-data-skillhub@1.0.5 finance sh600519,sz000651 --num 4

# 技术指标
npx -y westock-data-skillhub@1.0.5 technical sh600519 --indicator macd
npx -y westock-data-skillhub@1.0.5 technical sh600519 --group macd,rsi
```

### 1.7 研报/公告

```bash
npx -y westock-data-skillhub@1.0.5 report list sh600519 --limit 5
npx -y westock-data-skillhub@1.0.5 notice list sh600519 --limit 10
```

### 1.8 宏观指标

```bash
npx -y westock-data-skillhub@1.0.5 macro indicator cn_core --date 2026-03-01
```

### 1.9 龙虎榜

```bash
npx -y westock-data-skillhub@1.0.5 lhb --type institution,hotmoney --raw
```

### 1.10 国家队护盘信号（宽基ETF + 券商银行）

```bash
# 宽基ETF行情
npx -y westock-data-skillhub@1.0.5 kline sh510300,sh510050,sh510500,sh512100,sh588000,sz159915 --period day --limit 10 --raw

# 宽基ETF资金流向
npx -y westock-data-skillhub@1.0.5 fund flow sh510300,sh510050,sh510500,sh512100,sh588000,sz159915

# 券商ETF + 银行ETF
npx -y westock-data-skillhub@1.0.5 kline sh512000,sh512800 --period day --limit 5 --raw
npx -y westock-data-skillhub@1.0.5 fund flow sh512000,sh512800
```

**护盘信号判定**：

| 信号 | 条件 | 强度 |
|------|------|------|
| 宽基ETF异常放量 | 成交额 > 近5日均值2倍 | 中 |
| 多只宽基ETF同步流入 | ≥3只同日主力净流入 | 强 |
| 沪深300+上证50双流入 | 510300和510050同日净流入 | 强 |
| 券商+银行双拉升 | 两板块涨幅>0.5%且资金净流入 | 强 |

≥2个「强」或≥3个「中」→ 判定「国家队护盘信号明显」。

---

## 二、westock-tool（排行/选股/筛股）

**调用方式**：`npx -y westock-tool <命令> [参数]`

### 2.1 涨停连板梯队

```bash
# 连板天梯
npx -y westock-tool ranking limitup_days --limit 50

# 涨停封单量排行
npx -y westock-tool ranking limitup_seal_volume --limit 30
```

### 2.2 跌停排行

```bash
npx -y westock-tool ranking limitdn_days --limit 20
npx -y westock-tool ranking limitdn_seal_amount --limit 20
```

### 2.3 资金排行

```bash
# 主力净流入排行
npx -y westock-tool ranking cap_main_net --limit 20 --raw

# 5日主力净流入
npx -y westock-tool ranking cap_main_5d --limit 20

# 两融余额变动
npx -y westock-tool ranking margin_chg_d
```

### 2.4 成交额/涨跌幅排行

```bash
# 成交额TOP
npx -y westock-tool ranking qt_daily --orderby Amount --limit 20 --raw

# 10日涨幅TOP（排除创业板/科创板/北交所后取主板前20）
npx -y westock-tool ranking qt_chg_interval --orderby ChgPct10D --limit 50 --raw
```

### 2.5 事件选股

```bash
# 近期龙虎榜股票池
npx -y westock-tool event longhu_statis_past_15

# 板块过去30日统计
npx -y westock-tool event block_past_30 --limit 30
```

---

## 三、neodata（自然语言金融数据搜索）

**调用方式**：`python3 scripts/query.py --query "<查询语句>"`
- scripts/query.py 位于 neodata-financial-search skill 目录下
- 首次若 TOKEN_EXPIRED / TOKEN_MISSING，按 neodata SKILL.md 凭证获取流程处理
- Python ≥ 3.7

### 3.1 主线挖掘常用查询

```bash
# 热点个股及题材归因
python3 scripts/query.py --query "A股 {日期} 今日涨停股票和热门个股有哪些，为什么上涨，有什么题材概念"

# 当日市场重大事件和驱动因素
python3 scripts/query.py --query "今日A股市场重大事件和驱动因素"

# 市场资金流向和北向资金最新情况
python3 scripts/query.py --query "A股市场资金流向和北向资金最新情况"

# 近期市场重大新闻事件和情绪分析
python3 scripts/query.py --query "近期市场重大新闻事件和情绪分析"
```

### 3.2 财经资讯聚合（5维度查询）

```bash
python3 scripts/query.py --query "港股今日要闻 {DATE}"
python3 scripts/query.py --query "国际财经新闻 {DATE}"
python3 scripts/query.py --query "中国财经新闻 {DATE}"
python3 scripts/query.py --query "金融市场大宗商品外汇新闻 {DATE}"
python3 scripts/query.py --query "今日财经快讯 财联社电报"
```

### 3.3 返回字段

从 `docData.docRecall[].docList[]` 提取：

| 字段 | 类型 | 含义 |
|------|------|------|
| `title` | str | 新闻标题 |
| `content` | str | 新闻正文/摘要 |
| `publishTime` | number | Unix时间戳（秒） |
| `source` | str | 文章来源 |
| `url` | str | 文章链接 |

---

## 四、数据采集原则

1. **涨停/跌停计数**始终优先使用 `changedist` 数据
2. **无依赖的多个查询**应在同一轮工具调用中并行发出
3. **批量查询**：凡支持批量的命令只调1次，代码用逗号分隔（search 例外，不支持批量）
4. **空结果处理**：如实标注「暂无数据」，不编造
5. **货币单位**：港股港元/美元、美股美元；A股人民币
6. **K线有延迟**：展示须标注数据日期，勿称「现价」「实时涨跌」
