---
name: demand-mining-pipeline
description: Use when starting demand mining for a new direction/niche from zero, when a candidate pain needs a go/no-go decision on how deep to dig, or when mining is under time pressure and validation stages (cross-year, review mining, KD, price reality check) risk being silently skipped. Orchestrates reddit-pain-mining, gtrends-demand-scan, competitor-teardown and the KD tool into one gated pipeline.
---

# 需求挖掘流水线（总控）

## Overview

把四个已验证的工具串成一条**带闸门的流水线**：`reddit-pain-mining`（找痛点+裁决）→ `gtrends-demand-scan` + KD 精评（搜索需求侧）→ `competitor-teardown`（竞品缺口+差评）→ 收钱验证。**每个阶段有明确 go/no-go 闸门，任一闸门失败就止损回机会池，不靠"再挖挖看"续命。**

**REQUIRED SUB-SKILLS:** 各阶段细节不在本文件重复，必须读对应 skill：
- 阶段 1-2：`reddit-pain-mining`（信号分类/receipts/记分卡/六级付费证据）
- 阶段 3：`gtrends-demand-scan`（词根/限流纪律/双通道判定）+ `scripts/kd_scan.py`（哥飞版精评）
- 阶段 4：`competitor-teardown`（官网 8 维度 + Trustpilot/Capterra/G2 三平台坑位）

## 流水线与闸门

| 阶段 | 内容 | 闸门 |
|---|---|---|
| P0 矿区选择 | 社区画像：about/new 密度、买家（付费者）密度、反方社区 | G0 主矿区信号密度成立 |
| P1 海捞+聚类 | top+new+句式搜索+评论线程，30-50 receipts 聚 5-8 簇，百分制记分卡 | G1 ≥1 簇 ≥60 分且频率+付费意愿率 ≥60% |
| P2 深挖验证 | **跨年长跨度（≥3 年份独立 receipts）+ 反方社区 + 六级付费证据** | G2 跨年稳定 + 三源 ≥2 源闭合 |
| P3 搜索需求 | GTrends 词根扫描 + SEO 生死簿 + **KD 精评收口** | G3 ≥3-5 词有真实量且 KD 可打 |
| P4 竞品拆解 | 官网 8 维功能矩阵 + **三平台差评聚类** | G4 存在可卡位层 + 定价锚成立 |
| P5 终评+形态 | 记分卡终评 + 三问过滤 + 行业特有约束（如 PHI/YMYL）显式决策 | G5 全过 → 报告落盘 + 更新 AGENTS.md |
| P6 收钱验证 | landing page $1 smoke test → concierge → 收钱访谈 | G6 有人真付钱才算赢 |

P1→P2 只允许带 1-2 个簇过闸，防止全面铺开。

## 压缩纪律（时间紧时唯一允许的操作）

**只能压缩采集样本量（少抓 30 帖），不能跳闸门、不能跳验证类型。** 实测压力场景下子代理会静默砍掉以下五项——它们每一项都对应一次真实踩坑，砍掉即返工：

1. **跨年长跨度验证**（P2）——top 列表全是戏剧帖，痛点必须靠搜索+评论+跨年测；单一时窗的高频可能是事件尖峰
2. **三平台差评**（P4）——只拉 Trustpilot 会漏 Capterra 的隐性收费主题和 G2 的沉默信号
3. **KD 精评**（P3）——预筛 KD 与精评落差可超 30 分（lease violation notice 预筛 1→精评 40.2）；跳过=生死簿失效
4. **价格现实检查**（P2 六级证据 L5/L6）——Etsy $1-3 实价 / 免费竞品覆盖，不做就会重犯"$29 幻想"坑
5. **词性分类**（P1）——服务采购/信息查询类信号不做产品，漏分类=把 lead-gen 当 SaaS 做

赶时间的正确做法：P1 少抓（top25+搜索 3 组）、P4 竞品站拆 5 家而非 11 家——但 P2 的五项验证一个不少，宁可砍样本不砍验证。

## 执行默认值

- **成本分层**：采集（.json/DOM 文本）派 `[secondary_model]` 池便宜模型；判读（聚类/记分卡/聚类判读）留主会话；截图是文本失败时的升级路径
- **通道**：WebBridge（127.0.0.1:10086），请求体写文件再 `curl.exe --data-binary`，evaluate 键名 `code`；Reddit 评论线程走 old.reddit.com
- **落盘**：原始数据 `reddit-data/{方向}_{source}_{date_HHMM}.json`；报告 `analysis_report_{方向}_{date}.md`（社区画像→receipts→记分卡→反对点→形态→下一步）；结论必须回写项目 AGENTS.md
- **反模式**（每个阶段收尾自检）：热门≠趋势、共鸣≠付费、骂得凶≠需求强、"无竞品"先核量、AI 先 receipts 后结论、社区先贡献后索取

## 常见错误

- **闸门当摆设**：G2/G3 不达标仍然"先做个 landing page 试试"——收钱验证（P6）只验证已过关的方向，不救验证不过关的方向
- **并行铺开多簇**：P1 出 5-8 簇全都想验证 → 必须记分卡排序只带前 1-2 簇
- **跳过 P0**：直接挖第一个看到的社区 → 付费者密度不够（如员工社区替代老板社区）会让付费意愿证据全失真
- **P6 前写代码**：闸门 G6 之前不开发，concierge/landing 先收钱
