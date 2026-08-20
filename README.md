# market-review-suite

跨市场复盘报告合集。每日自动生成美股复盘、A股复盘、盘前分析及视频提示词，同步至此仓库。

## 在线访问

### 方式一（推荐）：GitHub Pages

```
https://tim0thy1.github.io/market-review-suite/
```

> 如果打不开，需要在仓库 Settings → Pages → 将 Source 设为 `master` 根目录，保存后等待几分钟即可生效。

### 方式二：htmlpreview 即时预览

```
https://htmlpreview.github.io/?https://github.com/Tim0thy1/market-review-suite/blob/master/index.html
```

无需任何配置，复制链接到浏览器即可。

### 方式三：直接浏览仓库

[https://github.com/Tim0thy1/market-review-suite](https://github.com/Tim0thy1/market-review-suite)

## 报告类型

| 类型 | 目录前缀 | 说明 |
|------|---------|------|
| 📊 A股复盘 | `a-share-review-` | A股收盘全维复盘 |
| 🇺🇸 美股复盘 | `us-market-review-` | 美股深度复盘 |
| 🔮 盘前分析 | `a-share-premarket-` | A股盘前预测 |
| 🎬 视频脚本 | `premarket-video-` | 盘前视频制作提示词 |

## 目录结构

```
market-review-suite/
├── index.html                  # 导航首页（自动扫描，无需手动更新）
├── a-share-review-YYYYMMDD/    # A股复盘报告
├── us-market-review-YYYYMMDD/  # 美股复盘报告
├── a-share-premarket-YYYYMMDD/ # 盘前分析报告
└── premarket-video-YYYYMMDD/   # 视频提示词
```

## 声明

所有报告基于公开数据生成，不构成投资建议。