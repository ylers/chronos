# chronos 开发文档

给要改动、扩展 chronos 的人看:架构、数据模型、i18n、如何加面板 / 字段 / 设置项、如何测试。

---

## 1. 项目概览

```
chronos/
  run.py                       # 启动入口: CLI 参数解析 + 数据库选择 + smoke
  pyproject.toml               # 依赖 + 清华镜像 index(uv)
  chronos_app/
    model/
      fields.py                # Category / State / Scope 枚举 + FixFeature 位域编解码
      item.py                  # Item 数据类 + extendable 模板 / 访问器
      store.py                 # Database: SQLite CRUD、镜像列同步、表单、设置
    ui/
      theme.py                 # 从设置推导调色板并生成 QSS
      main_window.py           # QMainWindow: 侧栏 + QStackedWidget,持有全部面板
      sidebar.py               # 竖排图标栏(SECTIONS 常量)
      planner_panel.py         # 🗒 计划表
      quick_panel.py           # ⚡ 及时行动(含快加 DSL 解析)
      experiment_panel.py      # 🧪 实验管理
      reference_panel.py       # 📖 参考
      all_items_panel.py       # 🗂 全部条目
      settings_panel.py        # ⚙ 设置
    widgets/
      helpers.py               # 复用组件: 表格/对话框/确认框/小按钮等
    i18n.py                    # 轻量 i18n: tr() + 中文文案表
  tests/                       # stdlib unittest
  data/                        # 运行期自动生成(SQLite),含使用库/开发库
  docs/                        # 本文档 + 使用说明
```

分层规则:**ui 依赖 model;model 不依赖 ui**。`model/` 内可单测,无需 Qt。`i18n.tr()` 在 `model/fields.py` 里以懒 import 方式使用(仅渲染 label 时),避免 model 层反向依赖 ui。

---

## 2. 环境与工具链

- **uv**:位于 `~/.local/bin/uv`(已加入 PATH)。所有命令都用 `uv run …`,不进系统 Python。
- **镜像**:`pyproject.toml` 里把清华源 `https://pypi.tuna.tsinghua.edu.cn/simple` 设为默认 index,本机无法直连 pypi.org。新增依赖要装得进去必须走该镜像。
- **Python ≥ 3.11**,唯一运行依赖 `PySide6>=6.8`(本机为 6.11.1)。
- 系统**无 pip / sudo**;想装系统级工具走 uv 的 tool 机制(`uv tool install …`)。

```bash
cd /home/paschen/aaa_daily/proj/chronos
uv sync                       # 首次或依赖变更后同步 .venv
uv run python run.py --dev    # 开发模式(开发库)
uv run python run.py --demo   # 重置开发库并写入演示数据
uv run python -m unittest discover tests   # 单元测试
uv run python run.py --smoke  # 无头截图 + 结构校验(自动退出)
```

---

## 3. 数据模型

### 3.1 fix feature:16 位位域

GUI / 操作 / 属性等「定长」信息用**一个 16 位整数**紧凑编码:

```
编码 = state<<14 | importance<<11 | priority<<8 | category

bits  0-7    category   类别    (8 bits: 0未分类 1长期 2短期 3即时 4灵感 5实验)
bits  8-10   priority   优先级  (3 bits: 0-7)
bits 11-13   importance 重要度  (3 bits: 0-7)
bits 14-15   state      状态    (2 bits: 0未开始 1准备做 2遇障碍 3已完成)
```

- **bits 16-31 预留**为扩展字(deadline / repeat 等未来固定字段)。`FixFeature.encode()` 只写低 16 位,`decode()` 只读低 16 位——高位可安全扩展而不破坏旧数据。
- `FixFeature` 是 **frozen dataclass**,用 `fix.with_(state=State.DONE)` 返回改过某个字段的新实例,不原地改。

### 3.2 SQLite schema

```sql
items(id, name, parent_id, description, fix_feature, category, priority, importance, state,
      extendable JSON TEXT, created_at, updated_at, completed_at)
forms(id, name, description, scope, created_at)               -- scope: 'planner' | 'quick'
form_items(form_id, item_id, position, PK(form_id, item_id)) -- 表单↔条目 多对多, ON DELETE CASCADE
settings(key PRIMARY KEY, value TEXT)                         -- 值以 JSON 文本存储
```

关键约定:

