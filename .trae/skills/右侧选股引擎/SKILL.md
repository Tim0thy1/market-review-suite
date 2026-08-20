---
name: right-side-stock-screener
description: "基于中线右侧交易信号的智能选股引擎，整合多数据源筛选优质标的并持续自学习优化。调用当用户需要选股、筛选右侧信号标的、寻找中线交易机会、扫描突破或回踩启动形态时使用。"
display_name: "右侧选股引擎"
display_name_en: "Right-Side Stock Screener"
version: 1.0.0
visibility: public
---

# 右侧选股引擎

## 概览

本 skill 是一个**中线右侧选股系统**，整合 westock-data（结构化行情/技术指标/资金流向/风险事件）与自学习引擎，
自动从多源融合生成候选池，按八维右侧信号清单逐只筛选，输出 10-20 只高质量标的，并跟踪历史表现持续优化筛选逻辑。

**核心能力**：
- 多源候选池融合（板块龙头 + 资金流入 + 涨幅排行 + 龙虎榜 + 综合评分）
- 八维右侧信号清单逐条核查（趋势过滤 → 右侧确认 → 量能 → 板块共振 → 基本面避雷 → 风控 → 持仓周期 → 综合打分）
- 技术指标计算（MA/MACD/KDJ/RSI/BOLL + 自定义箱体突破/回踩启动识别）
- 自学习权重与阈值自适应（根据历史选股后续表现调整参数）
- HTML 报告 + JSON 跟踪双输出

**交易适配规则**：持仓 10~20 个交易日，止盈 8%~11%，单笔严控最大亏损 ≤ -6%，本金复利目标，只做共振右侧。

## 依赖声明

| 依赖 | 用途 |
|------|------|
| **westock-data** | K线/技术指标/资金流向/板块行情/龙虎榜/风险事件/公司简况/财务数据 |
| **Python ≥ 3.7** | 运行选股引擎/自学习模块/报告生成器 |
| **Node.js** | westock-data 命令依赖；HTML 报告 `node --check` 语法自检 |

> westock-tool 排行功能若可用则增强候选池生成；不可用时降级为 westock-data sector ranking + LHB 融合。

## 数据存储约定

| 路径 | 内容 |
|------|------|
| `d:\AI\trae work\stock\right-side-screener\config.json` | 当前筛选配置（权重+阈值） |
| `d:\AI\trae work\stock\right-side-screener\history\YYYYMMDD\selection.json` | 每日选股结果（供自学习回溯） |
| `d:\AI\trae work\stock\right-side-screener\reports\选股报告_YYYYMMDD.html` | HTML 选股报告 |
| `d:\AI\trae work\stock\right-side-screener\learning\learning_log.json` | 自学习调整日志 |

## 工作流程

### 第 0 步：环境检查与初始化

1. 确认 Python 可用：`python --version`
2. 确认 westock-data 可用：`npx -y westock-data-skillhub@1.0.5 search 测试`
3. 确认数据目录存在，不存在则创建：
   ```powershell
   New-Item -ItemType Directory -Force -Path "d:\AI\trae work\stock\right-side-screener\history", "d:\AI\trae work\stock\right-side-screener\reports", "d:\AI\trae work\stock\right-side-screener\learning"
   ```
4. 读取当前配置 `config.json`（不存在则用默认配置初始化）
5. 获取当前日期：`Get-Date -Format "yyyy-MM-dd"`

### 第 1 步：自学习回溯（可选但推荐）

运行自学习模块，检查历史选股的后续表现并更新配置：

```bash
python "<skill路径>/scripts/learning.py" --data-dir "d:\AI\trae work\stock\right-side-screener"
```

- 读取 `history/` 下所有历史选股记录
- 对每条记录，获取当前价格，计算持有期收益
- 按八维信号分类统计命中率
- 命中率高的维度权重微调上调；命中率低的维度权重微调下调
- 输出更新后的 `config.json` 和 `learning/learning_log.json`
- 在报告中展示自学习调整摘要

