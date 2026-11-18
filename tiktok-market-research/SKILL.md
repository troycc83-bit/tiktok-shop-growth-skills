---
name: tiktok-market-research
description: 跨平台市场调研（零成本，美国 TikTok Shop 卖家专用）。围绕耳机类目，聚合 Google 搜索/Trends、Amazon 榜单与评论、TikTok 前台与评论、Reddit/YouTube 讨论，做交叉验证判断"真品类还是闪 trend"，并从竞品差评里挖产品机会点和用户真实语言。内置三个免 key 抓取工具：Reddit 真实评论（PullPush API）、TikTok 视频/评论/字幕（本地 scraper 服务）、Amazon 搜索/评论聚合（本地 scraper 服务）。当用户说"调研 XX 品类""这个品能不能做""挖竞品差评""抓 Reddit/TikTok/Amazon 评论""看看市场机会""多平台验证一下""用户都在抱怨什么"时使用。Triggers: 市场调研, 选品调研, 竞品分析, 差评挖掘, 用户痛点, Reddit评论, TikTok评论, Amazon评论, 交叉验证, market research, product research.
agent_created: true
---

# 跨平台市场调研（Market Research）

## 目的

用零成本公开信息回答一个核心问题：**这个品/赛道值不值得做，机会点在哪里**。产出不是一份大而全的报告，而是能直接指导决策和喂给内容 Skill 的"机会点 + 用户语言库"。

## 调用前必读

- 共享知识库 `~/.workbuddy/skills/tiktok-shop-growth/shared-kb/user-language.md`（已有买家措辞）、`competitors.md`（竞品清单）。
- 来源与验证规则：`references/sources-and-validation.md`（含三个抓取工具的完整用法和实测结论）。

## 工作流（按需触发，无固定频率）

### 第 1 步：明确调研对象

向用户确认（缺省就自己假设并标注）：
- 品类/产品词（如"开放式耳机""open-ear earbuds"）
- 目标市场（默认美国）
- 目的：找新品机会 / 验证已有品 / 挖差评机会 / 找内容素材

### 第 2 步：多平台采集（能自动的全自动）

| 平台 | 自动程度 | 采集内容 | 工具 |
|------|---------|---------|------|
| Google 搜索 / Trends | ✅ 直接联网搜 | 需求趋势、搜索方向、用户真实提问 | 联网搜索 |
| **Reddit 评论** | ✅ 内置脚本（免 key） | 真实用户原话、痛点、未被满足场景 | `fetch_reddit_comments.py` |
| **TikTok 视频/评论/字幕** | ✅ 内置本地服务（免 key） | 爆款视频数据、评论区、台词 | `fetch_tiktok.py` |
| **Amazon 搜索/评论聚合** | ✅ 内置本地服务（免 key） | ASIN、价格带、评分、褒贬方面 | `fetch_amazon.py` |
| YouTube / 评测媒体 | ✅ 联网搜 | 深度测评、pros/cons | 联网搜索 |

#### 抓 Reddit 真实评论

搜索引擎只能拿被索引的摘要，Reddit 官网直连又被人机验证挡住。**用内置脚本走 PullPush 公开归档 API（免 key、免登录、免浏览器）**：

```bash
python3 ~/.workbuddy/skills/tiktok-market-research/scripts/fetch_reddit_comments.py \
    --query "UGREEN ClipBuds" --size 50 --out /tmp/reddit_comments.json
python3 ~/.workbuddy/skills/tiktok-market-research/scripts/fetch_reddit_comments.py \
    -q "open ear earbuds noise cancelling" -s 50 --min-score 2
```
- 仅标准库，无需 pip 安装。数据是非实时归档（有延迟），新上市产品可能搜不到——如实说明，不要编造。
- 若直连被拦，脚本会打印 `source_url`，改用网页抓取工具访问同一 URL 提取 JSON。

#### 抓 TikTok 真实评论 / 字幕

TikTok 评论需动态签名，浏览器抓不到。内置 `omkarcloud/tiktok-scraper` 本地服务解决（免 key、免账号）：