- **`items.fix_feature` 是规范表示**,`category/priority/importance/state` 是**镜像列**,由 `store.py` 的 `_pack()` 单点写入保持同步:紧凑编码 + 可索引查询两全。读数据一律用 `FixFeature.decode(fix_feature)`,不要把镜像列当权威。
- **`items.parent_id` 是指向 `items.id` 的自关联**：NULL 表示根 Item。`set_parent()` 是唯一推荐写入口，负责验证目标存在、拒绝自引用并沿祖先链阻止循环；`children()` 返回直接子项。删除父项时先将直接子项的 `parent_id` 清空，绝不级联删除任务。
- **`items.completed_at`** 在状态从非完成切换为 `DONE` 时写入当前时间。取消完成只改状态、保留该字段；以后再次完成会以新时间覆盖。直接编辑一个已经完成的 Item 不会无故改写完成时间。
- **extendable** 存 JSON 文本;`Item.extendable_get(key, default)` 安全读取。
- **外键**在连接时用 `PRAGMA foreign_keys = ON` 开启,删表单 / 删条目会级联清 `form_items`。
- **迁移**:`Database._migrate()` 在初始化时对旧库做幂等 `ALTER TABLE`(当前只补过 `forms.scope`)。加新列走这里。

### 3.3 scope 模型(面板互斥)

`fields.py` 定义了两个**互斥的归属域**:

```python
Scope.PLANNER = "planner"  # 长期 + 短期
Scope.QUICK   = "quick"    # 即时 + 灵感 + 未分类
PLANNER_CATEGORIES = {LONG_TERM, SHORT_TERM}
QUICK_CATEGORIES   = {UNDEFINED, INSTANT, IDEA}
scope_of_category(category) -> Scope | None   # 实验等返回 None(不属于任何表单面板)
```

互斥在**两层**同时执行:

1. **存储层(权威)**:
   - `add_to_form(form_id, item_id)`:若 `scope_of_category(item.category) != form.scope` 直接返回 `False`,不入库。
   - `update_item(...)`:改类目后调用 `_reconcile_form_membership(item_id)`,把条目从 scope 不匹配的表单自动移出。
2. **UI 层(体验)**:各面板用 `db.query(category_in=…)` / `list_forms(scope=…)` 限定自己 scope 的类目与表单;`ItemDialog` 传入 `categories=` 只露出本面板允许的类目。

> 经验教训:scope 校验必须落在**存储层**,UI 过滤只是体验。只靠 UI 隐藏类目,API 调用者绕过去就会破坏不变式(已有回归测试覆盖)。

---

## 4. 存储层 API(`chronos_app.model.store.Database`)

```python
# 条目
create_item(name, description="", fix=None, extendable=None) -> Item
get_item(item_id) -> Item | None
update_item(item_id, *, name=None, description=None, fix=None, extendable=None) -> Item | None
set_state(item_id, state) -> Item | None
delete_item(item_id) -> bool
duplicate_item(item_id, *, name=None) -> Item | None

# 查询(全部可选,可叠加)
query(*, category=None, category_in=None, state=None, state_not=None,
      keyword=None, form_id=None, order="updated_at DESC, id DESC", limit=None) -> list[Item]

# 表单
create_form(name, description="", scope="planner") -> Form
delete_form(form_id) -> bool
list_forms(scope=None) -> list[Form]      # scope 过滤可省略
get_form(form_id) -> Form | None
add_to_form(form_id, item_id) -> bool     # scope 不匹配返回 False
remove_from_form(form_id, item_id) -> None
transfer_item(item_id, source_form_id, target_form_id) -> bool
form_items(form_id) -> list[Item]         # 按 position 排序
set_form_order(form_id, ordered_item_ids) -> None

# 设置 / 统计 / 清理
get_setting(key, default=None); set_setting(key, value)
counts() -> dict[state, int]              # 按状态统计
clear_all()                               # 清空条目/表单,保留 settings(供 --demo 幂等)
```

`duplicate_item()` 复制 description、fix feature、extendable JSON 和全部兼容表单归属。对每个所属表单,副本插在原条目之后,原位置之后的条目顺延。UI 负责传入本地化副本名称(`tr("{name} (Copy)")`)。

`query()` 的 `form_id` 走 `_query_form_sql()`:JOIN `form_items` 后按 `fi.position` 排序。注意其参数绑定是**把 `form_id` 放在最前、其余 params 扁平追加**——一个子句可以展开成多个占位符(如 `category IN (?,?,?)`),不能把参数和 where 子句做 zip 对齐(曾有回归 bug,测试 `test_query_form_with_multi_param_filter` 保护)。