### 第 2 步：候选池生成（多源融合）

**方案 A — Agent 直接执行 westock-data 命令收集候选（推荐）**：

| 来源 | 命令 | 选取规则 |
|------|------|---------|
| 板块龙头 | `westock-data sector ranking --raw` → `westock-data sector constituent <板块代码>` | TOP5 行业各取前 5 只成份股 |
| 龙虎榜机构 | `westock-data lhb --type institution,hotmoney --raw` | 近 15 日机构/游资买入个股 |
| 资金流入 | `westock-data fund flow <批量候选> --raw` | 主力持续净流入 TOP20 |
| 涨幅排行 | `westock-tool ranking qt_chg_interval --orderby ChgPct10D --limit 50 --raw`（若可用） | 10 日涨幅 TOP20（排除已涨 >30%） |
| 综合评分 | `westock-tool ranking CompScore --limit 20 --raw`（若可用） | 综合评分 TOP20 |

> 去重后候选池通常 30-80 只，进入下一步逐只筛查。

**方案 B — 调用 screener.py 自动生成**：

```bash
python "<skill路径>/scripts/screener.py" --phase candidates --data-dir "d:\AI\trae work\stock\right-side-screener" [--industry <行业名>] [--exclude-300] [--exclude-688] [--exclude-bj]
```

### 第 3 步：逐只筛查（八维右侧信号清单）

对候选池中每只股票执行深度筛查。Agent 可直接调用 westock-data 命令采集数据并按清单核查，
也可调用 screener.py 自动完成：

```bash
python "<skill路径>/scripts/screener.py" --phase screen --data-dir "d:\AI\trae work\stock\right-side-screener" --stocks <逗号分隔代码列表>
```

**数据采集**（每只股票，尽量批量）：

```bash
# K线（至少60根日线，用于MA60和箱体识别）
westock-data kline <code> --period day --limit 60 --raw

# 技术指标
westock-data technical <code> --indicator ma,macd,kdj,rsi,boll --raw

# 资金流向
westock-data fund flow <code> --raw

# 公司简况（获取行业/板块）
westock-data profile <code> --raw

# 风险事件
westock-data risk <code> --raw

# 当前价/成交额从 K线最后一根获取（quote 命令不可用）
```

**八维清单核查**（详细规则见 `references/checklist.md`）：

| 维度 | 核心检查项 | 不达标处理 |
|------|-----------|-----------|
| 一、大趋势过滤 | MA60 走平/向上、股价站稳 MA60 上方、低点逐步抬高、非下降趋势 | **直接淘汰** |
| 二、右侧确认 | A: 箱体突破（≥15日横盘+站稳上沿+放量1.3倍+缩量沉淀）<br>B: 多头回踩启动（MA20向上+未破20日线+重新放量收阳） | **二选一不满足→淘汰** |
| 三、量能硬性 | 启动阳线放量、无无量虚拉 | 不满足→淘汰 |
| 四、板块共振 | 所属板块近3-5日强于大盘、优先主线板块、避开高位退潮 | 不满足→降分 |
| 五、基本面避雷 | 无大额解禁/减持、无业绩暴雷、非ST、日均成交额≥1.5亿、短期未涨超30% | **任意一条→直接淘汰** |
| 六、风控规划 | 明确防守支撑位、最大亏损≤-6% | 不满足→淘汰 |
| 七、持仓周期 | 预期10-20交易日、满20日未达止盈无条件离场 | 标注预期 |
| 八、综合打分 | 图形清晰度、信号共振度、盈亏比吸引力 | 主观加权 |

### 第 4 步：生成报告

调用报告生成器或 Agent 直接写 HTML：

```bash
python "<skill路径>/scripts/report_generator.py" --input "<screener输出JSON路径>" --data-dir "d:\AI\trae work\stock\right-side-screener"
```

