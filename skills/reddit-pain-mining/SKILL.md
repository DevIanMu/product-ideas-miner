---
name: reddit-pain-mining
description: Use when mining Reddit for user pain points to validate a product or micro SaaS idea, collecting posts/comments at scale, judging whether a pain is worth building for, verifying willingness to pay, checking competitor weaknesses via review sites, or estimating realistic pricing for digital products. Covers subreddit selection, signal scoring, receipts evidence, Trustpilot/G2 review mining, Etsy/Gumroad price checks, YouTube view/subscriber demand validation, Upwork/Fiverr human-price anchors.
---

# Reddit 痛点挖掘与验证

## Overview

Reddit 用来找**痛点**不是找点子。原子证据单位是 **receipt：一条可溯源的用户原话（原话 + 链接 + 社区 + 用户名）**。任何结论必须能指回 receipts；收集不到 3 条以上独立 receipts 的痛点不算候选。

## 五类信号与候选门槛

| 信号 | 价值 |
|---|---|
| 反复出现的抱怨 | 频率 = 市场大小 |
| 手工方案（Excel/Zelle/脚本凑合） | 有付费意愿 + 没工具 = 机会，**最强信号** |
| 求助帖（"有没有工具能…"） | 即时明确需求 |
| 已有工具的吐槽 | 竞品验证市场 + 空隙 |
| 购买前语言（best X for Y / X vs Y / alternative to） | 接近付费 + 天然 SEO 选题 |

反面信号：纯幻想帖、单帖无共鸣、"我做了个工具"晒帖（是供给不是需求）。
**候选门槛**：反复提及 + 手工方案 + 吐槽竞品，三条至少占两条。

## 去哪挖

- 高密优先：r/SomebodyMakeThis、r/smallbusiness、目标垂直 sub（r/Landlord、r/freelance…）。**不要平均撒网大社区**（r/Entrepreneur 情绪帖淹没信号，实测密度最低）
- 反方视角：r/Tenant 之于 r/Landlord——用户抱怨你的目标人群什么，就是合规/透明度工具机会
- 评论区是金矿：upvote 平平的帖，评论里一排 "same here" 才是强度信号；**土办法越复杂，付费空间越大**

## 采集方法

搜索句式库：`is there a tool`、`how do you handle/track`、`drowning in spreadsheets`、`alternative to`、`X vs Y`、`drives me crazy`。Google 用 `site:reddit.com/r/{sub} "句式"`。

抓取通道与代码片段见 [fetch-snippets.md](fetch-snippets.md)：列表用 `top.json`/`search.json`，**评论线程必须走 old.reddit.com**（新站 permalink `.json` 已失效）。每帖记：链接、sub、日期、信号类型、一句话痛点、原话、共鸣数、付费线索。

## 成本分层派发（采集 vs 判读）

采集是机械劳动，判读（识别信号、聚类、打记分卡）才是智力劳动——分层降低成本：

**方式 1（原生，推荐）：`[secondary_model]` 子代理模型池**
config.toml 配好便宜 provider 的模型别名 + 变体后，Agent/AgentSwarm 工具获得 `model` 参数，按次指定：

```toml
[secondary_model]
default_model = "<便宜模型别名>"          # 如 Ark 上的 DeepSeek Flash：列表抓取、评论线程、模板页提取
[secondary_model.models]
"<便宜模型别名>" = "默认。Reddit .json 抓取、机械格式化、量大的收据提取"
"<便宜视觉模型别名>" = "需要读截图时"
```

- 池别名必须是已配置的 `[models]` 条目；`"primary"` = 主会话模型（贵），留给判读类子代理
- 思考档位：`[secondary_model].default_effort = "low"` 是池级强制（会连 "primary" 一起降级，慎用）；精细做法是给便宜模型注册 `default_effort = "low"` 的变体别名
- **Reddit 抓取全部是 .json/DOM 文本提取，不需要多模态**；截图只在反爬/渲染异常时作升级路径
- 生效于新会话（工具描述启动时固化）

**方式 2：无头 CLI 工人**：`kimi -p -m <便宜别名> --agent-file <工人.md> "<机械工单>"`——独立进程独立模型，可与方式 1 并存，适合池外并行。

**方式 3：机械工单过渡**（未配置池时）：子代理工单写成"跑固定 curl/evaluate 序列 + 原样返回紧凑结果"，禁止子代理做信号判断——判断留在主会话。

## 需求记分卡（百分制）

六个维度各打 0-5 分，按权重加权后归一到 100 分：**总分 = 加权和 ÷ 70 × 100，取整**。

