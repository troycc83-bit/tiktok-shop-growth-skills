# 来源清单与交叉验证规则

> 零成本数据源地图。按"能不能自动拿"分级，优先自动，受阻就降级，绝不编造。

## 数据源清单（总览）

| 来源 | 自动程度 | 拿什么 | 工具 |
|------|---------|--------|------|
| Google 搜索 / Trends | ✅ 直接联网搜 | 需求趋势、用户提问、评测 | WebSearch |
| **Reddit 评论** | ✅ 内置脚本（免 key） | 真实用户原话、痛点、差评 | `fetch_reddit_comments.py` |
| **TikTok 视频/评论/字幕** | ✅ 内置本地服务（免 key） | 视频数据、评论区、台词 | `fetch_tiktok.py` |
| **Amazon 搜索/评论聚合** | ✅ 内置本地服务（免 key） | ASIN、价格带、评分、褒贬方面 | `fetch_amazon.py` |
| YouTube / 评测媒体 | ✅ 联网搜 | 深度测评、pros/cons | WebSearch |
| 浏览器实测 | ⚠️ 可能遇反爬 | 补充以上拿不到的 | 浏览器工具 |

---

## ✅ Reddit 真实评论 —— 内置脚本（推荐）

**问题**：Reddit 官方 JSON 端点已加登录墙，网页有人机验证（"Prove your humanity"），直连返回 403；搜索引擎只能拿被索引的摘要，抓不到真实评论区。

**方案**：PullPush 公开归档 API（`https://api.pullpush.io/reddit/search/comment/`），免 key、免登录、免浏览器，按关键词搜评论，返回 body/score/subreddit/author/时间/permalink。

**工具**：`scripts/fetch_reddit_comments.py`（仅标准库）
```bash
python3 scripts/fetch_reddit_comments.py -q "UGREEN ClipBuds" -s 50 --out comments.json
python3 scripts/fetch_reddit_comments.py -q "open ear earbuds noise cancelling" -s 50 --min-score 2
python3 scripts/fetch_reddit_comments.py -q "noise cancelling earbuds" --type submission -s 30
```

**关键词策略**：
- 新品型号评论少（如刚上市的 ClipBuds Pro 2 精确词无结果）→ 用宽词：品牌名+品类词、痛点词组合
- 中文/非英语市场评论也存在（菲律宾、印度等 subreddit），按需过滤
- 按 score 排序脚本已内置，高赞评论=社区共识，优先看

**局限**：非实时归档（延迟数小时到数天）；免费端点有速率限制，别高频猛抓；数据非官方，标注来源。

**若本机直连被拦**：脚本会打印 `source_url`，改用网页抓取工具访问同一 URL，从返回 JSON 提取评论。

**备查（本环境不实用）**：
- `reddrix`（github.com/Coding-Doctor-Omar/reddrix，MIT，157★）：功能强但初始化强制下载 1.3GB Camoufox 内核，低网速不可用。
- `yars`（github.com/datavorous/yars）：宣称免 API key，未实测。

---

## ✅ TikTok 视频/评论/字幕 —— 内置本地服务（推荐）

**问题**：TikTok 网页有人机验证，评论接口需 `msToken` + 动态签名（X-Bogus/A_Bogus），由 TikTok 自有混淆 JS 生成且定期更换，浏览器/WebFetch 抓不到。

**关于 Scrapy**：Scrapy 只是通用 HTTP 抓取框架，发的裸请求没有签名，直接 403/空数据。要用 Scrapy 爬 TikTok，必须外挂 Playwright 执行签名 JS 或集成逆向签名库，维护成本极高，**不建议**。真正解决问题的是封装了签名+浏览器方案的项目。

**方案**：`omkarcloud/tiktok-scraper`（MIT，2026 活跃），本地起 HTTP 服务，免费、无 API key、无账号。项目已内置在 `scripts/tiktok-scraper/`。

**工具**：`scripts/fetch_tiktok.py`
```bash
# 一次性装依赖
pip3 install bottle cheroot curl_cffi marshmallow

# 启动服务（持续的终端/后台任务，默认 8000 端口）
python3 scripts/fetch_tiktok.py --serve

# 抓视频评论（链接或 ID）
python3 scripts/fetch_tiktok.py --comments "https://www.tiktok.com/@xxx/video/7692114317151423775" --out comments.json

# 抓字幕/台词（做视频拆解时可替代 Whisper）
python3 scripts/fetch_tiktok.py --transcript 7692114317151423775 --out transcript.json

# 抓视频详情（播放/点赞/评论/分享数、描述、话题）
python3 scripts/fetch_tiktok.py --details 7692114317151423775

# 关键词搜索（对出口 IP 敏感，可能被挡）
python3 scripts/fetch_tiktok.py --search "open ear earbuds" --country US
```

