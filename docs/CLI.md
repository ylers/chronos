# chronos 命令行使用说明

`chronos_cli.py` 允许在不启动 GUI 的情况下查看、添加、复制和删除 Item/Form。CLI 调用与 GUI 相同的 `Database` 数据层，因此会自动维护 fix feature 镜像列、scope 约束、Form 归属和级联关系。

## 1. 基本格式与数据库选择

在项目目录运行：

```bash
cd /home/paschen/aaa_daily/proj/chronos
uv run python chronos_cli.py [全局选项] <命令>
```

| 形式 | 数据库 | 用途 |
|---|---|---|
| 不加选项 | `data/chronos.db` | 真实使用数据 |
| `--dev` | `data/chronos-dev.db` | 开发/演示数据 |
| `--db PATH` | 指定路径 | 临时库、测试库或备份库 |

全局选项必须放在 `item`、`form`、`info` 前面：

```bash
# 正确
uv run python chronos_cli.py --dev item list

# 错误
uv run python chronos_cli.py item list --dev
```

查看帮助：

```bash
uv run python chronos_cli.py --help
uv run python chronos_cli.py item --help
uv run python chronos_cli.py item add --help
uv run python chronos_cli.py form --help
```

## 2. 查看数据库信息

```bash
uv run python chronos_cli.py info
uv run python chronos_cli.py --dev info
uv run python chronos_cli.py info --json
```

输出当前数据库绝对路径、Item 数和 Form 数。执行删除前建议先运行 `info`，确认没有误操作开发库或使用库。

## 3. Item 命令

### 3.1 列出 Item

```bash
uv run python chronos_cli.py item list
uv run python chronos_cli.py item list --category instant
uv run python chronos_cli.py item list --category 3 --state done
uv run python chronos_cli.py item list --search server
uv run python chronos_cli.py item list --form 21
uv run python chronos_cli.py item list --limit 10
uv run python chronos_cli.py item list --json
```

| 参数 | 说明 |
|---|---|
| `--category VALUE` | 类别编号或英文别名 |
| `--state VALUE` | 状态编号或英文别名 |
| `--search TEXT` | 在名称和描述中搜索 |
| `--form ID` | 只看指定 Form 的 Item，按 Form position 输出 |
| `--limit N` | 最多输出 N 条 |
| `--json` | 输出完整 JSON，适合脚本或 Codex 读取 |

### 3.2 查看单个 Item

```bash
uv run python chronos_cli.py item show 72
uv run python chronos_cli.py item show 72 --json
```

输出名称、描述、category、priority、importance、state、编码后的 fix feature、extendable JSON、时间戳及所属 Forms。

### 3.3 添加 Item

```bash
# 默认：即时任务，priority=3，importance=3，state=未开始
uv run python chronos_cli.py item add "回复邮件"

# 指定全部固定字段
uv run python chronos_cli.py item add "部署服务器" \
  --description "部署测试环境" \
  --category instant \
  --priority 7 \
  --importance 6 \
  --state planned

# 创建后直接加入 Form #21
uv run python chronos_cli.py item add "检查 API" \
  --category instant --priority 6 --importance 5 --form 21
```

类别支持数字或别名：

| 数值 | 别名 | 含义 / scope |
|---:|---|---|
| 0 | `undefined`、`uncategorized` | 未分类 / quick |
| 1 | `long`、`long-term` | 长期 / planner |
| 2 | `short`、`short-term` | 短期 / planner |
| 3 | `instant`、`quick` | 即时 / quick |
| 4 | `idea` | 灵感 / quick |
| 5 | `experiment` | 实验 / 不属于 Form |

状态支持数字或别名：

| 数值 | 别名 | 含义 |
|---:|---|---|
| 0 | `not-started`、`todo` | 未开始 |
| 1 | `planned` | 准备做 |
| 2 | `blocked` | 遇障碍 |
| 3 | `done` | 已完成 |

