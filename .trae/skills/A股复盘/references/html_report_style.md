# HTML 复盘报告输出规范

分析/复盘型回答产出 HTML 文件时遵循本规范。

> **权威原则**：图表库、JS 自检、图/表切换、双轴与空值细则以官方 `wb-finance-skill/references/html-report-style.md` 为准。本文件只补充 A 股复盘的**章节结构**与**配色约定**；路径一～四按结构写 HTML，路径五用 `hotspot_report_template.html`。

## JS 语法自检（交付前必须执行）

见 wb-finance `html-report-style.md` §0。含 ECharts 的报告交付前必须 `node --check`。

## ECharts 图表库引用

引库与 option 骨架直接套用 wb-finance 文档；只替换 data / 标签。

```html
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
```

若改为 head **内联**整库：业务初始化须与库分属两个平级 `<script>`（或库在 head、初始化在 body 末尾**单个** script）。**禁止** `<script>` 嵌套；内层 `</script>` 会截断外层，导致 `echarts.init` 不执行。

## 配色规范（硬约束 + 本 skill 视觉）

**硬约束（对齐 wb-finance）**：浅底深字；上涨 `--red` / `#dc2626`，下跌 `--green` / `#16a34a`；**首屏 `.tldr` 结论卡先行**。

**本 skill 视觉**：路径一～四可用石板蓝/行情蓝（`--accent` 建议 `#1e40af`～`#1e3a5f` 区间，勿强行与其它 skill 同色）；路径五热点速览严格跟 `hotspot_report_template.html`（橙红脉冲：`--accent #c2410c`）。禁止默认暗色仪表盘。

## 页面结构（路径一～四）

```
浮动折叠章节导航栏（右上角 ☰ 按钮，点击展开/收起章节目录）
header（标题 + 日期）
.tldr 首屏结论卡（一句话定性 + 关键数据 + 条件→操作→止损框架）
## 技术面 / 情绪 / 短线 / 全景 …（按所选路径）
## 次日关注 / 风险提示
footer 免责声明
```

### 浮动折叠章节导航栏（必含 · 所有 HTML 报告）

所有复盘报告必须包含**浮动折叠章节导航栏**：右上角圆形 ☰ 按钮（`position:fixed`），点击展开/收起章节目录面板，面板列出全部章节锚点，点击跳转。每个 `<div class="section">` 必须带唯一 `id`（如 `sec0`、`sec1`…，深度解读章节用 `sec85`）。

```html
<button class="toc-btn" onclick="document.getElementById('tocPanel').classList.toggle('open')" aria-label="章节导航">☰</button>
<div class="toc-panel" id="tocPanel">
<div class="toc-head">章节导航</div>
<nav class="toc-nav">
<a href="#sec0">零 市场底层状态</a><a href="#sec1">一 多时间维度全景</a>…<a href="#sec85">8.5 重磅深度解读</a>…
</nav>
</div>
```

```css
.toc-btn{position:fixed;right:16px;top:16px;z-index:1000;width:44px;height:44px;border-radius:50%;background:#1e40af;color:#fff;font-size:20px;border:none;cursor:pointer;box-shadow:0 4px 14px rgba(30,64,175,.35);display:flex;align-items:center;justify-content:center}
.toc-btn:hover{background:#1e3a5f}
.toc-panel{position:fixed;right:16px;top:70px;z-index:999;width:230px;max-height:calc(100vh - 100px);overflow-y:auto;background:#fff;border:1px solid #e2e8f0;border-radius:12px;box-shadow:0 10px 30px rgba(15,23,42,.18);padding:12px;display:none}
.toc-panel.open{display:block}
.toc-head{font-weight:700;font-size:14px;color:#1e3a5f;padding-bottom:8px;border-bottom:1px solid #e2e8f0;margin-bottom:8px}
.toc-nav a{display:block;padding:6px 10px;font-size:12.5px;color:#334155;text-decoration:none;border-radius:6px;border-left:3px solid transparent}
.toc-nav a:hover{background:#f1f5f9;color:#1e40af}
```

路径五热点速览：严格按 `hotspot_report_template.html`（已含 `.tldr` + ECharts）。

## 核心逻辑拆解模块（默认必含）

路径一～四的复盘报告中**必须包含**核心逻辑拆解章节。放在"板块表现"与"技术面分析"之间。

### 章节结构

`
## 核心逻辑拆解：为什么今天{主线方向}涨/跌？

### 拆解一：{方向名称} — {一句话定性}
- 事实层：{具体发生了什么}
- 传导层：{产业逻辑/传导链条}
- 映射层：{A股受益方向与个股}
- 持续性：{能走多久？验证条件？}

### 拆解二：{方向名称} — {一句话定性}
...
`

### 拆解数量：1-3 个方向，宁少勿滥。

### CSS 样式（加入 HTML <style> 中）

`css
.deep-dive .dive-card {
  background: linear-gradient(135deg, rgba(30,64,175,0.03), rgba(30,58,95,0.05));
  border: 1px solid rgba(30,64,175,0.15);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 14px;
}
.deep-dive .dive-card h3 {
  color: #1e40af;
  font-size: 15px;
  margin-bottom: 12px;
  margin-top: 0;
  border-bottom: 1px solid rgba(30,64,175,0.1);
  padding-bottom: 8px;
}
.deep-dive .dive-layer {
  margin-bottom: 8px;
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.deep-dive .layer-tag {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(30,64,175,0.1);
  color: #1e40af;
  flex-shrink: 0;
  min-width: 56px;
  text-align: center;
}
.deep-dive .dive-layer p {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #374151;
}
`

