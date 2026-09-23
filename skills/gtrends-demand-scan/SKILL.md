---
name: gtrends-demand-scan
description: Use when mining Google Trends for micro SaaS / niche demand via seed keywords (词根), choosing what seed words to use, judging whether a trending keyword is a real product opportunity, or building an automated trends-monitoring script without getting rate-limited (429). Covers pytrends, related queries rising, breakout keywords, and keyword-to-product validation.
---

# Google Trends 词根法挖 micro SaaS 需求

## Overview

用 Google Trends 的 **related queries（rising + top）** 从"商业词根"钓出需求候选词。核心原则：**词根必须编码「人群 × 场景 × 商业意图」，Trends 产出的是候选词不是结论**——每个候选词必须回 Reddit/竞品/价格平台做三源验证（见 reddit-pain-mining skill）。

## 反模式（实测踩过的坑）

| 词根类型 | 后果 |
|---|---|
| **工具后缀词根**（Generator / Calculator / Converter / 無料…） | related queries 被娱乐/新闻热点淹没。实测 184 个此类词根跑出 18 个"新词"，17 个是名人/游戏/菜谱噪声 |
| **热点词当种子**（ai headshot generator 等） | 只能验证已知热点，无法系统性发现需求；且热点词吸引的是免费消费者 |
| **单日 300 请求的"激进"脚本** | 实测 ~42 请求/6 分钟即触发 IP 级封锁 1 小时以上 |

## 五类有效词根（种子词 = 人群×场景×商业意图）

1. **购买前语言**：`alternative to`、`spreadsheet for`、`template for`（不满现状/Excel 硬扛 = 替换机会）；变体：`竞品名 + alternative`（如 `MoeGo alternative`）——做某个垂直时，该领域的已知竞品本身就是词根
2. **职业人群**：`for landlords`、`for contractors`、`for therapists`、`for realtors`（"X for 职业"把噪声限制在付费人群内，实测命中率最高）
3. **B2B 工作流动词**：`invoice template`、`booking software`、`late payment`
4. **价格语言**：`fee calculator`、`pricing`
5. **Reddit 信号反推**：把 Reddit 挖到的痛点短语当种子（如 `trade journal`），实现"社区验证有人抱怨 → Trends 验证抱怨变成搜索"

词根维护：related 返回 0 的淘汰；钓出好词的词根扩展同族。

## 流水线（脚本见 gtrends_microsaas_scan.py）

1. **related queries**：窗口 `today 3-m`（比 7 天更压新闻尖峰）；rising ≥ 200% 全收 + top 前 10
2. **商业意图过滤（零请求，本地完成）**：职业词 +2 / 工作流词 +2 / 意图词 +1 / 新闻娱乐词 −3 / 多个大写专有名 −1；<2 分丢弃。通常砍掉 70% 候选——**过滤必须在请求 12 个月曲线之前做**，否则请求预算被噪声烧光
3. **绝对量锚定**：候选词与基准词（GPTs ≈ 日搜 5000）同批请求，均值比值估算 est_daily。Trends 只给 0-100 相对值，跨请求直接比指数无意义
4. **双通道判定**（12 个月曲线）：
   - `breakout_new`：近 21 天之前全年热度 ≤ 1 且近期上升 → 全新需求（少但锋利）
   - `steady_grower`：有历史热度但近 12 周均值 ≥ 前 12 周 ×1.3 → **主猎场**。注意 is_new 过滤器会系统性地把好词滤掉、把一次性热点留下，必须两条通道并存
5. **入库门槛**：est_daily ≥ 50；甜区 200-1000/日（太大轮不到独立开发者）

## 限流纪律（第一工程约束）

pytrends 走 Google 未授权接口，按 IP+指纹限流：

- 每次运行 ≤ 13 个种子词（验证过的安全水位）；间隔 ≥ 15s；每种子 ≤ 5 候选进曲线判定
- 每个种子完成即增量落盘（中断不丢数据）；连续 3 次 429 优雅终止，**不要加塞重试**（会加重封锁）
- 与其他 Trends 任务共用出口 IP 时合并计算请求量
- 抽查单个词用浏览器人工查 trends.google.com——**浏览器和 API 是两条独立判定通道**，API 被封不影响浏览器

## 候选词之后（Trends 给不了的三件事）

每个入库词必须人工/半人工补三刀才算候选成立：SERP 首页是否还有 Reddit/Quora 帖排名（有空隙）；Reddit 能否找到 receipts 原话；相邻品类是否有付费证据。**全自动判定做/不做 = 必然踩坑**。

## 常见错误

- 把 rising 百分比当需求量（它是相对增幅，小词 1000% 可能只是 5→55 次/日）
- 追 Breakout 词（多为新闻事件，90 天内回落）
- 词根随便加但不淘汰零产出词根
- 用内容文章思维判断：有搜索量就做——要先分"搜索驱动生意"还是"外联驱动生意"（零搜索量≠无需求，是需求未被命名）