| 维度 | 权重 | 问法 |
|---|---|---|
| 频率 | ×3 | 多少独立帖/评论提到？ |
| 强度 | ×2 | 是否真金白银损失/骂人/求人？ |
| 付费意愿 | ×3 | 有"我花过钱/愿意付"吗？ |
| 付费能力 | ×2 | B2B/技术/高收入人群？ |
| 手工方案 | ×2 | Excel/外包/脚本凑合？ |
| 竞品空隙 | ×2 | 现有工具被骂难用/缺功能？ |

**判定**：总分 **≥ 60** 且 频率+付费意愿两项得分率 **≥ 60%**（即 (频率×3+付费意愿×3) ÷ 30 ≥ 0.6）→ 深挖；50-59 观察；<50 淘汰。历史报告若用未加权 /30 分制，直接看得分率即可换算（24/30 = 80% ≈ 80 分）。

## 付费意愿：六级证据（从弱到强）

1. **直接信号**：用户原话"愿意付"（稀有，"shut up and take my money" 是玩梗不是订单）
2. **相邻市场定价证据**：无直接信号时查相邻品类真实成交价（Kiplinger/行业报告/G2 定价页）——先例：退休教练 $2000-6000/季 证明"这类问题有人付费"。**Upwork/Fiverr 人力市场价**：搜痛点的交付物（eviction notice、demand letter、spreadsheet setup），Fiverr 起标价 = 个人买家为这份交付物实际付得起的人力价，Upwork 按发布新鲜度看招聘流——先例：房东驱逐通知人力起草 $25-160/份，工具定 $9-15/月就有"省一次 freelancer 钱就回本"的锚。注意三个坑：gig 数量是**供给不是需求**；多数 gig 无销量显示；`notice to vacate` 这类词会被 DMCA/求职服务污染结果，需甄别
3. **竞品差评挖掘**：Trustpilot/G2 拉竞品 1-2 星评价，按主题聚类（客服失联/资金问题/rigid）。既是空隙证据也是差异化来源。**验证过的结构：Reddit 吐槽 + Trustpilot 差评 + 搜索需求三源互证**
4. **YouTube 需求验证**：搜痛点关键词，看头部视频播放量和频道订阅数。判读：某问题有 10 万+ 播放的视频或万人订阅的垂直频道 = 问题被广泛关注、且 YouTube 作为获客渠道被预验证（IdeaBrowser 用 "63K+ views" 作 proof signal 的同款手法）。**注意：播放量证明的是关注度和需求规模，是付费意愿的间接证据而非直接证据——观众愿意花时间 ≠ 愿意掏钱；播放量高但评论区全在找免费方案时要降权**
5. **市场价格现实检查**（防踩坑，必做）：Etsy/Gumroad 搜同类数字产品看真实客单价。先例：以为模板能卖 $29，Etsy 实价 $1-3 → 整个变现模型重做。Gumroad 零产品 = 该形态未被验证
6. **免费竞品覆盖检查**：搜 "free + 品类"（apartments.com 免费 4 单元、Innago 免费、Stessa 免费）。如果免费工具已覆盖你的功能清单，回答不了"为什么有人付你钱"就换方向。记住那句原话："Property management apps are just someone else's spreadsheets that you have to pay for"

## 三源验证（Reddit 之外的独立确认）

Reddit 看原话 → 搜索工具看主动需求（Google Ads 关键词规划师/CPC，出价 = 有人花钱买这些用户）→ 电商/评论平台看购买反馈 → 内容平台看传播潜力 → 自由职业平台看人力成本价（这条需求外包出去值多少钱）。三源齐了候选才成立。

## 词性分类（避免把非 SaaS 需求当产品做）

候选词/痛点先分类：**工具需求**（software/template for X）/ **服务采购**（insurance/lawyer/seo for X → lead-gen 或内容选题，不是 SaaS）/ **信息查询**（what is X → 淘汰）/ **内容选题 / 营销话题 / 短期热闹**。

## 反模式

- 热门 ≠ 趋势（单帖爆火 vs 跨周跨社区重复出现）
- 共鸣 ≠ 付费（21 评论"我也想要"的 C 端 App 记分卡 20/70 → 淘汰）
- 骂得凶 ≠ 需求强（看有没有找替代方案/问价格/问迁移）
- 只看一个社区（每个 sub 有自己的偏见，跨 3-5 个对比）
- 让 AI 直接给结论（先输出 receipts 证据，再判断）

## 红线

先贡献后索取（答 10 个问题再软性提及）；读每个 sub 的 self-promotion 规则；把 Reddit 当用户访谈现场，不是广告渠道。
