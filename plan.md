# chronos

chronos 是一个综合系统:日常事物记录 + 工作流优化 + 实验追踪。
以**原生 PySide6 桌面应用**实现(非浏览器),数据存于本地 SQLite。

## 1. item 结构

```
item: [id] [name] [description] [fix feature] [extendable feature]
```

- **fix feature**: 对应 GUI/操作/属性的「定长」信息,用一个 16 位整数紧凑编码。
- **extendable feature**: 对应日常拓展需求的「变长」参数,以 JSON 字典存储,
  部分参数由 fix feature 派生(如实验类自带 parameters/result/iterations)。

## 2. fix feature 编码 (16 bits)

```
state(2) | importance(3) | priority(3) | category(8)
```

| 位域 | 长度 | 含义 |
|---|---|---|
| bits 0-7 | 8 | category: 0未分类 / 1长期 / 2短期 / 3即时 / 4灵感 / 5实验 |
| bits 8-10 | 3 | priority 优先级 0-7 |
| bits 11-13 | 3 | importance 重要度 0-7 |
| bits 14-15 | 2 | state: 0未开始 / 1准备做 / 2遇障碍 / 3已完成 |

bits 16-31 预留为扩展字(deadline / repeat 等未来固定字段)。
SQLite 中 `items.fix_feature` 为规范表示;`category/priority/importance/state`
为镜像列,由存储层单点写入同步,保证紧凑编码与索引查询两全。

## 3. task model(任务的时间尺度)

| 类别 | 时间尺度 | 例子 |
|---|---|---|
| 1 长期 | 月 / 年 / 无期限 | 学习一门新技能 |
| 2 短期 | 周 / 日 | 完成本周作业、打印某份文件 |
| 3 即时 | 分钟 / 小时 | 读这篇文章、等实验跑完 |

**面板归属(scope,互斥)**: 长期/短期 → 计划表(组织进表单);即时/灵感/未分类 → 及时行动;
实验 → 实验管理。任一条目只属于一个面板,**不会同时出现在计划表与及时行动**;
表单按 scope 隔离,计划表表单与及时行动表单互不共享(存储层 `add_to_form` 校验类目与表单 scope 匹配,改类目自动移出旧表单)。

## 4. GUI 设计(VSCode 式左侧栏)

| icon | 面板 | 能力 |
|---|---|---|
| 🗒 计划表 | planner | 创建/删除表单,向表单添加、编辑、排序、完成/删除条目(仅长期/短期) |
| ⚡ 及时行动 | quick | 单行快加(`!优先级 #类别 *重要度`),可新建/选择 **quick 表单** 并落入;勾选完成、过滤、删除(仅即时/灵感/未分类) |
| 🧪 实验管理 | experiment | 实验列表 + 参数键值表 / 结论 / 运行记录编辑 |
| 📖 参考 | reference | fix feature 字段位域/取值/含义说明 + 面板归属,当前设置值一览(实时刷新) |
| 🗂 全部条目 | all_items | 一处浏览/管理**所有**条目,按状态/类别/关键字过滤,四种排序 |
| ⚙ 设置 | settings | 背景色、强调色、明暗主题、字号、界面语言(中文/English),改动即时生效 |

计划表与及时行动**互斥**:条目按类目归属单一面板,两者表单不共享。

## 5. 存储(SQLite)

```sql
items(id, name, parent_id, description, fix_feature, category, priority, importance, state,
      extendable JSON, created_at, updated_at)
forms(id, name, description, scope, created_at)                 -- scope: planner / quick,表单互不共享
form_items(form_id, item_id, position)                          -- 表单 ↔ 条目 多对多
settings(key, value)                                            -- 主题等设置
```

## 6. 代码结构

```
chronos/
  run.py                      # 入口: [--dev] [--demo] [--smoke] [--db PATH]
  pyproject.toml              # 依赖 + 清华镜像 index(uv)
  chronos_app/
    model/   fields.py        # 位域编解码 + 类别/优先级/状态枚举
             item.py          # Item 数据类 + extendable 模板
             store.py         # Database: CRUD、查询、镜像列同步、表单、设置
    ui/      theme.py         # 从背景色推导调色板并生成 QSS
             main_window.py   # 左侧栏 + QStackedWidget
             sidebar.py       # 竖排图标栏
             planner_panel.py / all_items_panel.py / quick_panel.py / experiment_panel.py / reference_panel.py / settings_panel.py
    widgets/ helpers.py       # 表格/对话框/徽章等复用组件
  tests/                      # stdlib unittest
```

## 7. 运行(开发与使用分离,独立数据库)

```bash
uv sync                     # 首次: 建 .venv 并装 PySide6(清华源)
uv run python run.py        # 使用库 data/chronos.db(真实数据)
uv run python run.py --dev  # 开发库 data/chronos-dev.db
uv run python run.py --demo # 重置开发库并写入演示数据(只进开发库)
uv run python run.py --smoke# 临时库自动截图六个面板并做结构校验后退出
uv run python --db PATH     # 显式指定库
uv run python -m unittest discover tests
```

`--demo` 永不写入使用库;窗口标题带 `[dev]` 标识当前开发库。
