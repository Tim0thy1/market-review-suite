---
name: market-trend-assessment
description: "A 股大盘多维度研判工具。支持三种分析路径：(1) 日频情绪与涨停梯队——量能→催化→结构→风控四段式，覆盖环境判断、主线挖掘、梯队分层、情绪周期定位及次日关注清单；(2) 周线阶段模型——基于七阶段生命周期的仓位取向与预案推演；(3) 群体心理分析——认知偏差识别、极端情绪量化检测、资金分化追踪。正式输出为 HTML 报告。触发：市场分析、情绪周期、阶段研判、主线识别、涨停梯队、行为金融、恐慌贪婪。"
display_name: "市场趋势研判"
display_name_en: "Market Trend Assessment"
version: 1.0.0
visibility: public
---

# A 股大盘多维度分析框架

## 能力概览

本 skill 提供三套独立可组合的分析路径，分别从日频博弈、周线趋势、群体心理三个角度解构市场：

| 路径 | 时间尺度 | 核心关注点 |
|------|----------|-----------|
| 日频情绪 + 涨停梯队 | 盘后日频 | 市场强度、主线、涨停结构、情绪周期 |
| 周线阶段模型 | 周线大周期 | 七阶段定位、仓位取向、分叉预案 |
| 群体心理分析 | 跨周期 | 认知偏差、极端情绪、聪明钱行为 |

> **输出格式**：正式报告为自包含 `.html`；Agent 读取 `references/trend_report_template.html` 后直接生成。对话中仅输出摘要与文件路径。视觉风格遵循靛紫系情绪/周期配色，详见模板文件。
>
> **启动顺序**：金融场景先加载 `wb-finance-skill` 获取红线与时区口径，再调用 westock / neodata 拉取行情数据。

---

## 数据准备

### 外部依赖

| 依赖 | 用途 |
|------|------|
| `wb-finance-skill` | **优先加载**：红线约束、HTML 报告规范、market-state / theme-lifecycle 参考 |
| `westock-data` | 涨跌分布、大盘画像、板块行情、龙虎榜、宏观指标、资讯 |
| `westock-tool` | 连板/跌停排行、资金排行、事件选股 |
| `neodata-financial-search` | 情绪/政策/资金叙事类资讯搜索 |

### 常用命令

```bash
# 市场广度与画像
westock-data changedist
westock-data market-overview --type updown,trade,interval,rotation
westock-data market-overview

# 指数与板块
westock-data quote sh000001,sz399001,sz399006
westock-data sector ranking

# 龙虎榜 / 资讯 / 宏观
westock-data lhb --type institution,hotmoney
westock-data hot stock
westock-data hot news
westock-data news article sh000001 --limit 10
westock-data macro indicator core_indicators_cur

# 排行与筛选（westock-tool，勿写成 westock-data ranking）
westock-tool ranking limitup_days --limit 30
westock-tool ranking limitdn_days --limit 30
westock-tool ranking cap_main_5d --limit 20
westock-tool ranking margin_chg_d
westock-tool event block_past_30 --limit 30
westock-tool event buyback --limit 30
westock-tool event manager_sharechg --limit 30

# 个股资金等（按需）
westock-data fund flow sh600519
westock-data asfund sz000001
westock-data margintrade sz000001
westock-data blocktrade sz000001
westock-data sector constituent <板块代码>

# 自然语言补充（neodata skill 目录下）
python3 scripts/query.py --query "A股市场资金流向和北向资金最新情况"
python3 scripts/query.py --query "近期市场重大新闻事件和情绪分析"
```

按需取用，不必一次跑全。禁止用 clawhub / 第三方 API / web_search 替代上述可信 skill 获取行情数据。

---

## 路径 A：日频情绪与涨停梯队

按「量能→催化→结构→风控」四段式展开：

