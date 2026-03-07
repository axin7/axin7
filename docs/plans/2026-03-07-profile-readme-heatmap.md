# Profile README Heatmap Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构 GitHub Profile README，并通过 GitHub GraphQL + GitHub Actions 每天自动生成真实贡献热力图 SVG。

**Architecture:** 使用一个 Python 脚本通过 GraphQL 拉取 `contributionsCollection`，将数据转换为静态 SVG 产物写入 `assets/heatmap.svg`；`README.md` 仅做静态引用，`.github/workflows/update-heatmap.yml` 负责定时更新与安全提交。实现过程遵循 KISS、YAGNI 与 TDD，优先使用 Python 标准库，避免引入不必要依赖。

**Tech Stack:** GitHub Actions、GitHub GraphQL API、Python 3 标准库、SVG、Markdown

---

### Task 1: 建立贡献数据解析测试与样例负载

**Files:**
- Create: `tests/fixtures/github_contributions_response.json`
- Create: `tests/test_generate_github_heatmap.py`
- Create: `scripts/generate_github_heatmap.py`

**Step 1: Write the failing test**

在 `tests/test_generate_github_heatmap.py` 中写一个最小失败用例，验证脚本能把 GraphQL 返回中的 `weeks[].contributionDays[]` 解析为扁平天数据，至少断言：

```python
calendar = load_calendar_from_fixture("tests/fixtures/github_contributions_response.json")
days = normalize_days(calendar)
assert len(days) == 14
assert days[0]["date"] == "2026-01-01"
assert days[0]["count"] == 3
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests/test_generate_github_heatmap.py -v`

Expected: FAIL，提示 `load_calendar_from_fixture` 或 `normalize_days` 未定义。

**Step 3: Write minimal implementation**

在 `scripts/generate_github_heatmap.py` 中加入最小实现：
- `load_calendar_from_fixture(path)`
- `normalize_days(calendar)`
- 使用标准库 `json` 读取样例文件

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests/test_generate_github_heatmap.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/fixtures/github_contributions_response.json tests/test_generate_github_heatmap.py scripts/generate_github_heatmap.py
git commit -m "test: add contribution calendar parsing coverage"
```

### Task 2: 建立 SVG 渲染测试并实现最小热力图输出

**Files:**
- Modify: `tests/test_generate_github_heatmap.py`
- Modify: `scripts/generate_github_heatmap.py`

**Step 1: Write the failing test**

新增测试，验证给定标准化天数据后，SVG 输出满足：
- 包含 `<svg`
- 包含至少一个 `<rect`
- 包含日期或标题文本
- 不同贡献强度映射为不同填充色

```python
svg = render_heatmap_svg(sample_days, username="axin7")
assert "<svg" in svg
assert svg.count("<rect") >= 7
assert "GitHub Contributions" in svg
assert "fill="#" in svg
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests/test_generate_github_heatmap.py -v`

Expected: FAIL，提示 `render_heatmap_svg` 未定义或输出不满足断言。

**Step 3: Write minimal implementation**

在 `scripts/generate_github_heatmap.py` 中实现：
- `level_to_color(level)`
- `render_heatmap_svg(days, username)`
- 布局规则：按周成列、按星期成行生成 `<rect>` 网格
- 使用固定尺寸、圆角与低饱和绿色配色

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests/test_generate_github_heatmap.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_generate_github_heatmap.py scripts/generate_github_heatmap.py
git commit -m "feat: render profile contribution heatmap svg"
```

### Task 3: 为脚本增加 GitHub GraphQL 拉取与 CLI 出口

**Files:**
- Modify: `tests/test_generate_github_heatmap.py`
- Modify: `scripts/generate_github_heatmap.py`

**Step 1: Write the failing test**

新增 CLI / 集成测试，验证脚本可以：
- 从 fixture 模式生成文件
- 通过命令行指定输出路径
- 输出文件包含有效 `<svg>` 内容

```python
exit_code = main([
    "--from-fixture", "tests/fixtures/github_contributions_response.json",
    "--output", "tmp/heatmap.svg",
    "--username", "axin7",
])
assert exit_code == 0
assert Path("tmp/heatmap.svg").read_text().startswith("<svg")
```

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests/test_generate_github_heatmap.py -v`

Expected: FAIL，提示 `main` 不支持参数或未写出文件。

**Step 3: Write minimal implementation**

在 `scripts/generate_github_heatmap.py` 中实现：
- `fetch_contributions(token, username, from_date, to_date)`
- `main(argv=None)`
- 支持参数：`--username`、`--output`、`--from-fixture`
- 使用标准库 `urllib.request` 调用 GraphQL API
- 将 GraphQL token 从环境变量读取，例如 `GH_STATS_TOKEN`，并在缺失时快速失败

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests/test_generate_github_heatmap.py -v`

Expected: PASS

**Step 5: Commit**

```bash
git add tests/test_generate_github_heatmap.py scripts/generate_github_heatmap.py
git commit -m "feat: add graphql fetch and heatmap cli"
```

### Task 4: 重写 `README.md` 为个人名片结构并接入热力图区块

