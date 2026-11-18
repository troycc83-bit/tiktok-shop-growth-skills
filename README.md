# TikTok Shop 增长 Skills

美国 TikTok Shop 耳机类目（单人卖家）的 WorkBuddy Skill 集合。1 个主控 + 4 个能力 Skill，全部按需调用，无固定频率。

## 结构

```
tiktok-shop-growth/      主控：业务记忆、路由、共享知识库
  references/business-profile.md      业务档案（已确认事实）
  assets/                             知识库初始模板
  shared-kb/                          实际运行的共享知识库（会被持续写入）
tiktok-video-remix/      核心：爆款视频拆解 + 仿写 → 英文 hook/分镜/达人 Brief
  scripts/decompress_video.py         视频抽帧 + 音轨转写脚本（降级路径）
  references/                         拆解框架 + 耳机 5 大骨架库
tiktok-market-research/  跨平台调研：Google/Amazon/TikTok/Reddit + 交叉验证 + 差评挖机会
tiktok-sales-plan/       销售计划：双模型拆解 + 三档预测（只给骨架不代填数字）
tiktok-weekly-review/    周报复盘：偏差归因 + 跑赢骨架回流知识库
```

## 安装 / 同步到本地

这些 Skill 安装在用户级目录 `~/.workbuddy/skills/`。要把本仓库内容同步到本地：

```bash
# 把仓库里的 5 个目录复制到 WorkBuddy 用户级 skills 目录
cp -R tiktok-shop-growth tiktok-video-remix tiktok-market-research \
      tiktok-sales-plan tiktok-weekly-review ~/.workbuddy/skills/
```

复制后在 WorkBuddy 新开任务即可调用。修改本地文件后，反向复制回本仓库提交即可版本化管理。

## 调用方式

在 WorkBuddy 里直接说人话触发，不需要记 Skill 名：

| 说法 | 触发 |
|------|------|
| "拆解这条视频""仿写这个爆款" | 视频拆解+仿写 |
| "调研 XX 品类""挖竞品差评" | 跨平台市场调研 |
| "做个销售计划""GMV 目标拆解" | 销售计划 |
| "复盘一下""这个脚本跑赢了" | 周报复盘 |

主控 Skill `tiktok-shop-growth` 记住业务背景、按需路由、维护共享知识库。

## 设计原则

- **按需调用**：不写死任何执行频率，用户说就用
- **只给骨架**：测算类不代填假设数字（客单价外的成本/佣金/预算留空）
- **不编造数据**：抓不到的平台数据标注"未获取"，行业报道标注来源
- **越用越值钱**：调研挖的用户语言 → 仿写素材；复盘跑赢的骨架 → 回流知识库

## 依赖（可选，仅视频降级路径需要）

```bash
pip install imageio-ffmpeg    # ffmpeg
pip install faster-whisper     # 音轨转写
```