`transfer_item()` 是跨 Form 移动的唯一入口。它在同一事务中校验来源关联、相同 scope 和 Item 类别兼容性，将 Item 追加到目标末尾、从来源移除并压紧来源 position。不要在 UI/CLI 中组合 `add_to_form()` + `remove_from_form()`，否则进程在两步之间失败时会留下双重归属或丢失归属。

### 4.1 CLI 与 skill

项目根目录的 `chronos_cli.py` 是 GUI 之外的受控入口。它必须调用 `Database` API，不能直接修改 fix feature 镜像列。命令说明见 `docs/CLI.md`；对应 Codex skill 安装在 `~/.codex/skills/chronos-manager/`。

维护 CLI 时遵守：

- 默认数据库始终是 `data/chronos.db`，`--dev` 才切换到 `chronos-dev.db`；
- 所有测试显式传 `--db` 指向临时数据库；
- 增加带 ID 的变更命令前先实现查看命令；
- 删除必须默认确认，非交互调用只有显式 `--yes` 才执行；
- scope 校验必须发生在创建 Item 前，失败不能留下半成品；
- 机器消费的查询应提供 `--json`；
- CLI 参数或安全策略变化时同步更新 `docs/CLI.md` 和 `chronos-manager/SKILL.md`，再运行 skill validator。

---

## 5. UI 架构

### 5.1 侧栏与面板注册

面板顺序由 **两处** 决定,必须保持一致:

- [`sidebar.py`](chronos_app/ui/sidebar.py) 的 `SECTIONS`(icon + 名称);
- [`main_window.py`](chronos_app/ui/main_window.py) 的 `self.panels` 列表。

两者按 `QStackedWidget` 的 index 一一对应。**新增面板时两处都要加,且顺序一致**(smoke 测试按 index 断言各面板内容)。

### 5.2 面板间通信

`MainWindow` 提供三个中枢方法,面板通过构造时拿到的 `main` 引用调用:

- `notify_items_changed()`:任一面板改了条目后广播,刷新全部面板(保证类目 / 表单互斥在 UI 上也即时一致)。
- `reapply_theme()`:设置面板改外观后重读设置、重应用 QSS、刷新全部面板。
- `reapply_language()`:切语言后重设全局文案、重设窗口标题、`retranslate()` + `refresh()` 全部面板。

### 5.3 尺寸持久化与自适应行高

`MainWindow._setup_ui_state()` 集中注册需要持久化的 `QTableWidget` 和 `QSplitter`。状态以 JSON 写入当前数据库的 `settings.ui_layout`：

```text
ui_layout = {
  version,
  window_geometry,
  tables: {key: [column_widths...]},
  splitters: {key: [pane_sizes...]},
  navigation: {sidebar_index, planner_form_id, quick_form_id, collapsed_item_ids}
}
```

`navigation` 子对象保存 `sidebar_index`、`planner_form_id` 和 `quick_form_id`。恢复时必须验证页面索引范围和表单 ID 是否仍存在；已删除的 Planner 表单由 `PlannerPanel.refresh()` 回退到第一个表单，Quick 表单则回退到“未归档”。侧栏和两个表单选择器的 change signal 都接入 250ms 防抖保存。

- `resizeEvent()` / `moveEvent()`、`QHeaderView.sectionResized`、`QSplitter.splitterMoved` 触发 250ms 单次定时器；
- `closeEvent()` 停止定时器并立即保存；
- 初始化时先建立控件，再调用 `_restore_ui_state()`；恢复期间用 `_restoring_ui_state` 阻止信号反向覆盖存档；
- 新增可调整表格/分栏时必须加入 `_persistent_tables` / `_persistent_splitters`，key 应稳定且不能依赖翻译文案；
- schema 变化时递增 `version` 并兼容旧字典，不能因缺少某个 key 阻止启动。

公共 `make_table()` 开启 `wordWrap`，纵向 header 使用 `ResizeToContents` 且最小行高 34px；`set_cell()` 强制垂直居中。因此长 name 会换行并增加行高。页面不要再调用固定 `setRowHeight()` 覆盖这一行为。

每个面板都实现两个方法:

- `refresh()`:重读数据并重绘;
- `retranslate()`:把面板内所有文案重新取一遍(标题、按钮、表头、placeholder、过滤下拉)。