**Files:**
- Modify: `README.md`
- Create: `assets/heatmap.svg`

**Step 1: Write the failing test**

这里使用内容验收代替单元测试。先定义完成标准：
- 首页只保留 4 个主区块：Hero、How I Think、Selected Work、Activity
- 移除详细项目矩阵展开
- `README.md` 引用 `assets/heatmap.svg`

可先写一个最小检查脚本或人工清单：

```text
- 不再出现 "Anyveo Projects / 项目矩阵" 二级长列表
- 出现 "## Activity"
- 出现 `![GitHub Contribution Heatmap](./assets/heatmap.svg)`
```

**Step 2: Run test to verify it fails**

Run: `rg -n "Anyveo Projects|## Activity|assets/heatmap.svg" README.md`

Expected: 当前结构不满足新要求。

**Step 3: Write minimal implementation**

修改 `README.md`：
- 开头只保留名字、定位、身份、城市
- 收缩方法论为短句区块
- 将项目矩阵改为 2～3 个精选入口
- 添加 `## Activity` 并引用 `./assets/heatmap.svg`

使用 fixture 或手动运行脚本先生成一个初始 `assets/heatmap.svg`，保证页面可立即显示。

**Step 4: Run test to verify it passes**

Run: `rg -n "## Activity|assets/heatmap.svg" README.md && rg -n "Anyveo Projects" README.md`

Expected: 第一条有结果，第二条无结果。

**Step 5: Commit**

```bash
git add README.md assets/heatmap.svg
git commit -m "feat: simplify profile readme and embed activity heatmap"
```

### Task 5: 增加 GitHub Actions 定时更新工作流

**Files:**
- Create: `.github/workflows/update-heatmap.yml`
- Modify: `README.md`
- Modify: `scripts/generate_github_heatmap.py`

**Step 1: Write the failing test**

定义 workflow 验收条件：
- 同时支持 `schedule` 与 `workflow_dispatch`
- 运行 `uv run python scripts/generate_github_heatmap.py --username axin7 --output assets/heatmap.svg`
- 仅在 `assets/heatmap.svg` 变化时提交
- commit message 固定为 `chore: update github contribution heatmap`

可通过文本检查先验证缺失：

```bash
rg -n "workflow_dispatch|schedule|update github contribution heatmap" .github/workflows/update-heatmap.yml
```

**Step 2: Run test to verify it fails**

Run: `test -f .github/workflows/update-heatmap.yml || echo missing`

Expected: 输出 `missing`

**Step 3: Write minimal implementation**

创建 `.github/workflows/update-heatmap.yml`：
- 触发器：`schedule` + `workflow_dispatch`
- 权限：`contents: write`
- 安装 Python / `uv`
- 使用 secret `GH_STATS_TOKEN`，若未配置则回退 `GITHUB_TOKEN`
- 运行脚本生成 `assets/heatmap.svg`
- 用 `git diff --quiet` 判断是否有变化
- 有变化时提交并推送

必要时在脚本中补充对 token 环境变量名称的兼容读取。

**Step 4: Run test to verify it passes**

Run: `sed -n '1,240p' .github/workflows/update-heatmap.yml`

Expected: 明确包含触发器、脚本命令、变更判断与提交逻辑。

**Step 5: Commit**

```bash
git add .github/workflows/update-heatmap.yml scripts/generate_github_heatmap.py README.md
git commit -m "ci: automate daily github heatmap updates"
```

### Task 6: 完成端到端验证与文档补充

**Files:**
- Modify: `README.md`
- Optional Create: `docs/plans/2026-03-07-profile-readme-heatmap-verification.md`

**Step 1: Write the failing test**

定义最终验收清单：
- 本地 fixture 生成 SVG 成功
- 单元测试通过
- `README.md` 结构符合新设计
- GitHub Actions 可手动触发

**Step 2: Run test to verify it fails**

Run: `uv run python -m unittest tests/test_generate_github_heatmap.py -v && uv run python scripts/generate_github_heatmap.py --from-fixture tests/fixtures/github_contributions_response.json --output assets/heatmap.svg --username axin7`

Expected: 在实现完成前，至少有一项失败。

**Step 3: Write minimal implementation**

补充 README 中必要说明：
- 图表来源于 GitHub 真实贡献数据
- 如需配置 token，使用仓库 secret `GH_STATS_TOKEN`

如有必要，增加一份简短验证记录文档，记录手动触发 workflow 的验收结果。

**Step 4: Run test to verify it passes**

Run: `uv run python -m unittest tests/test_generate_github_heatmap.py -v && uv run python scripts/generate_github_heatmap.py --from-fixture tests/fixtures/github_contributions_response.json --output assets/heatmap.svg --username axin7`

Expected: 全部 PASS，且 `assets/heatmap.svg` 成功生成。

**Step 5: Commit**

```bash
git add README.md assets/heatmap.svg tests/test_generate_github_heatmap.py .github/workflows/update-heatmap.yml scripts/generate_github_heatmap.py
git commit -m "docs: finalize profile heatmap automation"
```
