# Product Ideas Miner

从 Reddit 社区挖掘 micro SaaS 需求的一套 Agent Skill + 工具脚本。核心方法论：**Reddit 找痛点不找点子；原子证据 = receipts（原话+链接+社区）；先收钱验证再开发。**

已在真实方向（美国小房东法律文书工具站）完整走通：Reddit 痛点挖掘 → 搜索需求验证 → 竞品差评交叉验证 → 记分卡 86/100。

## Skill 总览

| Skill | 角色 |
|---|---|
| `demand-mining-pipeline` | ★ 总控：把下面三个 skill + KD 工具串成带闸门 G0-G6 的流水线；含"压缩纪律"（赶时间只能缩样本量，不能跳验证类型）与 **P3 渠道分叉**（搜索型用 KD / 触达型用 list-gate） |
| `reddit-pain-mining` | 找痛点：receipts 证据制、**六类信号**（含"系统间搬运"/glue）、百分制记分卡（≥60 深挖）、六级付费意愿证据 |
| `gtrends-demand-scan` | 搜索需求侧：词根=人群×场景×商业意图、商业过滤、双通道判定、限流纪律、"什么时候不该用 GTrends" |
| `competitor-teardown` | 竞品侧：官网 8 维度功能矩阵 + Trustpilot/Capterra/G2 差评挖掘（含各平台抓取坑位；必查主题含"集成与同步缺失"） |

## 流水线

```
P0 矿区选择 ─G0→ P1 海捞+记分卡 ─G1→ P2 深挖验证(跨年/六级证据) ─G2→
P3 渠道分叉 ─┬→ 搜索型: GTrends+KD精评 ─G3→ P4 竞品拆解+差评 ─G4→
             └→ 触达型: list-gate(≥50 家目标企业名单) ─G3′↗
P5 终评+三维(形态/定价锚/运维负担) ─G5→ P6 收钱验证 ─G6→ 通过才开发
```

任一闸门失败即止损回机会池，不靠"再挖挖看"续命。细节见 `skills/demand-mining-pipeline/SKILL.md`。

## 安装

### Kimi Code / Claude Code 等 Agent

把 `skills/` 下每个目录复制到用户级 skill 目录：

```bash
# Kimi Code
cp -r skills/* ~/.kimi-code/skills/
# Claude Code
cp -r skills/* ~/.claude/skills/
```

重启会话后 skill 自动可检索（按 description 触发）。

## 依赖脚本

| 脚本 | 用途 |
|---|---|
| `skills/gtrends-demand-scan/gtrends_microsaas_scan.py` | GTrends 词根扫描（pytrends，需 `pip install pytrends pandas`） |
| `scripts/kd_scan.py` | 哥飞版 KD 精评批量查询（需 `WC_KD_TOKEN` 环境变量或 `--token`） |
| `scripts/glue_scan.py` | 搬运信号（glue）扫描器：回扫已归集语料找"系统间手工搬运"receipts（manually enter / doesn't sync / export to excel / double entry），零依赖 |

Skill 中提到的 WebBridge（127.0.0.1:10086）是本机浏览器控制通道，属于执行环境而非本仓库内容；无此环境时按各 skill 内的备选方案（无头 CLI 工人/纯脚本）执行。

## 许可证

MIT