条目表格统一使用 `Qt.ContextMenuPolicy.CustomContextMenu`,右键位置先经 `table.indexAt(pos)` 解析并 `selectRow()`,再显示 `QMenu`。Planner 提供复制 / 上移 / 下移 / 删除。Quick Action 仅在选中具体 quick 表单时提供可用的上移 / 下移,因为此时有明确的 `form_items.position`;全局视图中的移动项禁用。Quick 的移动不能直接用可见行号索引完整表单,必须取可见相邻条目的 ID,在完整 `form_items` ID 序列中交换,以兼容状态、类别和关键词过滤。Experiments、All Items 没有持久化手动顺序,只提供复制 / 删除。

Quick Action 的 `按优先级排序` 是一次性持久化重排,对 `db.form_items(form_id)` 的完整结果做稳定排序,键为 `(-priority, -importance)`,然后调用 `set_form_order()`。不要只排序当前过滤后的表格行；否则隐藏条目的 position 会变得不可预测。

Quick Action 下拉中的 `None` 表示“未归档”，不是“全部”。数据层通过 `query(unfiled_scope=Scope.QUICK)` 的 `NOT EXISTS` 子查询排除已经属于 Quick 表单的条目；`item_forms(item_id, Scope.QUICK)` 提供列表归属显示和转移来源。未归档条目使用 `add_to_form()` 归档，已有归属的条目使用 `transfer_item()` 原子转移，`remove_from_form()` 则恢复为未归档。

父子 UI 使用 `hierarchy_rows(items, collapsed_ids)` 将当前查询结果稳定转换为深度优先顺序，折叠节点时跳过其完整后代；`set_hierarchy_name()` 写入 `▼` / `▶` / `↳` 和缩进，并把深度保存在 `UserRole + 1`。只对当前可见集合构树：父项被筛掉时子项提升为当前视图根节点。右键菜单通过 `add_parent_menu()` 提供候选父项及解除操作，通过 `add_collapse_action()` 切换全窗口共享的 `MainWindow.collapsed_item_ids`。该集合保存在 `ui_layout.navigation.collapsed_item_ids`，所以重启后恢复；数据层仍会二次执行循环校验。

### 5.4 i18n

机制在 `chronos_app/i18n.py`:

- **英文为规范键**,`_CATALOG[key]["zh"]` 是翻译;缺失时回退到英文键本身。
- `tr(key, **kwargs)`:取当前语言文案并 `.format(**kwargs)`;`set_language("zh"|"en")` 切换全局。
- 面板内写死文案一律走 `tr(...)`;**不要拼接中文**。新增文案 = 在 `_CATALOG` 加一条 zh。
- 类别 / 状态的中文不在 `_CATALOG`,而是 `fields.py` 里的 `CATEGORY_KEYS` / `STATE_KEYS`(英文规范键)→ `category_label()` / `state_label()` 内部走 `tr()`。

### 5.5 主题

`ui/theme.py`:从设置(背景色 / 强调色 / 深色 / 字号)推导调色板,拼成一段 QSS 应用到 `QApplication`。`DEFAULT_SETTINGS` 是缺省值;设置面板每个控件 change 即写库并触发 `reapply_theme()`。改主题时注意 QSS 里选择器要同时照顾明暗两套(如文字颜色、表格交替行)。

---

## 6. 新增一个面板(逐步指南)

以加一个「📊 统计」面板为例:

1. **建面板类**:复制一个现有面板的结构(推荐参考 `all_items_panel.py`),实现 `__init__(self, db, main)`,内部 `_build_ui()` + `retranslate()` + `refresh()`。构造里持有 `self.db`、`self.main`。
2. **注册侧栏**:`sidebar.py` 的 `SECTIONS` 里按位置插入 `("Statistics", "📊")`。
3. **注册主窗口**:`main_window.py` 的 `panels` 列表在**同一位置**加入 `StatisticsPanel(self.db, self)`。
4. **复用组件**:表格用 `widgets/helpers.make_table/set_cell/set_headers/clear_table`,按钮用 `small_button`,确认框用 `confirm`,弹输入用 `prompt_text`,新建 / 编辑条目用 `ItemDialog`(可传 `categories=` 限制类目)。编辑对话框的优先级和重要度使用 `ScoreSlider`；Planner、Quick Action、All Items 表格使用 `set_score_cell` / `InlineScoreSlider`，值变化后用 `FixFeature.with_()` 生成新位域并立即写库。不要在各面板重复实现评分控件。
5. **i18n**:所有文案走 `tr()`,在 `i18n.py` 补 zh。
6. **smoke**:`run.py` 的 `names` 里加一项,`verify()` 里补结构断言(行数 / 标题语言等),保证无头验证覆盖到它。

---

