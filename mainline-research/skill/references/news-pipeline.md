# 财经资讯聚合管线（打包自 daily-financial-news）

> 主线挖掘需要信息冲刷时，使用本文件的5维度新闻聚合管线。

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

### 阶段2：逐条提取关键信息
每条新闻记：标题、发布时间、原文链接、内容摘要。

### 阶段3：时间过滤与去重
- 只保留 {DATE} 00:00 至 20:00 HKT 的新闻
- 标题相似度>80%且时间差<30分钟 → 去重

### 阶段4：访问原文获取完整内容
关注五要素：核心事件、关键数据、人物表态、事件背景、市场影响。

### 阶段5：主题聚类
常用分类：地缘政治/全球宏观/大宗商品/企业动态/中美博弈/亚太市场。

### 阶段6：逐条深度摘要
每条200-400字，含核心事件、数据、表态、背景、市场影响，末尾补「所以呢」。

### 阶段7：生成HTML报告
资讯阅读风，首屏「今日要点」3-6条，按主题分节。

---

## 二、快讯接入模式

```bash
python3 scripts/query.py --query "今日财经快讯 财联社电报"
python3 scripts/query.py --query "A股市场最新快讯"
python3 scripts/query.py --query "港股市场最新快讯"
python3 scripts/query.py --query "全球宏观最新快讯"
```

---

## 三、主线挖掘专用查询模板（信息五源冲刷）

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

1. 五个维度查询不可遗漏
2. 深度摘要含数据、表态、背景、市场影响
3. 报告中统一用「综合消息面」「市场反馈」等中性表述，不暴露数据源
4. 查询返回空时改写query重试