**实测（2026-11-18）**：
- ✅ `/videos/details`、`/videos/comments`（实测 49 条）、`/videos/transcript` 可用
- ⚠️ `/search/videos` 在当前出口 IP 返回 502 blocked（区域限制），换美国住宅 IP 可解
- 字幕接口输出带时间戳的台词，可直接喂给视频拆解 Skill

---

## ✅ Amazon 搜索/评论聚合 —— 内置本地服务（推荐）

**问题**：Amazon 有 AWS WAF + 登录墙，浏览器/WebFetch 抓不到评论；逐条评论文本匿名访问基本拿不到。

**方案**：`omkarcloud/amazon-scraper`（MIT，258★，2026 活跃），同 TikTok 作者的架构，本地 HTTP 服务，免费、无 API key、无账号。项目已内置在 `scripts/amazon-scraper/`。

**工具**：`scripts/fetch_amazon.py`
```bash
# 一次性装依赖
pip3 install bottle cheroot curl_cffi beautifulsoup4 lxml marshmallow

# 启动服务（默认 8001 端口，避开 TikTok 的 8000）
python3 scripts/fetch_amazon.py --serve

# 关键词搜索：找竞品 ASIN / 价格带 / 评分 / 评论数（快，1-2s）
python3 scripts/fetch_amazon.py --search "open ear earbuds" --out search.json

# 评论聚合：AI 摘要 + 评分分布 + 褒贬方面（慢，30s+ 过 WAF）
python3 scripts/fetch_amazon.py --reviews B0D2XRXNGY --out reviews.json

# 商品详情 / Best Sellers 榜单
python3 scripts/fetch_amazon.py --details B0D2XRXNGY
python3 scripts/fetch_amazon.py --bestsellers electronics
```

**实测（2026-11-18）**：
- ✅ `/search` 快且稳，搜 "open ear earbuds" 拿到 16 个真实 ASIN（Anker/TOZO/JLab 等）含评分与评论数
- ✅ `/products/reviews` 能拿 `customers_say`：AI 摘要 + 各方面 sentiment（positive/negative/mixed）+ 提及次数 + 评分直方图 → **negative/mixed 方面就是差评机会点**
- ⚠️ 逐条评论文本匿名访问拿不到（`reviews=[]`，`is_partial=True`），完整分页需登录。逐条原话改用 Reddit/TikTok 或用户贴文本
- ⚠️ 连续快速请求会触发 Amazon WAF **间歇性 404**（`no product page`），稍等 8–30 秒重试即恢复；wrapper 已内置 2 次自动重试。实测真实耳机 ASIN（Soundcore V20i，20,519 条评分）单独请求成功拿到完整聚合数据，工具对耳机类目可用

---

## 失败处理原则

- 任何来源抓取失败，**如实标注"数据未获取"**，不用想象的数字或评论填充。
- 只基于成功获取的信息下判断，并在结论里说明数据覆盖范围。
- 遇到抓取受阻，区分两类并如实说明：
  - **TikTok search 502** = 出口 IP 区域限制，短期无解 → 改用已知视频链接走 details/comments
  - **Amazon 404 `no product page`** = WAF 间歇限流 → 脚本已自动重试 2 次；仍失败就稍等再试，或降级用搜索接口拿评分/评论数
  - 任何来源都拿不到逐条原话时，改用 Reddit / TikTok 评论，或请用户贴文本，Skill 只负责分析和结构化
- 两个本地服务需分别在持续运行的终端/后台任务中启动；端口 8000（TikTok）/ 8001（Amazon）不冲突。

---

## 交叉验证规则

| 信号组合 | 判断 | 建议 |
|---------|------|------|
| TikTok 热 + Google 升 + Amazon 有量 | 真品类机会 | 值得投入，进入内容/选品 |
| TikTok 热 + Google/Amazon 静 | 疑似闪 trend | 谨慎，小批量测试或放弃 |
| 多平台有量 + 差评集中 | 明确差异化机会 | 做"解决差评痛点"的产品与内容 |
| 多平台都静 | 需求不足 | 放弃 |
| 仅 Amazon 有量，TikTok 静 | 传统品类，内容机会待验证 | 用内容测试 TikTok 接受度 |

## 数据可信度标注

- **平台一手数据**（Seller Center 导出、前台可见评论）：高
- **平台 AI 聚合**（Amazon customers_say）：中高，是官方对真实评论的聚合，但非逐条原话
- **公开行业报道**（如"据 Kalodata 报道 GMV 145 万美元"）：中，仅作方向参考，必须标注来源
- **推测/判断**：明确标为判断，附依据