## 7. 测试与验证

### 7.1 单元测试(stdlib unittest,零额外依赖)

```bash
uv run python -m unittest discover tests
```

- `test_fields.py` — 位域编解码、边界、`with_()`。
- `test_store.py` — CRUD、镜像列同步、查询过滤、表单生命周期、**scope 互斥**(`test_add_to_form_scope_guard` / `test_update_item_reconciles_form`)、**表单查询参数对齐**(`test_query_form_with_multi_param_filter`)、设置读写。
- `test_quick.py` — 快加 DSL 解析(`!优先级 #类别 *重要度`)。
- `test_i18n.py` — `tr()` 回退与格式化。

每个测试用例都指向一条真实业务规则;改存储层 / 解析逻辑后跑全量确认无回归。

### 7.2 smoke(无头验证 + 截图)

```bash
timeout 60 uv run python run.py --smoke
```

用**临时库**启动窗口,自动:

- 依次对 6 个面板截图(中文一轮、English 一轮),存到 `shots/`;
- 断言:侧栏 6 项、各面板数据行数、fix feature 参考表 4 行、设置表 5 行、主题已应用、**scope 隔离**(计划表表单 ∩ 及时行动表单 = ∅,及时行动条目全为 quick 类目)、**语言文案**(侧栏 tooltip、面板标题)、**表单过滤**(选中 quick 表单后列表与 `db.form_items(form_id)` 一致)。

以退出码 0/1 表示通过/失败,可进 CI。**注意**:smoke 必须带 `timeout` 兜底——窗口 crash 后 `app.exec()` 可能挂住。

### 7.3 界面人工验证

在图形环境下 `uv run python run.py --dev --demo`,逐面板手测:侧栏切换、表单增删 / 条目增删排序、快加落表单、实验参数编辑、设置改颜色即时生效、语言切换。

---

## 8. 常见开发任务

### 加一个新的「设置项」

1. `theme.py` 的 `DEFAULT_SETTINGS` 加默认值;
2. `settings_panel.py` 加控件,change 信号里 `db.set_setting(key, value)` + `main.reapply_theme()`(或 `reapply_language()`);
3. 需要 UI 用的值,在 `MainWindow._load_settings()` / `reapply_theme()` 读出来即可;
4. `reference_panel.py` 的设置一览表会按 `_SETTING_ROWS` 渲染,若想让新设置也展示,在那里补一行;
5. 加 i18n 文案。

### 加一个新的「类别」

1. `fields.py` 的 `Category` 加常量;
2. `CATEGORY_KEYS` 加规范键(英文)+ `i18n.py` 加 zh;
3. 决定它的 **scope 归属**(`PLANNER_CATEGORIES` / `QUICK_CATEGORIES`,或都不属于 → 独立面板,如实验);
4. 若要它可入表单,确认对应表单 scope 的校验逻辑覆盖它;
5. `item.py` 的 `default_extendable()` 若需要给它一个参数模板则补一条;
6. 更新 `plan.md` / 文档的取值表,smoke 的结构断言按需调整。

### 用上预留的高 16 位(加 deadline / repeat 等定长字段)

1. 在 `fields.py` 定义掩码与位移(如 `DEADLINE_SHIFT = 16`),在 `FixFeature` 加字段;
2. `encode()` 写入、`decode()` 读出;**保持低 16 位布局不变**,旧数据即可无损升级;
3. `store.py` 无需改(位域整体走 `fix_feature` 列);
4. 需要查询索引的话,参考镜像列模式加一列并在 `_pack()` / `update_item` 同步。

### 迁移旧库

SQLite 里打开旧库确认结构后,在 `store.Database._migrate()` 加幂等 `ALTER TABLE`(先 `PRAGMA table_info` 查列名再补)。**不要**在 schema 里直接加列然后靠 `CREATE TABLE IF NOT EXISTS` 期待旧库自动获得新列——它不会。

---

## 9. 运行参数速查

```
uv run python run.py             # 使用库 data/chronos.db
uv run python run.py --dev       # 开发库 data/chronos-dev.db(标题带 [dev])
uv run python run.py --demo      # 重置开发库 + 写演示数据(幂等,只进开发库)
uv run python run.py --db PATH   # 显式指定库(绕过默认分离)
uv run python run.py --smoke     # 临时库自动截图 + 校验后退出
```

`run.py` 的 `resolve_db()` 是唯一决定库路径的地方:`--smoke` > `--db` > `--dev/--demo` > 默认。`--demo` 永不触碰使用库。