```bash
# 一次性装依赖 + 启动服务（持续运行的终端/后台任务，端口 8000）
pip3 install bottle cheroot curl_cffi marshmallow
python3 ~/.workbuddy/skills/tiktok-market-research/scripts/fetch_tiktok.py --serve

# 抓评论 / 字幕 / 详情
python3 .../fetch_tiktok.py --comments "https://www.tiktok.com/@xxx/video/769..." --out comments.json
python3 .../fetch_tiktok.py --transcript 7692114317151423775 --out transcript.json
python3 .../fetch_tiktok.py --details 7692114317151423775
```
- 字幕接口带时间戳台词，可直接喂给视频拆解 Skill（替代 Whisper）。
- 搜索接口对出口 IP 敏感；被挡时如实说明，用已知视频链接走 details/comments。
- **Scrapy 不适用**：TikTok 需 msToken + X-Bogus/A_Bogus 动态签名，Scrapy 裸请求直接 403，外挂 Playwright/逆向库维护成本极高。

#### 抓 Amazon 搜索 / 评论聚合

内置 `omkarcloud/amazon-scraper` 本地服务（免 key、免账号，端口 8001 避开 TikTok）：

```bash
# 一次性装依赖 + 启动服务
pip3 install bottle cheroot curl_cffi beautifulsoup4 lxml marshmallow
python3 ~/.workbuddy/skills/tiktok-market-research/scripts/fetch_amazon.py --serve

# 搜索找竞品 ASIN / 价格带 / 评论数（快）
python3 .../fetch_amazon.py --search "open ear earbuds" --out search.json
# 评论聚合：AI 摘要 + 评分分布 + 褒贬方面（慢，30s+ 过 WAF）
python3 .../fetch_amazon.py --reviews B0D2XRXNGY --out reviews.json
python3 .../fetch_amazon.py --bestsellers electronics
```
- **机会点来源**：`customers_say.aspects` 里 `sentiment=negative/mixed` 的方面 = 差评机会点。
- **局限**：匿名访问拿不到逐条评论文本（`reviews=[]`）；连续请求会触发 WAF 间歇 404，脚本已内置 2 次重试，稍等即恢复。逐条原话改用 Reddit/TikTok 或用户贴文本。

#### 通用原则

- **能联网搜的直接搜**，不要让用户动手。
- 遇到反爬/登录墙：先试内置脚本 / 网页抓取；受阻就如实说明，降级为"用户贴链接或复制评论文本，Skill 负责分析"，不假装抓到了数据。
- **绝不编造平台数据**。抓不到就标注"数据未获取"，只用能拿到的信息下判断。

### 第 3 步：交叉验证（核心判断）

```
TikTok 热 + Google 搜索升 + Amazon 有量/评论  → 真品类机会，值得投入
TikTok 热 + 其他平台静                       → 疑似闪 trend，谨慎
多平台都有量 + 差评集中                       → 明确差异化机会点
```

给出明确结论：机会等级（高/中/低/存疑）+ 一句判断理由。

### 第 4 步：挖评论，提取三类资产

从能拿到的评论（竞品差评优先）里提取：
1. **差评机会点**：反复出现的问题 = 产品差异化方向（Amazon aspects 的 negative/mixed + Reddit 抱怨 + TikTok 评论）
2. **用户语言**：买家描述痛点的英文原话（直接可当 hook 文案）
3. **场景缺口**：用户提到但竞品没满足的使用场景

按 `user-language.md` 的格式整理，**主动写回共享知识库**，供仿写 Skill 使用。

### 第 5 步：输出（一页纸，结构化）

```
# 市场调研：[品类/产品]
结论：机会等级 + 一句理由
跨平台信号：Google / Amazon / TikTok / Reddit 各自一句话
差评机会点：3-5 条（每条=问题+可差异化方向）
用户语言库：5-10 条真实措辞（英文原话）
建议下一步：做内容 / 继续验证 / 放弃
```

## 红线

- 不编造销量、价格、排名、评论等数据；抓不到就标注，不用估算数字填充
- 行业报道数据（如 Kalodata 报道的 GMV）要标注"来源为公开报道，非官方数据，仅作方向参考"
- 区分"事实"与"判断"，判断要给出依据
- 明确标注数据来源与时间，AI 聚合评论与逐条用户原话要区分
