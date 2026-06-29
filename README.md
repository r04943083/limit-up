<div align="center">

# limit-up · LU

**An AI‑native personal investment platform — research, recommend, simulate, manage, journal, and continuously improve your decisions, with AI doing the reasoning.**

Local‑first · premium Futu/Webull‑style dark terminal · covers **US + Hong Kong + A‑share**.

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-local-003B57?logo=sqlite&logoColor=white)
![MCP](https://img.shields.io/badge/MCP-server-7C3AED)
![AI](https://img.shields.io/badge/AI-Claude_Code-D97757)

[English](#english) · [中文](#中文)

</div>

---

<a id="english"></a>

## English

### What is LU?

LU is a **single‑user, local‑first** investment workstation. It pulls market data once into a local SQLite database, computes everything deterministically in Python, and uses an LLM **only to narrate, score, and reason over those facts — never to invent numbers**. The web UI is a Futu‑牛牛‑style three‑pane terminal; the same engine is exposed to Claude Desktop/Code/Cursor through an MCP server.

> ⚠️ **Not financial advice.** Every AI output is labeled opinion. This is a personal research tool.

### The "dual‑brain" architecture

```
                 ┌──────────────────────────── deterministic brain ───────────────────────────┐
Browser ──REST──▶│ apps/api (FastAPI :8000) ─▶ packages/lucore  (compute · data · services)    │
                 │                                   │                                          │
Claude / claude -p ──MCP──▶ apps/mcp (stdio) ────────┤                                          │
                 │                                   ▼                                          │
                 │                            SQLite  (data/lu.db)                              │
                 └────────────────────────────────────────────────────────────────────────────┘
                                                   ▲
                                                   │ narrates / scores facts (never computes numbers)
                                       reasoning brain: LLMProvider
                                  (claude -p · GLM‑4.6 · Anthropic API)
```

- **Deterministic brain — `packages/lucore` (Python).** Market data routing & caching, technical indicators, screening, backtesting, portfolio & paper‑trade math. It never asks an LLM to compute a number.
- **Reasoning brain — pluggable `LLMProvider`.** Default is **headless Claude Code (`claude -p`)** — zero marginal cost on a Max plan, seamless background generation. Optional paid providers: GLM‑4.6, Anthropic API. The LLM receives a *facts contract* and returns structured, validated JSON that is persisted as labeled opinion.
- **MCP server — `apps/mcp`.** Exposes LU's tools to any MCP client. Read tools return facts; the write‑back tool persists the calling LLM's own structured analysis into the local DB.
- **Web app — `apps/web` (Next.js 15).** Reads stored results (instant, cache‑first) and drives generation.

### Features

LU implements the full product surface across **13 screens**:

| Screen | Route | What it does |
| --- | --- | --- |
| **Opportunities** | `/` | Daily AI briefing, opportunity feed, index ribbon, sector heatmap, gain/loss distribution. |
| **Watchlist** | `/watchlist` | Futu‑style 3‑pane terminal: groups with drag‑reorder, tags & notes, dense quote rows + sparklines, `.ebk` import/export, JSON backup. |
| **Research** | `/research/{symbol}` | K‑line (D/W/M + volume), MA/BOLL/MACD/RSI/KDJ, three‑statement financials (annual/quarterly), dividends, shareholders, profile, **DCF with live‑editable assumptions**, AI deep‑dive. |
| **AI Chat** | `/chat` | Grounded conversational analyst — mentioning a ticker auto‑injects LU's real facts (price/MAs/RSI/analyst targets). |
| **Recommendations** | `/recommendations` | Deterministic screeners (growth/value/momentum/dividend/AI/quality/swing) + AI thesis & scoring. |
| **Limit‑up** | `/limitup` | A‑share 涨停 pool, consecutive‑limit ladder (连板天梯), dragon‑tiger list (龙虎榜), Stock‑Connect flows, AI replay. |
| **Portfolio** | `/portfolio` | CSV/`.ebk` import (Futu/IBKR/generic), multi‑currency analytics, allocation, concentration (HHI), correlation heatmap, AI review. |
| **Paper Trading** | `/paper` | Virtual cash account; trades fill at the cached quote; positions & P&L derived live from the ledger. |
| **Strategy** | `/strategy` | Rule backtester (`rsi` · `ma_cross` · `breakout`): equity curve vs buy‑&‑hold, drawdown, win‑rate, Sharpe, exposure + AI explanation. |
| **Replay** | `/replay` | Bar‑by‑bar historical playback with the future hidden — a "guess the next move" tape‑reading drill. |
| **Journal** | `/journal` | Decision log with conviction; AI grades the **quality of your reasoning** (strengths / blind spots / biases). |
| **AI Studio** | `/studio` | Five AI labs: **Bull‑vs‑Bear debate**, **multi‑agent panel** (fundamental/technical/sentiment/risk/macro), **investor personas** (Buffett · Lynch · Livermore · Wood · Dalio · Contrarian), **AI coach**, **investing DNA**. |
| **AI Usage** | `/usage` | Token/cost tracking and a call log for every LLM invocation. |

### Tech stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2 + SQLite, APScheduler, Pydantic v2, yfinance, akshare.
- **Frontend:** Next.js 15 (App Router) · React 19 · TypeScript 5.7 · Tailwind 3.4 · lightweight‑charts.
- **AI seam:** headless `claude -p` (default) / GLM‑4.6 / Anthropic API, plus an MCP (FastMCP) server.
- **Tooling:** `uv` workspace, `ruff`, `pytest`, Playwright E2E.

### Project structure

```
limit-up/
├─ packages/lucore/        # the deterministic engine (all real logic lives here)
│  └─ lucore/{data,compute,services,db,llm,scheduler}/
├─ apps/api/               # FastAPI adapter (:8000) — thin routers over lucore
├─ apps/web/               # Next.js terminal (:3000) — App Router, "use client" pages
├─ apps/mcp/               # FastMCP server (stdio) — LU tools for Claude/Cursor
├─ scripts/                # start-web.sh / stop-web.sh / init_db.py
└─ data/                   # local SQLite DB + exports (git‑ignored, never committed)
```

### Quick start

**Requirements:** Python 3.12 (managed by [`uv`](https://docs.astral.sh/uv/)), Node 20+. `uv` is expected on `PATH` (e.g. `~/.local/bin`).

**One command (recommended — builds & serves both services with crash‑restart):**

```bash
scripts/start-web.sh           # PROD: build the web app, then serve  → http://localhost:3000
scripts/start-web.sh --dev     # DEV: hot reload (uvicorn --reload + next dev), no build
scripts/start-web.sh --tunnel  # also open a public Cloudflare quick‑tunnel (no auth!)
scripts/stop-web.sh            # stop everything (and the tunnel)
```

> PROD serves a build snapshot; if a page looks stale, hard‑refresh (Ctrl/Cmd+Shift+R).
> `--tunnel` exposes a random, **unauthenticated** `*.trycloudflare.com` URL — anyone with the link can use it and burn your AI quota.

**Granular (Makefile):**

```bash
make install   # uv sync + npm install
make initdb    # create data/lu.db
make api       # FastAPI on http://localhost:8000   (try /health)
make web       # Next.js on http://localhost:3000
make test      # pytest
make lint      # ruff
```

LU runs with **zero config and zero AI cost** out of the box.

### Configuration

Optional — copy to a `.env` at the repo root. All keys are prefixed `LU_`.

| Variable | Default | Description |
| --- | --- | --- |
| `LU_LLM_PROVIDER` | `claude_code` | `claude_code` (zero‑cost `claude -p`) · `glm` · `anthropic`. |
| `LU_CLAUDE_BIN` / `LU_CLAUDE_MODEL` | `claude` / auto | Headless Claude binary & model override. |
| `LU_GLM_API_KEY` / `LU_ANTHROPIC_API_KEY` | – | Keys for the paid providers. |
| `LU_ENABLE_HK` / `LU_ENABLE_CN` | `true` / `true` | Toggle Hong Kong / A‑share markets. |
| `LU_ENABLE_SCHEDULER` | `true` | In‑process daily sync + briefing job. |
| `LU_BRIEFING_HOUR` / `LU_BRIEFING_MINUTE` | `8` / `30` | Local time to auto‑sync and write the daily briefing. |
| `LU_DATA_DIR` / `LU_DB_FILENAME` | `data/` / `lu.db` | Storage location. |
| `LU_FINNHUB_API_KEY` / `LU_SEC_USER_AGENT` | – | Optional data‑source credentials. |

### Data & caching

LU is **cache‑first**: data is fetched once into SQLite, refreshed roughly daily (and on explicit "sync"), and pages read from the DB instantly — no live fetch on load. Staleness is judged against each symbol's **market‑local** trading day.

- **yfinance** — quotes, fundamentals, news, OHLCV for US/HK/A‑share.
- **akshare** — A‑share limit‑up pool, dragon‑tiger list, Stock‑Connect flows.
- **Futu `.ebk`** — watchlist import/export.

### MCP tools

Exposed by `apps/mcp` to any MCP client (Claude Desktop/Code, Cursor):

`lu_health` · `search_stock` · `get_research_facts` · `technical_analysis` · `screen_stock` · `portfolio_analysis` · `backtest_strategy` · `paper_trade` · `save_analysis` (write‑back).

### Conventions

- **Colors: red = up, green = down** (Chinese / Futu convention).
- **All numbers come from `compute` + `data`; the LLM only narrates and scores.**
- `data/` (your DB/portfolio) and `reference/` (personal exports) are **never committed**.

### Testing

```bash
uv run pytest -q                       # Python unit tests (lucore)
cd apps/web && npx playwright test     # Playwright E2E (needs the app running)
```

### License

Personal project — no open‑source license is granted. All rights reserved.

---

<a id="中文"></a>

## 中文

### LU 是什么?

LU 是一个**单用户、本地优先**的投资工作站。它把行情数据**一次性**拉进本地 SQLite,所有数值都在 Python 里**确定性计算**,LLM **只负责叙述、打分、对既有事实做推理——绝不编造数字**。Web 界面是富途牛牛式的三栏终端;同一套引擎还通过 MCP 服务器开放给 Claude Desktop/Code/Cursor 使用。

> ⚠️ **非投资建议。** 所有 AI 输出都标注为「观点」。这是个人研究工具。

### 「双脑」架构

```
                 ┌──────────────────────────── 确定性脑 ───────────────────────────┐
浏览器 ──REST──▶ │ apps/api (FastAPI :8000) ─▶ packages/lucore (compute·data·服务) │
                 │                                   │                              │
Claude / claude -p ──MCP──▶ apps/mcp (stdio) ────────┤                              │
                 │                                   ▼                              │
                 │                            SQLite  (data/lu.db)                  │
                 └──────────────────────────────────────────────────────────────────┘
                                                   ▲
                                                   │ 叙述 / 打分(从不计算数字)
                                          推理脑:LLMProvider
                                  (claude -p · GLM‑4.6 · Anthropic API)
```

- **确定性脑 —— `packages/lucore`(Python)。** 行情路由与缓存、技术指标、选股、回测、组合与模拟交易的数学。永远不会让 LLM 算数。
- **推理脑 —— 可插拔 `LLMProvider`。** 默认 **无头 Claude Code(`claude -p`)**:Max 套餐下边际成本为零、后台无感生成。可选付费:GLM‑4.6、Anthropic API。LLM 收到的是一份「事实契约」,返回经校验的结构化 JSON,作为「带标签的观点」落库。
- **MCP 服务器 —— `apps/mcp`。** 把 LU 的工具开放给任意 MCP 客户端:读工具返回事实,写回工具把调用方 LLM 自己的结构化分析持久化进本地库。
- **Web 应用 —— `apps/web`(Next.js 15)。** 读取已存结果(缓存优先、即时)并触发生成。

### 功能

LU 覆盖完整产品面,共 **13 个页面**:

| 页面 | 路由 | 做什么 |
| --- | --- | --- |
| **机会** | `/` | 每日 AI 简报、机会流、指数条、行业热力图、涨跌分布。 |
| **自选** | `/watchlist` | 富途式三栏终端:分组拖拽排序、标签与备注、密集报价行+迷你走势、`.ebk` 导入导出、JSON 备份。 |
| **研究** | `/research/{代码}` | K 线(日/周/月+量)、MA/BOLL/MACD/RSI/KDJ、财报三表(年/季)、分红、股东、概况、**可实时改假设的 DCF**、AI 深度研究。 |
| **AI 对话** | `/chat` | 接地气的对话式分析师——提到代码会自动注入 LU 的真实事实(价格/均线/RSI/分析师目标)。 |
| **推荐** | `/recommendations` | 确定性选股器(成长/价值/动量/分红/AI/质量/波段)+ AI 逻辑与打分。 |
| **涨停** | `/limitup` | A 股涨停池、连板天梯、龙虎榜、沪深港通资金、AI 复盘。 |
| **组合** | `/portfolio` | CSV/`.ebk` 导入(富途/IBKR/通用)、多币种分析、配置、集中度(HHI)、相关性热力图、AI 复盘。 |
| **模拟交易** | `/paper` | 虚拟现金账户;按缓存价成交;持仓与盈亏由台账实时派生。 |
| **策略** | `/strategy` | 规则回测器(`rsi`·`ma_cross`·`breakout`):净值曲线 vs 买入持有、回撤、胜率、Sharpe、仓位暴露 + AI 解读。 |
| **复盘** | `/replay` | 逐根回放历史 K 线、隐藏未来——「猜涨跌」练盘感。 |
| **日志** | `/journal` | 带信念度的决策记录;AI 评的是你**决策过程的质量**(优点/盲点/行为偏差)。 |
| **AI 工作室** | `/studio` | 五个 AI 实验室:**多空辩论**、**多智能体投研**(基本面/技术/情绪/风险/宏观)、**投资人格**(巴菲特·林奇·利弗莫尔·伍德·达里奥·逆向)、**AI 教练**、**投资 DNA**。 |
| **AI 用量** | `/usage` | 每次 LLM 调用的 token/成本统计与调用日志。 |

### 技术栈

- **后端:** Python 3.12、FastAPI、SQLAlchemy 2 + SQLite、APScheduler、Pydantic v2、yfinance、akshare。
- **前端:** Next.js 15(App Router)· React 19 · TypeScript 5.7 · Tailwind 3.4 · lightweight‑charts。
- **AI 接缝:** 无头 `claude -p`(默认)/ GLM‑4.6 / Anthropic API,外加 MCP(FastMCP)服务器。
- **工具链:** `uv` 工作区、`ruff`、`pytest`、Playwright E2E。

### 项目结构

```
limit-up/
├─ packages/lucore/        # 确定性引擎(所有真实逻辑都在这)
│  └─ lucore/{data,compute,services,db,llm,scheduler}/
├─ apps/api/               # FastAPI 适配层(:8000)—— lucore 之上的薄路由
├─ apps/web/               # Next.js 终端(:3000)—— App Router,"use client" 页面
├─ apps/mcp/               # FastMCP 服务器(stdio)—— 给 Claude/Cursor 的 LU 工具
├─ scripts/                # start-web.sh / stop-web.sh / init_db.py
└─ data/                   # 本地 SQLite 库 + 导出(已 git‑ignore,绝不入库)
```

### 快速开始

**环境要求:** Python 3.12(由 [`uv`](https://docs.astral.sh/uv/) 管理)、Node 20+。`uv` 需在 `PATH` 上(如 `~/.local/bin`)。

**一条命令(推荐 —— 构建并托管前后端,崩溃自动重启):**

```bash
scripts/start-web.sh           # 生产:先 build 前端再托管 → http://localhost:3000
scripts/start-web.sh --dev     # 开发:热重载(uvicorn --reload + next dev),不 build
scripts/start-web.sh --tunnel  # 额外开 Cloudflare 公网隧道(无鉴权!)
scripts/stop-web.sh            # 全部停止(含隧道)
```

> 生产模式服务的是 build 快照;页面没更新就硬刷新(Ctrl/Cmd+Shift+R)。
> `--tunnel` 暴露一个随机、**无鉴权**的 `*.trycloudflare.com` 网址——谁有链接谁能用、会消耗你的 AI 额度。

**细粒度(Makefile):**

```bash
make install   # uv sync + npm install
make initdb    # 创建 data/lu.db
make api       # FastAPI → http://localhost:8000   (试试 /health)
make web       # Next.js → http://localhost:3000
make test      # pytest
make lint      # ruff
```

LU **零配置、零 AI 成本**即可开箱运行。

### 配置

可选——在仓库根目录建 `.env`。所有键以 `LU_` 为前缀。

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `LU_LLM_PROVIDER` | `claude_code` | `claude_code`(零成本 `claude -p`)· `glm` · `anthropic`。 |
| `LU_CLAUDE_BIN` / `LU_CLAUDE_MODEL` | `claude` / 自动 | 无头 Claude 可执行文件与模型覆盖。 |
| `LU_GLM_API_KEY` / `LU_ANTHROPIC_API_KEY` | – | 付费 provider 的密钥。 |
| `LU_ENABLE_HK` / `LU_ENABLE_CN` | `true` / `true` | 开关 港股 / A 股 市场。 |
| `LU_ENABLE_SCHEDULER` | `true` | 进程内每日同步 + 简报任务。 |
| `LU_BRIEFING_HOUR` / `LU_BRIEFING_MINUTE` | `8` / `30` | 自动同步并生成每日简报的本地时刻。 |
| `LU_DATA_DIR` / `LU_DB_FILENAME` | `data/` / `lu.db` | 存储位置。 |
| `LU_FINNHUB_API_KEY` / `LU_SEC_USER_AGENT` | – | 可选数据源凭据。 |

### 数据与缓存

LU 是**缓存优先**的:数据一次性拉进 SQLite,约每日(及显式「同步」时)刷新,页面直接读库即时呈现——**加载时不实时拉取**。过期与否按每个标的**所在市场的本地交易日**判断。

- **yfinance** —— 美股/港股/A 股的报价、基本面、新闻、OHLCV。
- **akshare** —— A 股涨停池、龙虎榜、沪深港通资金。
- **富途 `.ebk`** —— 自选导入导出。

### MCP 工具

由 `apps/mcp` 开放给任意 MCP 客户端(Claude Desktop/Code、Cursor):

`lu_health` · `search_stock` · `get_research_facts` · `technical_analysis` · `screen_stock` · `portfolio_analysis` · `backtest_strategy` · `paper_trade` · `save_analysis`(写回)。

### 约定

- **配色:红 = 涨,绿 = 跌**(中国 / 富途习惯)。
- **所有数字来自 `compute` + `data`;LLM 只叙述与打分。**
- `data/`(你的库/组合)与 `reference/`(个人导出)**绝不入库**。

### 测试

```bash
uv run pytest -q                       # Python 单元测试(lucore)
cd apps/web && npx playwright test     # Playwright E2E(需先启动应用)
```

### 许可

个人项目——未授予任何开源许可,保留所有权利。

---

<div align="center">
<sub>LU · dual‑brain investing — deterministic numbers, AI reasoning. Not financial advice.</sub>
</div>
