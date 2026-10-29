# 来源记录

- skill: `slowlove-campus-30s`；显示名称：`@SlowLoveCampus-30s`
- kind: 用户项目的封装与整合
- version: `1.2.0-30s`
- recorded_at: `2026-10-29`
- source: 用户的 SlowLoveCampus 项目，仓库 https://github.com/gleam-studios/-SlowLoveCampus ，以及本包 1.0.0 导出版本；文件指纹见 MANIFEST.json。
- author: 用户项目与 Agent 辅助封装；提示词子 Skill 的来源保留在其 SOURCE.md。
- license: 未为整个集合新设统一许可；不改变素材、总纲或子 Skill 的权利归属，multi-shot-prompt 未声明独立许可证。

当前包只包含两步提示词创作入口、标准库工作目录辅助脚本、完整 multi-shot-prompt、创作总纲、7 张场景图、2 张角色图及 2 段角色音频。总纲已适配为输出提示词即结束。

按用户要求移除原 1.0.0 的 RH-minimax-H3 子 Skill、提交／下载／凭据脚本、视频生成测试、requests 依赖及生成参数；不打包密钥、前端、Codex 模型参数、历史任务和成片。multi-shot-prompt 的通用资源原样保留，但本包入口只允许编写和检查提示词，不调用其下游执行流程。

开发源目录由 my-skills 管理；桌面文件夹和 .skill 是本次导出版本，不是共享库安装副本。没有修改原 SlowLoveCampus 项目或本机共享技能库。未执行真实模型创作对比或视频生成。

本版本由 1.1.0 提示词版独立复制，另设 30s 标识避免与原版安装冲突。1.2.0-30s 在总纲与入口中补充 30 秒的情节发展、双向回应、多镜头用途、简短对白和连续性要求；允许更丰富的关联小情节，不强制固定段落、镜头数或反转。素材、子 Skill 和辅助脚本保持不变，仍在交付提示词后结束。