1. **量能判断 — 市场强度**：强势/震荡/弱势/退潮，依据 `changedist` + `market-overview --type updown,trade`
2. **催化识别 — 主线挖掘**：真主线/次级/脉冲，依据 `sector ranking` + `limitup_days` + `lhb`
3. **结构分层 — 涨停梯队**：龙头 / 中军 / 补涨 / 后排，依据 `limitup_days` + `sector constituent`
4. **风控定位 — 情绪周期 + 次日关注**：结合情绪周期阶段（见下表）和行为金融复核（可选，见路径 C），给出次日观察标的与信号

### 情绪周期阶段速查

| 阶段 | 盘面特征（示意） | 策略取向（条件框架，非指令） |
|------|-----------------|------------------------------|
| 冰点 | 涨停偏少、连板矮、跌停多 | 观望取向，等右侧确认信号 |
| 修复 | 龙头反包、炸板率降、首板增 | 低仓试错取向（条件满足时） |
| 主升 | 连板加速、板块扩散、放量 | 顺势持有确认主线（非指令） |
| 高位震荡 | 龙头分歧、后排掉队 | 降风险敞口、评估补涨质量 |
| 退潮 | 龙头大跌、跌停潮 | 防守取向，等冰点后再评估 |

切换信号、持续性评估逻辑保持原框架；写入 HTML 时用「条件→观察→风险」表述，避免「必须满仓/清仓」口吻。

---

## 路径 B：周线阶段模型

完整框架见 `references/stage-theory.md`。

分析流程：读取阶段论文档 → 拉取指数/涨跌停/板块/资金数据 → 自下而上对照七阶段特征 → 输出当前阶段 + 证据链 + 分叉路径 → 仓位取向与应急预案。

### 七阶段速查

| 阶段 | 名称 | 仓位取向（示意，非指令） |
|------|------|--------------------------|
| 一 | 下跌到企稳 | 轻仓观察 |
| 二 | 超跌反弹 | 偏低仓、快进快出 |
| 三 | 真空期 | 中低仓、等方向 |
| 四 | 主线初期 | 逐步提高敞口（主线确认后） |
| 五 | 主线中期 | 高仓持有主升（条件框架） |
| 六 | 主线末期 | 降低敞口、转防御 |
| 七 | 进入下跌 | 极低仓、等阶段一 |

预警信号：主线成交拥挤、跌速榜持续放大、龙头回撤约 28%–33% 等详见 `stage-theory.md`。

---

## 路径 C：群体心理分析

详细理论见 `references/behavioral-finance-frameworks.md`。

分析流程：

1. 情绪周期六阶段定位（绝望→怀疑→乐观→狂热→焦虑→自满）
2. 十种认知偏差群体检测
3. 五大指标读数：拥挤度、融资、换手、新高新低、媒体情绪
4. 聪明钱 vs 散户资金分化判断
5. 综合结论 + 风险等级（高/中/低）+ 条件化观察建议

拥挤度等阈值见 reference；**极端信号须与价格结构、估值、资金流向交叉验证**，不可单独作为交易依据。

---

## HTML 报告生成

按用户意图选择分析路径（可多路径同页分节）。模板：`references/trend_report_template.html`。

报告必须包含：

- Header + `.tldr` 一句话结论
- 所选路径的分析章节（数据证据 + 解读）
- 风险提示与免责声明

文件保存建议：`{workspace}/market-trend/{路径}_YYYYMMDD.html`。

---

## 使用须知

- 三条路径可互补：日频定节奏，周线定大方向，群体心理做拐点校验
- 多信号冲突时优先重视下行风险
- 数据存在滞后（融资、部分资金流 T+1）；媒体情绪需甄别噪声
- A 股散户占比高、政策冲击大，情绪波动幅度通常大于美股

## 合规声明

文末固定：「以上分析基于公开数据，不构成投资建议。仓位与操作须自行决策并自担风险。」
不使用「建议买入/卖出」措辞；策略表中的仓位表述视为**情景取向**，交付时改写为条件框架。

## 参考文件索引

| 用途 | 路径 |
|------|------|
| HTML 模板 | `references/trend_report_template.html` |
| 周线阶段模型 | `references/stage-theory.md` |
| 群体心理框架 | `references/behavioral-finance-frameworks.md` |
| HTML 风格规范 | `wb-finance-skill/references/html-report-style.md` |
