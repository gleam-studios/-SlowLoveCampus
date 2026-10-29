# API Key 存入与读取

使用 RunningHub 账户的 API Key（不是 MiniMax Key）。API Key 只存本机私有配置或运行环境，不随 Skill 分发。默认配置为 `~/.config/rh-minimax-h3/.env`；默认配置目录权限 0700、文件 0600。

读取顺序：非空 `RUNNINGHUB_API_KEY` → `RUNNINGHUB_ENV_FILE` 指定文件（若设置）或默认私有文件。指定文件缺 Key 时不再自动尝试其他项目；环境变量可覆盖旧配置，诊断时用 `status` 看来源。

```bash
SKILL_DIR="$HOME/.agents/skills/video/ai/rh-minimax-h3"
# 第一次隐藏输入 Key。不要把真实 Key 放在命令参数或 shell 历史。
python3 "$SKILL_DIR/scripts/credentials.py" set
# 或从用户已授权的项目配置导入，仅提取 RUNNINGHUB_API_KEY。
python3 "$SKILL_DIR/scripts/credentials.py" import-env --from-env /绝对路径/agent/.env
python3 "$SKILL_DIR/scripts/credentials.py" status
# 用户要求换 Key 时隐藏输入并替换。
python3 "$SKILL_DIR/scripts/credentials.py" set --replace
```

也可保存至用户指定文件（`--env-file`）并设置 `RUNNINGHUB_ENV_FILE` 指向该处。配置脚本仅写入 Key，不保存其他配置；不要以 `--replace` 覆盖包含其他业务配置的 `.env`，除非用户明确要替换整份文件。

在已有 oTATo 项目中，可以直接使用已授权的项目配置而不导入：

```bash
export RUNNINGHUB_ENV_FILE='/Users/griffith/Desktop/土豆/@土豆老板oTATo/agent/.env'
python3 "$SKILL_DIR/scripts/credentials.py" status
```

脚本只解析 `RUNNINGHUB_API_KEY=...`（可带引号或 `export`），不支持变量插值；不会 source 或执行配置。状态输出隐藏整个 Key，既不显示片段也不输出哈希。文件保存成功不代表账号验证通过；实际授权调用才检验服务认证和额度。