### 写作原则

1. **结论先行**：每个拆解的标题就是一句话结论
2. **四层结构**：事实→传导→映射→持续性，层层递进
3. **数据支撑**：每层都有具体数字或事实，不空泛
4. **正反都讲**：既讲逻辑也讲风险/证伪条件
5. **通俗表达**：用大白话讲产业逻辑，不用黑话



## 新增章节样式（可选模块共用）

### 外资机构视角模块

`css
.foreign-perspective { background: #f8f9fc; border-radius: 14px; padding: 20px; margin-bottom: 20px; border: 1px solid #e0e7ff; }
.foreign-perspective h2 { color: #1e40af; border-bottom: 2px solid #e0e7ff; padding-bottom: 10px; margin-bottom: 14px; }
.foreign-perspective .inst-card { background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 10px; border-left: 4px solid #667eea; }
.foreign-perspective .inst-name { font-weight: 700; font-size: 14px; color: #1e3a5f; }
.foreign-perspective .inst-view { font-size: 13px; color: #374151; margin-top: 4px; line-height: 1.5; }
.foreign-perspective .inst-tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-left: 6px; }
.foreign-perspective .tag-bull { background: #dcfce7; color: #166534; }
.foreign-perspective .tag-bear { background: #fce7e7; color: #991b1b; }
.foreign-perspective .tag-neutral { background: #fef3c7; color: #92400e; }
.foreign-perspective .flow-row { display: flex; gap: 12px; flex-wrap: wrap; }
.foreign-perspective .flow-item { background: #fff; border-radius: 8px; padding: 10px 14px; flex: 1; min-width: 140px; text-align: center; border: 1px solid #e5e7eb; }
.foreign-perspective .flow-value { font-size: 20px; font-weight: 700; }
.foreign-perspective .flow-label { font-size: 11px; color: #6b7280; margin-top: 2px; }
.foreign-perspective .compare-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.foreign-perspective .compare-table th { background: #f1f5f9; padding: 8px 10px; text-align: left; }
.foreign-perspective .compare-table td { padding: 8px 10px; border-bottom: 1px solid #e5e7eb; }
`

### 反弹定性分析模块

`css
.rebound-analysis { background: #fff; border-radius: 14px; padding: 20px; margin-bottom: 20px; border: 1px solid #fde68a; }
.rebound-analysis h2 { color: #92400e; border-bottom: 2px solid #fef3c7; padding-bottom: 10px; margin-bottom: 14px; }
.rebound-analysis .rebound-card { background: #fffbeb; border-radius: 10px; padding: 14px; margin-bottom: 10px; border-left: 4px solid #f59e0b; }
.rebound-analysis .rebound-type { font-weight: 700; font-size: 14px; color: #92400e; }
.rebound-analysis .rebound-detail { font-size: 13px; color: #666; margin-top: 4px; line-height: 1.5; }
.rebound-analysis .signal-good { color: #22c55e; font-weight: 600; }
.rebound-analysis .signal-bad { color: #ef4444; font-weight: 600; }
.rebound-analysis .signal-warn { color: #f59e0b; font-weight: 600; }
.rebound-analysis .strategy-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.rebound-analysis .strategy-card { background: #f8f9fc; border-radius: 8px; padding: 10px; border: 1px solid #e5e7eb; }
.rebound-analysis .strategy-card h4 { font-size: 13px; margin-bottom: 4px; color: #1e3a5f; }
.rebound-analysis .strategy-card p { font-size: 12px; color: #666; line-height: 1.5; }
`

### 板块热点密度与Token经济学模块

`css
.hotspot-density { background: #fff; border-radius: 14px; padding: 20px; margin-bottom: 20px; border: 1px solid #e0e7ff; }
.hotspot-density h2 { color: #1e40af; border-bottom: 2px solid #e0e7ff; padding-bottom: 10px; margin-bottom: 14px; }
.hotspot-density .density-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.hotspot-density .density-table th { background: #f1f5f9; padding: 8px 10px; text-align: left; font-weight: 600; }
.hotspot-density .density-table td { padding: 8px 10px; border-bottom: 1px solid #e5e7eb; }
.hotspot-density .heat-high { background: #fef2f2; color: #991b1b; }
.hotspot-density .heat-mid { background: #fffbeb; color: #92400e; }
.hotspot-density .heat-low { background: #f0fdf4; color: #166534; }
.hotspot-density .token-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; border-radius: 10px; padding: 14px; margin: 10px 0; }
.hotspot-density .token-card h4 { font-size: 14px; margin-bottom: 6px; }
.hotspot-density .token-card p { font-size: 12px; opacity: 0.9; line-height: 1.5; }
.hotspot-density .supply-chain { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin-top: 10px; }
.hotspot-density .supply-node { background: #f8f9fc; border-radius: 8px; padding: 10px; text-align: center; border: 1px solid #e5e7eb; }
.hotspot-density .supply-node h5 { font-size: 12px; color: #1e3a5f; margin-bottom: 4px; }
.hotspot-density .supply-node p { font-size: 11px; color: #666; }
`


## 图表质量要求

趋势/对比/占比用 ECharts；查阅型用表格；优先图/表可切换。细则见 wb-finance §3–§4。
