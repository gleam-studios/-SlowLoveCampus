# SlowLoveCampus 工作流使用说明

## 方式一：本地运行，MiniMax 自动生成视频

**运行条件：** 电脑已安装 Codex，并拥有 RunningHub API Key。

**操作步骤：**

1. 打开 Codex，发送以下内容：

   ```text
   拉取 https://github.com/gleam-studios/-SlowLoveCampus.git 到 /Users/griffith/Desktop/AI/拉取的项目，并启动项目、打开运行界面。
   ```

2. 在打开的界面中填写并保存 RunningHub API Key。
3. 点击「一键运行」，自动执行视频制作流程。

**注意：最多同时生成 3 条视频。**

## 方式二：通过 Skill 写提示词，手动生成视频

以下 Skill 安装命令三选一，给 GPT 发送：

```text
用（粘贴下方的 Skill 安装命令）这个 Skill 写提示词。
```

### 15 秒版

```bash
npx skills add https://github.com/gleam-studios/-SlowLoveCampus/tree/main/skill-packages/@SlowLoveCampus-skill-15s --skill slowlove-campus -g -y
```

### 20 秒版

```bash
npx skills add https://github.com/gleam-studios/-SlowLoveCampus/tree/main/skill-packages/@SlowLoveCampus-skill-20s --skill slowlove-campus-20s -g -y
```

### 30 秒版

```bash
npx skills add https://github.com/gleam-studios/-SlowLoveCampus/tree/main/skill-packages/@SlowLoveCampus-skill-30s --skill slowlove-campus-30s -g -y
```

Skill 输出完整提示词后结束，使用提示词手动生成视频。
