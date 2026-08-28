# 财经资讯聚合管线（打包自 daily-financial-news）

> 主线挖掘需要信息冲刷时，使用本文件的5维度新闻聚合管线。
> 数据通道统一通过 neodata-financial-search 的自然语言查询获取。

---

## 一、日报生成流程（7阶段）

### 阶段1：拉取原始新闻（5维度查询）

```bash
python3 scripts/query.py --query "港股今日要闻 {DATE}"
python3 scripts/query.py --query "国际财经新闻 {DATE}"
python3 scripts/query.py --query "中国财经新闻 {DATE}"
python3 scripts/query.py --query "香港地产市场新闻 {DATE}"
python3 scripts/query.py --query "金融市场大宗商品外汇新闻 {DATE}"
```

> scripts/query.py 位于 neodata-financial-search skill 目录下。若 TOKEN_EXPIRED/TOKEN_MISSING，按凭证获取流程处理。

### 阶段2：逐条提取关键信息

每条新闻记录四项：
1. 完整标题
2. 发布时间（精确到分钟）
3. 原文链接URL
4. 内容摘要（来自content字段）

### 阶段3：时间过滤与去重

- **时间窗口**：只保留 {DATE} {TIME_START} 至 {TIME_END} HKT 的新闻
- **时区**：publishTime 为 Unix 时间戳（秒），统一转 HKT（GMT+8）后过滤
- **去重**：标题相似度 > 80% 且发布时间差 < 30 分钟 → 只保留来源更权威的

### 阶段4：访问原文获取完整内容

抓取时关注五要素：
- 核心事件（发生了什么）
- 关键数据（股价、指数、百分比、金额）
- 人物表态（关键人物原话）
- 事件背景（前因后果）
- 市场影响（对金融/行业/政策的潜在影响）

### 阶段5：主题聚类

常用分类（可灵活调整）：
1. 地缘政治/国际局势
2. 全球宏观/货币政策/经济数据
3. 大宗商品/金融市场
4. 企业动态
5. 中美科技与贸易博弈
6. 港股/亚太市场

规则：同主题按时间从早到晚排列，同一事件连续报道合并为一条。

### 阶段6：逐条深度摘要

每条200-400字，包含：
1. 核心事件概述
2. 具体数字数据
3. 关键人物表态
4. 事件背景与前因后果
5. 对金融市场/行业的影响分析
6. 末尾补「所以呢」：数据背后的含义或可观察信号

### 阶段7：生成HTML报告

按新闻模板写自包含HTML：
- 资讯阅读风：浅底、墨色标题区、时间线/标签
- 首屏「今日要点」3-6条 + 抓取/去重统计
- 按主题分节；每条含标题、时间、来源、链接、深度摘要、「所以呢」

---

## 二、快讯接入模式

```bash
python3 scripts/query.py --query "今日财经快讯 财联社电报"
python3 scripts/query.py --query "A股市场最新快讯"
python3 scripts/query.py --query "港股市场最新快讯"
python3 scripts/query.py --query "全球宏观最新快讯"
```

返回字段从 `docData.docRecall[].docList[]` 提取：title、content、publishTime、source、url。

归一化规则：
- 若 title 不在 content 中，前缀合并：`title｜content`
- publishTime（Unix时间戳）转 `%H:%M`
- 按时间倒序，最新优先

---

## 三、主线挖掘专用查询模板

### 信息五源冲刷查询

```bash
# ① 财经资讯 — 验证基本面引擎
python3 scripts/query.py --query "A股 融资 财报 业绩 最新"

# ② 龙头动态 — 验证点火持续
python3 scripts/query.py --query "A股 龙头 涨停 连板 今日"

# ③ 政策 — 政策点火源
python3 scripts/query.py --query "中国 产业政策 扶持文件 最新"

# ④ 前沿技术 — 传导是否扩散新环节
python3 scripts/query.py --query "AI 半导体 新能源 技术突破 最新"

# ⑤ 研报/外资 — 聪明钱方向
python3 scripts/query.py --query "券商研报 外资 北向资金 A股 最新"
```

---

## 四、质量标准

1. 五个维度的查询必须全部执行，不可遗漏
2. 深度摘要不是简单复述，需含数据、表态、背景分析和市场影响
3. 报告中不暴露具体数据源名称、抓取路径；统一用「综合消息面」「市场反馈」等中性表述
4. 若查询返回空，可改写query表述重试
