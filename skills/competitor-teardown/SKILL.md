---
name: competitor-teardown
description: Use when dissecting a competitor's official website (feature matrix, pricing, state coverage, funnel structure) or mining competitor bad reviews across Trustpilot/Capterra/G2 to find positioning gaps. Covers the extraction checklists, platform-specific scraping gotchas, cross-platform theme clustering, and cost-tiered dispatch (cheap-model headless workers for scraping, main model for planning/synthesis).
---

# 竞品拆解与差评挖掘

两个工作流：A=官网功能拆解（功能矩阵/缺口判定），B=三平台差评挖掘（Trustpilot/Capterra/G2）。
总原则：**主 agent（贵模型）只做规划、判读、合成；页面抓取尽量下沉给便宜工人**（无头 CLI 子会话或纯脚本），因为抓取是机械劳动，规划判读才是智力劳动。

## 成本分层派发（先读）

**方式 1（原生，推荐）：`[secondary_model]` 子代理模型池 + 思考档位绑定**

在 `~/.kimi-code/config.toml` 配置后，Agent/AgentSwarm 工具会多出 `model` 参数，主代理**每次派发时指定用哪个模型**：

```toml
# 便宜 provider（火山方舟 Ark = OpenAI 兼容协议）
[providers.ark]
type = "openai"
base_url = "https://ark.cn-beijing.volces.com/api/v3"
api_key_env = "ARK_API_KEY"

[models."ark/deepseek-v3"]
provider = "ark"
model = "deepseek-v3-241226"      # 按你的 Ark 控制台模型 ID 填
max_context_size = 64000

# K2.8 的多模态+low thinking 变体（照抄主模型别名同 provider/底层 model 名）
[models."k28-vision-low"]
provider = "managed:kimi-code"
model = "kimi-for-coding"          # K2.8 底层 model 名，从现有别名抄
max_context_size = 262144
capabilities = [ "thinking", "always_thinking", "image_in", "video_in", "tool_use" ]
support_efforts = [ "low", "high", "max" ]

[models."k28-vision-low".overrides]
default_effort = "low"

# 子代理模型池：default=便宜模型，看图任务主代理派发时指定 k28-vision-low
[secondary_model]
default_model = "ark/deepseek-v3"
[secondary_model.models]
"ark/deepseek-v3" = "默认。纯 DOM 文本抓取、机械提取、格式化工单——不需要看图"
"k28-vision-low" = "需要读 WebBridge 截图/看图时选这个（多模态 + low thinking）"
```

要点：
- 池里别名必须是已配置的 `[models]` 条目；`"primary"` 保留字=主代理自己的模型
- **思考档位三档控制**：`[secondary_model].default_effort`（整段强制）＞变体条目的 `default_effort`（overrides 固定）＞全局 `[thinking].effort`。给同模型注册不同 default_effort 的"变体别名"即可实现"K2.8 low / K2.8 high"同池共存
- `force = true` 可收回选择权（全子代理锁一个模型）；TUI 里 `/secondary-model` 随时换默认
- 注意：managed 官方只给 k3 家族声明了 support_efforts，手动给别的模型声明后若后端不认，观察输出质量；兜底方案是整段 `default_effort = "low"`
- DeepSeek 非多模态 → **工人工单默认走 DOM/innerText 文本提取，不看截图**；截图只作为文本提取失败时的升级路径，由主代理改用 k28-vision-low 重派

**方式 2：无头 CLI 工人（池外并行/外部调度）**

`kimi -p -m ark/deepseek-v3 --agent-file ~/.kimi-code/agents/web-scraper.md "<任务>"`——独立进程、独立模型，可与方式 1 并存。工人 agent 文件：`tools` 限 Bash+Write、body 写明"最后一条消息是给调用者的完整结果"、工单写死 WebBridge 用法与输出格式。

**方式 3：会话内子代理 + 机械化工单**（未配池时的过渡）：工单写成"跑固定 curl/evaluate 序列+原样返回紧凑结果"，禁止子代理做分析判断。

## WebBridge 速查（工人/子代理工单里必须写死）

- daemon `http://127.0.0.1:10086/command`，POST `{"action","args","session"}`；每个 session 独立标签组
- **请求体必须 Write 工具写文件再 `curl.exe --data-binary "@file"`**（Windows shell 会损坏内联 JSON）；文件名带随机后缀防并发覆盖
- `navigate` → sleep 3-5s → `evaluate`；返回 envelope `{"ok":true,"data":{"type":"string","value":"..."}}`，超长用 slice 分批
- 只读操作：不登录不注册不关标签；被反爬拦就记录现象跳过，不硬刚

