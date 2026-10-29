# 独立提示词 Skill

这里保存三份完整原文件目录，与项目的前端、Codex CLI、视频生成流程及运行数据隔离。使用各自目录内的总纲、素材和子 Skill；各版本都在输出完整视频提示词后结束，不调用视频生成服务。

| 版本 | 入口 | 内容 |
| --- | --- | --- |
| 15 秒 | [@SlowLoveCampus-skill-15s/SKILL.md](@SlowLoveCampus-skill-15s/SKILL.md) | 15 秒提示词版 v1.1.0 |
| 20 秒 | [@SlowLoveCampus-skill-20s/SKILL.md](@SlowLoveCampus-skill-20s/SKILL.md) | 独立20秒内容版 v1.0.0-20s，以紧凑互动事件链组织接招、自然变化与落点 |
| 30 秒 | [@SlowLoveCampus-skill-30s/SKILL.md](@SlowLoveCampus-skill-30s/SKILL.md) | 30 秒内容版 v1.2.0-30s，允许更多关联情节、动作、镜头与对白 |

完整克隆仓库或下载对应目录，保留其中全部文件。仅下载 SKILL.md 不包含运行所需的素材和子 Skill。

交给支持文件读写、看图及 Python 的 Agent，发送以下任一指令：

```text
读取 skill-packages/@SlowLoveCampus-skill-15s/SKILL.md，使用同目录内的资源，先展示一次15秒一句话剧情，等待用户确认后再写完整视频提示词，输出提示词后结束。
```

```text
读取 skill-packages/@SlowLoveCampus-skill-20s/SKILL.md，使用同目录内的资源，先展示一次20秒一句话剧情，等待用户确认后再写完整视频提示词，输出提示词后结束。
```

```text
读取 skill-packages/@SlowLoveCampus-skill-30s/SKILL.md，使用同目录内的资源，先展示一次30秒一句话剧情，等待用户确认后再写完整视频提示词，输出提示词后结束。
```

无需前端、Codex CLI 或视频平台凭据。每份目录的使用方法、来源及验证范围见各自说明；MANIFEST.json 和 ASSETS.json 可核对原文件与素材指纹。运行产物留在各 Skill 的 runs/（已由各自 .gitignore 排除）。
