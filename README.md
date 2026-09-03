# chronos

日常事物记录 · 工作流优化 · 实验追踪 —— 一个原生 **PySide6 (Qt6)** 桌面应用,数据存于本地 SQLite,**不使用浏览器**。

![语言](https://img.shields.io/badge/lang-Python%203.11%2B-blue)
![GUI](https://img.shields.io/badge/GUI-PySide6%206-green)

## 文档

- **[使用说明](docs/USAGE.md)** — 安装启动、六个面板、快加语法、开发库/使用库分离、数据备份。
- **[命令行说明](docs/CLI.md)** — 用指令查看、添加、复制、删除 Item/Form，支持 JSON 和开发库隔离。
- **[开发文档](docs/DEVELOPMENT.md)** — 架构、位域编码、SQLite schema、scope 互斥、i18n、新增面板/字段/设置项、测试与验证。

## 功能

| 面板 | 说明 |
|---|---|
| 🗒 **计划表** | 创建多个「表单」(如读书计划、本周安排),把**长期/短期**目标组织成表单,逐项推进、排序、完成 |
| ⚡ **及时行动** | 一句话快加任务,回车即记(**即时/灵感**);可新建/选择 quick 表单,快加直接落入所选表单,**切换表单即过滤列表** |
| 🧪 **实验管理** | 实验列表 + 参数键值表 / 结论 / 运行记录(每次运行留痕) |
| 📖 **参考** | fix feature 位域布局、各字段取值与含义、**面板归属**,**当前设置值一览**(随设置实时刷新) |
| 🗂 **全部条目** | 一处浏览与管理**所有条目**,按状态/类别/关键字过滤,四种排序 |
| ⚙ **设置** | 背景色、强调色、明暗主题、字号、**界面语言(中文 / English)**,改动即时生效 |

**计划表与及时行动互斥**:条目按类目归属单一面板(长期/短期 → 计划表,即时/灵感 → 及时行动),
任一条目不会同时出现在两者;表单按 scope 隔离,互不共享。

任务按时间尺度分三类:长期(月/年)、短期(周/日)、即时(分钟/小时),灵感与实验单独归类。
fix feature(类别/优先级/重要度/状态)编码为一个 16 位整数,extendable 参数为 JSON 键值对。

## 安装与运行

```bash
# 1. 首次: 建 .venv 并安装 PySide6(使用清华镜像,本机无需系统 pip)
uv sync

# 2. 启动(开发与使用分离,各用独立数据库)
uv run python run.py            # 使用库 data/chronos.db(真实数据)
uv run python run.py --dev      # 开发库 data/chronos-dev.db
uv run python run.py --demo     # 重置开发库并写入演示数据后启动(幂等,只进开发库)
uv run python run.py --smoke    # 临时库自动截图六个面板并做结构校验后退出(验证用)
uv run python run.py --db PATH  # 显式指定库,绕过默认分离
```

- **使用库** `data/chronos.db`:日常使用,**不会**被 `--demo` 写入演示数据。
- **开发库** `data/chronos-dev.db`:`--dev` / `--demo` 使用,演示数据只进这里。
- 窗口标题带 `[dev]` 标识区分当前库;设置面板可看到当前库路径。

## 及时行动的快加语法

在及时行动顶部输入框输入,回车即添加:

```
任务名 !优先级 #类别 *重要度
```

- `!7` 优先级(0-7,默认 3)
- `#3` 类别(0未分类 1长期 2短期 3即时 4灵感 5实验,默认即时)
- `*5` 重要度(0-7,默认 3)

例:`打印文件 !7 #3` → 名称「打印文件」,优先级 7,即时任务。

> 只有**即时/灵感/未分类**属于及时行动;写 `#1`/`#2`(计划表类目)或 `#5`(实验)时,
> 条目会按归属创建到对应面板,不在此列表显示(可在全部条目查看)。

## 数据模型

fix feature 16 位编码:`state(2) | importance(3) | priority(3) | category(8)`,
高 16 位预留扩展。SQLite 中 `items.fix_feature` 为规范位域,`category/priority/importance/state`
为镜像列由存储层同步,兼顾紧凑编码与索引查询。`forms.scope`(planner/quick)保证计划表与
及时行动的表单互不共享,条目改类目会自动移出 scope 不匹配的表单。详见 [plan.md](plan.md)。

## 测试

```bash
uv run python -m unittest discover tests
uv run python run.py --smoke
```

## 目录

```
chronos/
  run.py                  入口
  chronos_app/
    model/                位域编码 · 条目 · SQLite 存储
    ui/                   主题 · 主窗口 · 侧栏 · 六面板
    widgets/              复用控件
  tests/                  stdlib unittest
  data/                   运行期自动生成(SQLite)
  shots/                  --smoke 截图输出
```
