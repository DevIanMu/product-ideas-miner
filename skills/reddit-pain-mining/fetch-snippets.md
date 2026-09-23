# Reddit 抓取代码片段（配合 reddit-pain-mining skill）

三种通道，按可用性排序。原始数据按 `{subreddit}_{source}_{date}.json` 落盘，供后续分析。
成本分层：这些提取全部是 .json/DOM 文本操作，**应优先派给便宜模型**（`[secondary_model]` 池或无头 `kimi -p -m` 工人），判读留给主模型——见 SKILL.md"成本分层派发"。

## 通道 1：WebBridge 真实浏览器（推荐，带登录态不易被拦）

daemon 在 `http://127.0.0.1:10086/command`，POST JSON：`{"action":..., "args":{...}, "session":"任务名"}`。
Windows 下请求体必须写文件再 `curl.exe --data-binary "@file"`（防中文损坏）。

### 列表帖（top/hot/search）——同源 fetch .json

先 `navigate` 到目标 sub 页面建立同源上下文，再 `evaluate`：

```js
(async () => {
  const r = await fetch('/r/Landlord/top.json?t=month&limit=25', {headers:{'Accept':'application/json'}});
  const d = await r.json();
  return JSON.stringify((d.data?.children||[]).filter(c=>c.kind==='t3').map(c=>{
    const p=c.data; return {title:p.title, id:p.id, score:p.score, ncomments:p.num_comments,
      ratio:p.upvote_ratio, selftext:(p.selftext||'').slice(0,400), permalink:p.permalink};
  }));
})()
```

站内搜索（多关键词循环）：

```js
const r = await fetch('/r/Landlord/search.json?q='+encodeURIComponent('spreadsheet OR excel')
  +'&restrict_sr=1&sort=top&t=year&limit=15', {headers:{'Accept':'application/json'}});
```

### 评论线程——必须走 old.reddit.com

新站 `www.reddit.com/r/sub/comments/{id}/.../.json` 已失效（404/HTML）。先 navigate 到
`https://old.reddit.com/r/{sub}/` 建立上下文，再：

```js
(async () => {
  const r = await fetch('/comments/'+POST_ID+'.json?limit=15&sort=top&depth=1',
    {headers:{'Accept':'application/json'}});
  const d = await r.json();
  const post = d[0].data.children[0].data;
  const comments = (d[1].data.children||[]).filter(c=>c.kind==='t1')
    .map(c=>({score:c.data.score, body:(c.data.body||'').slice(0,350)}));
  return JSON.stringify({title:post.title, selftext:(post.selftext||'').slice(0,500), comments});
})()
```

## 通道 2：直接 .json 端点（curl/脚本，无登录态）

`curl -A "your-UA" "https://www.reddit.com/r/{sub}/hot.json?limit=25"` — 易 403，加自定义 UA、限速 <30 req/min。

## 通道 3：CDP 代理（本机 Chrome 调试端口）

参考实现 `D:\Projects\Reddit\scripts\fetch_subreddit.js`：经 `http://127.0.0.1:3456` 代理驱动真实 Chrome
打开 `.json` URL 并在页面内解析，适合无 WebBridge 时批量抓。

## 评论平台抓取（竞品差评）

Trustpilot 低分评价：`https://www.trustpilot.com/review/{domain}?stars=1&stars=2`，
用 `evaluate` 提取 `article` 卡片 innerText（前 12 条），按主题人工/LLM 聚类。
Etsy 有 DataDome 人机验证，自动化访问会被拦——让用户手动搜索并保存页面 HTML，
从 JSON-LD（`application/ld+json` 的 Product/ListItem）提取价格。

## 自由职业平台（Fiverr / Upwork）人力价格验证

证据性质：六级证据 L2 相邻市场定价——这条需求外包给人做值多少钱，给工具/SaaS 定价提供锚。
经 WebBridge 真实浏览器；Fiverr 无需登录，Upwork 搜索页带登录态结果更完整。
两站都有反爬，同 session 内每个 query 间隔 4-5 秒。

### Fiverr 搜索（卡片在 DOM 里一式三份，必须按 `data-gig-id` 去重）

`https://www.fiverr.com/search/gigs?query=<词>&search_in=everywhere`，然后 evaluate：

```js
(()=>{const seen=new Set();const out=[];
for(const c of document.querySelectorAll('div[data-gig-id]')){
  const id=c.getAttribute('data-gig-id');if(seen.has(id))continue;seen.add(id);
  const lines=(c.innerText||'').split('\n').map(s=>s.trim()).filter(Boolean);
  out.push({
    title:(lines.find(l=>/^I will/i.test(l))||'').slice(0,120),
    price:lines.find(l=>/^From/i.test(l))||'',
    rating:lines.find(l=>/^\([0-9]+\)$/.test(l))||'',
    level:lines.find(l=>/Level/.test(l))||''})}
return JSON.stringify({n_unique:out.length,gigs:out.slice(0,24)})})()
```

### Upwork 职位（发布时间在卡片文本里；"预算"数字是 client 历史花费，不是本单预算）

`https://www.upwork.com/nx/search/jobs/?q=<词>`，然后 evaluate：

```js
(()=>{const out=[];
for(const t of document.querySelectorAll('article')){
  const lines=(t.innerText||'').split('\n').map(s=>s.trim()).filter(Boolean);
  out.push({
    title:(lines.find(l=>l.length>15&&!/Posted|Save|Verified|Payment/.test(l))||'').slice(0,110),
    when:(lines.find(l=>/^Posted/.test(l))||'').slice(0,60)})}
return JSON.stringify({n:out.length,jobs:out.slice(0,15)})})()
```

### 判读口径

- Fiverr 起标价是英镑（×1.27 折美元）= C 端个人买家付得起的人力价 → 工具便宜 3-10x 的价值叙事锚
- Upwork 按 `Posted X ago` 看新鲜度：**小时/天级新帖 = 持续招聘流**，"Ongoing/长期岗" = 重复性需求（支持订阅形态）；单 query 可见 ~10 单 = B2B 小盘，别当大众市场
- 陷阱：gig 数量 = 供给 ≠ 需求；多数 gig 无销量显示；`notice to vacate` 等词会被 DMCA/求职服务污染；跨司法区混杂（搜 eviction 会混入英国/巴基斯坦/迪拜服务），判读时只取美国交付物