`priority` 和 `importance` 必须是 0–7。使用 `--form` 时，CLI 会在创建前校验 scope。例如长期任务不能加入 quick Form；校验失败不会留下半成品 Item。

### 3.4 复制 Item

```bash
uv run python chronos_cli.py item copy 72
uv run python chronos_cli.py item copy 72 --name "server backup"
uv run python chronos_cli.py item copy 72 --json
```

不指定名称时自动添加“（副本）”。副本保留 description、fix feature、extendable JSON 和兼容 Form 归属，并插在原条目后面。

### 3.5 删除 Item

```bash
# 交互式确认
uv run python chronos_cli.py item delete 72

# 自动化/skill 使用：显式跳过确认
uv run python chronos_cli.py item delete 72 --yes
```

删除 Item 会同时删除它的所有 `form_items` 关联。删除默认需要确认；非交互环境必须显式传 `--yes`。

## 4. Form 命令

### 4.1 列出 Form

```bash
uv run python chronos_cli.py form list
uv run python chronos_cli.py form list --scope quick
uv run python chronos_cli.py form list --scope planner --json
```

### 4.2 查看 Form 及其 Item

```bash
uv run python chronos_cli.py form show 21
uv run python chronos_cli.py form show 21 --json
```

Item 按 `form_items.position` 输出，因此这里看到的顺序与 GUI 表单顺序一致。

### 4.3 添加 Form

```bash
uv run python chronos_cli.py form add "今日任务" --scope quick
uv run python chronos_cli.py form add "年度计划" \
  --scope planner --description "2026 年目标"
```

Form scope 只能是 `quick` 或 `planner`，默认是 `quick`。

### 4.4 将已有 Item 加入/移出 Form

```bash
uv run python chronos_cli.py form add-item 21 72
uv run python chronos_cli.py form remove-item 21 72
```

参数顺序是 `FORM_ID ITEM_ID`。`add-item` 会校验 scope；`remove-item` 只删除关联，不删除 Item。

### 4.5 在同类型 Form 之间转移 Item

```bash
uv run python chronos_cli.py form move-item SOURCE_FORM_ID TARGET_FORM_ID ITEM_ID
```

例如把 Item #72 从 quick Form #21 转移到 quick Form #24：

```bash
uv run python chronos_cli.py form move-item 21 24 72
```

这是一个原子操作：只有在来源 Form、目标 Form、Item 和来源关联全部有效，并且两个 Form 的 scope 相同时才执行。成功后 Item 从来源移除并追加到目标末尾；失败时两边都不会改变。禁止 planner ↔ quick 跨类型转移。

### 4.6 删除 Form

```bash
uv run python chronos_cli.py form delete 21
uv run python chronos_cli.py form delete 21 --yes
```

删除 Form 会删除该 Form 的关联和顺序，但其中 Item 会保留，可以继续在 All Items 中查看。

## 5. JSON 输出与自动化

支持 `--json` 的命令：`info`、`item list/show/add/copy`、`form list/show/add`。

```bash
uv run python chronos_cli.py --dev item list --state blocked --json
```

自动化建议：

1. 先运行 `info --json` 确认数据库路径。
2. 查看操作优先使用 `--json`。
3. 删除前先 `show`，确认 ID 和名称。
4. 只有用户明确要求删除时才使用 `--yes`。
5. 不要直接编辑 SQLite 镜像列；始终调用 CLI 或 `Database` API。

## 6. 常见错误

### “Item #N 不存在”

使用 `info` 检查当前数据库。开发库与使用库的 ID 相互独立。

### “类别不属于 quick/planner 表单”

- 长期/短期只能加入 planner Form；
- 未分类/即时/灵感只能加入 quick Form；
- 实验不能加入 Form。

### 非交互删除失败

自动化环境无法询问确认，必须显式添加 `--yes`。这是安全保护，不应默认省略。
