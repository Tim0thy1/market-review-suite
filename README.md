# market-review-suite

跨市场复盘报告合集。每日自动生成美股复盘、A股复盘、盘前分析及视频提示词，同步至此仓库。

## 在线访问

### 方式一：GitHub Pages（推荐）

```
https://tim0thy1.github.io/market-review-suite/
```

### 方式二：htmlpreview 即时预览

```
https://htmlpreview.github.io/?https://github.com/Tim0thy1/market-review-suite/blob/master/index.html
```

无需任何配置，复制链接到浏览器即可。

### 方式三：直接浏览仓库

[https://github.com/Tim0thy1/market-review-suite](https://github.com/Tim0thy1/market-review-suite)

## 报告类型

| 类型 | 所属市场 | 目录命名 | 说明 |
|------|---------|---------|------|
| 🇺🇸 美股复盘 | 美股 | `美股复盘-YYYYMMDD` | 美股深度复盘 |
| 📊 A股复盘 | A股 | `A股复盘-YYYYMMDD` | A股收盘全维复盘 |
| 🔮 盘前分析 | A股 | `A股盘前分析-YYYYMMDD` | A股盘前预测 |
| 🎬 视频脚本 | A股 | `A股视频提示词-YYYYMMDD` | 盘前视频制作提示词 |

## 目录结构

```
market-review-suite/
├── index.html                  # 导航首页（自动扫描，无需手动更新）
├── 美股/
│   ├── 美股复盘-20260818/      # 美股复盘报告
│   └── 美股复盘-20260819/
├── A股/
│   ├── A股复盘-20260818/       # A股复盘报告
│   ├── A股复盘-20260819/
│   ├── A股盘前分析-20260819/   # 盘前分析报告
│   ├── A股盘前分析-20260820/
│   ├── A股视频提示词-20260819/ # 视频提示词
│   └── A股视频提示词-20260820/
└── generate_index.py           # 首页生成脚本（推送前运行）
```

## 声明

所有报告基于公开数据生成，不构成投资建议。# test push permission - Sun Aug 23 09:39:41 UTC 2026