## 工作流 A：官网功能拆解

**适用**：要回答"这家覆盖了什么功能、定价多少、漏了什么、我能做得更好的在哪"。

**拆解维度**（按 11 站实测经验收敛，工单里照抄）：
1. 功能全景：发布/筛选/收租/记账/维修/沟通/eSign/文书模板——哪些有哪些没有
2. 法律文书能力：有没有交互式生成器（问答→文档）？静态模板？按州吗？覆盖几种文书？
3. 迟租处理：reminder 自动化？滞纳金规则引擎？有没有"提醒→正式通知"升级链？
4. deadline 追踪：押金退还倒计时/notice 等待期/法定时限提醒——多数竞品空白，重点记录
5. 检查/举证：inspection 工具（拍照/condition report）？人工服务还是软件？
6. 定价：各档月价/免费档内容/按次购买/按 unit 计价/隐性收费；定价页 URL 记下
7. 目标客群：话术指向（accidental landlord vs PM 公司）——决定你是不是它的弃子用户
8. 内容与漏斗：州法内容页数量？内容→工具之间有没有承接（生成器/计算器/倒计时组件）？

**判读**：每站一句话弱点；最后按"功能缺口对照表"逐条判定自己 MVP 各项是 ✅缺口 / ⚠️形态已有护城河浅 / ❌红海。警惕三句话：'不做X是因为没人要'、'它有Y所以Y不是缺口'、'免费档没有=市场空白'（可能是成本结构做不了）。

## 工作流 B：三平台差评挖掘

**适用**：要回答"用户付过钱后骂什么、哪些骂点我能结构性规避或 weaponize"。

### Trustpilot
- URL：`https://www.trustpilot.com/review/{domain}?stars=1&stars=2`；evaluate 提取 `article` 卡片 innerText 前 300 字 + 评分（img alt）
- 坑：页面顶部混有 2-4 条平台"高亮正向"评价（过滤参数对它不生效），聚类前必须剔除
- 样本 <5 条低分 → 标"样本不足"跳过，不硬凑

### Capterra（坑最多，务必照做）
- **"Lowest Rating"排序页是坏的**（服务端 bug）：只渲染 1-2 条真实评论，其余用占位假评论 "Great Product with Room for Improvement" 重复填充——低分样本必须走 **Rating 筛选器**，不能信排序页
- 匿名筛选配额：每页仅 1 次筛选变更，之后静默 no-op → 登录墙（不登录）；换星级需清 sessionStorage + 重新导航
- 下拉交互须用 daemon 原生 `click`（`[data-testid=filter-overallRating-N]`），合成事件无效；Cloudflare 验证等 15s 可自愈
- 评论提取：评分/日期/Pros 一句/**Cons 原文前 250 字（重点）**/评论者公司规模
- 全局剔除占位假评论后再聚类（实测一场出现 43 次）
- Baselane 这类产品可能无低分 → 标注"结构性缺失"，转 Trustpilot/Reddit 补

### G2
- 低分筛选参数是 `filters[nps_score][]`（`rating` 参数已失效）
- 提取 "What do you dislike" 前 250 字 + 评分 + 日期
- 这些产品 G2 评分普遍 4.6-4.8，低分样本极小（1-4 条常见）→ 只作方向参考，不过度推断
- **沉默信号也是情报**：产品已从 G2 下架（如 Hemlane 301 到分类页）、零评论（Unclaimed Profile）——说明小盘产品的用户声音只在 Reddit/Trustpilot，Capterra/G2 研究对小竞品会系统性漏信号，必须交叉 Reddit

### 判读与聚类（留在主会话/贵模型做）
- 主题聚类：主题 | 出现次数 | 代表原话（英文原文+评分+日期）。原话必须页面实读，禁止编造
- 跨竞品横向：按出现家数排序；特别注意：客服失联、隐性收费/续费偷袭、资金问题、文书质量/合规缺陷、rigid 逼购
- 三条判读纪律：①差评盲区≠需求已满足（功能太新还没积累抱怨）②gig/供给数量≠需求 ③资金类恐怖故事全部来自碰钱的产品——文书工具站天然免疫该类别
- 单条高价值证据单独记录（如竞品五星好评自证"某功能 the one thing it's been missing"=窗口期证据）

## 落盘约定
- 功能矩阵：`reddit-data/competitor_feature_matrix_YYYY-MM-DD.md`
- 差评原始数据：JSON/txt + 聚类报告 md（`trustpilot_lowstar_roundN_*.json`、`capterra_reviews_report_*.md`、`g2_reviews_report_*.md`）
- 合成结论写回需求报告对应章节 + 更新项目 AGENTS.md 证据链