**报告内容**：
1. 首屏结论卡：选出标的数量、市场环境定性、整体仓位建议
2. 市场环境速览：大盘指数、市场状态、热门板块
3. 选中的标的列表（10-20只）：每只含代码/名称/行业/信号类型/评分/关键指标/八维通过情况/止损位/预期持有期
4. 候选池统计：总候选数→通过数→淘汰原因分布
5. 自学习状态：权重调整摘要、历史命中率、下次优化方向
6. 风险提示与免责声明

### 第 5 步：保存跟踪记录

将本次选股结果保存到 `history/YYYYMMDD/selection.json`，供下次运行时自学习回溯。

## 指定板块/条件过滤

| 条件 | 参数 | 示例 |
|------|------|------|
| 指定行业 | `--industry` | `--industry 半导体` |
| 排除创业板 | `--exclude-300` | 排除 300xxx |
| 排除科创板 | `--exclude-688` | 排除 688xxx |
| 排除北交所 | `--exclude-bj` | 排除 bj |
| 最小成交额 | `--min-amount` | `--min-amount 200000000` |
| 目标数量 | `--target-count` | `--target-count 15` |
| 回看天数 | `--lookback` | `--lookback 90` |

## 技术指标计算说明

screener.py 内部计算以下指标（不依赖 westock-data technical，但会交叉验证）：

| 指标 | 计算方式 | 用途 |
|------|---------|------|
| MA5/MA10/MA20/MA60 | 收盘价简单移动平均 | 趋势判断、支撑压力位 |
| MA60 斜率 | (MA60今日 - MA60的N日前) / N | 判断MA60走平/向上 |
| MACD | EMA12-EMA26=DIF, DIF的EMA9=DEA, 2×(DIF-DEA)=MACD | 趋势动量 |
| KDJ | RSV→K→D→J 标准算法 | 超买超卖 |
| RSI(6,12,24) | 平均涨幅/平均跌幅 | 强弱判断 |
| BOLL(20,2) | MA20±2×STD | 通道突破/回归 |
| 箱体识别 | 近N日最高最低价的波动率<阈值 → 横盘区间 | 箱体突破判定 |
| 回踩识别 | MA20向上 + 价格回调至MA20附近 + 重新放量收阳 | 多头回踩启动 |
| 量比 | 当日成交量 / 20日均量 | 放量/缩量判定 |
| 区间低点 | 滑动窗口最低点序列 | 低点抬高判定 |

## 自学习机制

### 学习流程
1. 读取 `history/` 下所有历史选股记录（至少 5 次运行后才启动调整）
2. 对每条记录，获取选股日到当前日的 K 线数据
3. 判定结果：止盈（≥8%）、止损（≤-6%）、超时（20日未达目标）、持有中
4. 按八维信号分组统计命中率，调整权重和阈值
5. 调整幅度受配置约束（每次最大 5%，累计上限 20%）
6. 输出更新后的 `config.json` 和调整日志

### 安全约束
- 每次调整幅度 ≤ 5%（`adjustment_rate`）
- 单维度累计调整上限 ≤ 20%（`max_weight_change`）
- 阈值调整上限 ≤ 10%（`max_threshold_change`）
- 最少样本数 ≥ 5（`min_samples`）才启动调整
- 调整日志完整记录，可回溯

## 输出规范

### HTML 报告
- 自包含 HTML（内联 CSS + ECharts CDN）
- 浅底深字研报风，上涨红下跌绿
- 首屏 `.tldr` 结论卡先行
- 交付前 `node --check` 内联 JS 语法自检

### JSON 跟踪
- 完整选股结果（含候选池、通过/淘汰明细、指标数据、八维检查详情）

## 快速启动

用户说「选股」「筛选右侧信号」「找中线标的」等触发词时，按第 0-5 步依次执行。

## 重要声明

> 本技能仅提供基于技术信号的客观筛选结果，不构成投资建议。数据可能有延迟，以交易所官方为准。投资有风险，决策需谨慎。
