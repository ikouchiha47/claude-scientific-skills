# Project: Claude Scientific Skills

## Environment Variables

**Before running any scripts**, source the `.env` file:

```bash
source .env
```

| Variable | Required | Description |
|----------|----------|-------------|
| `ALPHAVANTAGE_API_KEY` | Optional | Alpha Vantage market data API |
| `MEMORY_DIR` | Set in .env | Path to `.memory/` directory for persistent storage |
| `EIA_API_KEY` | Optional | US Energy Information Administration |
| `COMTRADE_API_KEY` | Optional | UN Comtrade trade flow data |

Never commit `.env` to git. If a script fails with missing config, check that `source .env` was run first.

## Running Code

### Python

All Python must use `uv` — never pollute the global environment.

```bash
# Ensure venv exists
[ -d .venv ] || uv venv

# Install deps
uv pip install <package>

# Run scripts
uv run python scripts/some_script.py

# Lint before committing
uv run ruff check .
```

### Before writing code

1. **Check memory first** — search for existing scripts, past approaches, known issues
2. **Check existing code** — look in `scripts/`, skill `scripts/` dirs, and reference docs for reusable code before writing new
3. **Read the skill's references/** — skill scripts are examples, not production-ready templates. Before using a skill's code, read its `references/` docs for API details, edge cases, and correct usage patterns. If the example doesn't handle your case (e.g. multi-ticker downloads, pagination, error handling), write new code using the references as the source of truth — don't force the example to work
4. **Verify dependencies** — after writing code, confirm all imports are installed (`uv pip install` if missing)
5. **Lint** — run `uv run ruff check` on any new/modified Python files

### Writing Python files

**NEVER use `echo` with `\n` to write Python files.** Use heredoc:

```bash
# CORRECT — heredoc preserves newlines
cat <<'PYEOF' > scripts/my_script.py
import pandas as pd

def main():
    print("hello")

if __name__ == "__main__":
    main()
PYEOF

# WRONG — writes literal \n characters, causes SyntaxError
echo 'import pandas as pd\ndef main():' > scripts/my_script.py
```

### Other languages

Use language-specific sandboxing (nix, npm/npx, cargo, etc.) — do not install globally.

## Script Locations

| Location | Purpose | Example |
|----------|---------|---------|
| `scientific-skills/<skill>/scripts/` | Reusable scripts bundled with a skill | `chart-scout/scripts/chart_scout.py` |
| `memory/scripts/` | Memory store CLI | `memory/scripts/memory_store.py` |
| `scripts/` | Reusable project-level tools (linking, generic feature engineering) | `scripts/link_skills.sh`, `scripts/feature_engineer.py` |
| `output/<analysis_name>/` | Ad-hoc analysis scripts + their outputs (data, charts, reports) | `output/mining_analysis/` |

**When creating scripts during analysis:**
- Put ad-hoc/one-off analysis scripts in `output/<analysis_name>/` alongside their output (CSV, PNG, reports)
- Only promote a script to `scripts/` if it's reusable across multiple analyses
- Never dump throwaway analysis scripts into root `scripts/` — it becomes a mess fast
- Name scripts descriptively: `output/mining_analysis/feature_extraction.py`, not `scripts/mining_v2.py`

## Skills Structure

Each skill lives under `scientific-skills/<skill-name>/` with:
- `SKILL.md` — main documentation (frontmatter + usage)
- `references/` — detailed reference docs
- `scripts/` — executable Python scripts (reusable, part of the skill)
- `assets/` — config files (YAML, JSON)

## Memory (Persistent Knowledge Store)

The `memory/` directory at the project root provides SQLite-based persistent storage. Use it to store and recall findings across sessions.

- **Storage**: `.memory/` directory (research.db, strategies.db, sessions.db)
- **Script**: `memory/scripts/memory_store.py`
- **Tables**: observations, analyses, strategies, correlations, sessions

**Always check memory before starting research** — avoid rediscovering known facts:

```bash
uv run python memory/scripts/memory_store.py search observations "earthquake mining"
uv run python memory/scripts/memory_store.py search correlations "monsoon agriculture"
```

**Always store findings after research**:

```bash
uv run python memory/scripts/memory_store.py insert observations '{"content": "...", "tags": "...", "source": "...", "confidence": "..."}'
```

See `memory/SKILL.md` and `memory/references/` for full schema and patterns.

## Query Reasoning — How to Break Down User Requests

When a user asks a research question, decompose it before executing. Think like a query expander:

### Step 1: Identify Components

User asks: *"Do geological events affect Indian mining stocks?"*

Break down:
- **Geological events** → earthquakes (USGS), weather/monsoon (Open-Meteo) → `geo-intelligence` skill
- **Indian mining stocks** → Coal India, NMDC, Vedanta, Tata Steel, Hindalco → `yfinance` skill
- **"Affect"** → need price data around event dates, correlation analysis → `quant-models` skill
- **Past knowledge** → check memory for prior findings → `memory`

### Step 2: Check What You Already Know

```bash
uv run python memory/scripts/memory_store.py search observations "mining earthquake"
uv run python memory/scripts/memory_store.py search correlations "earthquake"
```

If memory has relevant findings, build on them. Don't start from zero.

### Step 3: Identify Data Needs

| Need | Skill | Action |
|------|-------|--------|
| Earthquake data near mining regions | geo-intelligence | USGS API query |
| Mining stock prices | yfinance | `yf.download(["COALINDIA.NS", "NMDC.NS", ...])` |
| Weather/monsoon data | geo-intelligence | Open-Meteo historical |
| Correlation analysis | quant-models | Event study, regression |
| Visual chart analysis | chart-scout | Capture screenshots |

### Step 4: Execute and Store

Run the analysis, then store every useful finding in memory.

### Step 5: Chart Analysis

Always capture and analyze stock charts as part of any equity research:

```bash
# Capture chart screenshot (auto-selects screener.in for NSE/BSE)
uv run python .claude/skills/chart-scout/scripts/chart_scout.py \
  --symbol RELIANCE --exchange NSE --timeframe 1Y \
  --output output/<analysis-dir>/charts/RELIANCE.png
```

Read the screenshot with the Read tool and provide visual technical analysis:
- Price pattern (uptrend, range-bound, breakdown, parabolic)
- Volume confirmation
- Support/resistance levels
- Moving average positioning

### Step 6: Save Report

Always save a markdown report to `output/<analysis-name>/REPORT.md` containing:
- Data summaries (tables)
- Correlation findings
- Chart analysis (visual observations)
- Recommendations with rationale

This ensures results are reproducible and reviewable across sessions.

### More Examples

**"Suggest a basket of stocks for long-term investment"**
1. Components: stock screening, fundamental analysis, portfolio optimization
2. Check memory: past analyses, strategy results
3. Data: yfinance (fundamentals, prices), quant-models (portfolio optimization, risk metrics)
4. Execute: screen stocks → analyze → optimize weights → store recommendation

**"Backtest RSI strategy on NIFTY 50 stocks"**
1. Components: historical data, RSI computation, backtesting engine, performance metrics
2. Check memory: past backtest results for RSI strategies
3. Data: yfinance (NIFTY 50 prices), backtesting (vectorbt)
4. Execute: fetch data → run backtest → compare with benchmark → store results

**"How will monsoon affect agriculture stocks this year?"**
1. Components: monsoon forecast, historical monsoon-stock correlation, agriculture stocks
2. Check memory: past monsoon observations and correlations
3. Data: geo-intelligence (Open-Meteo forecast + history), yfinance (UPL, PI Industries, CHAMBLFERT)
4. Execute: get forecast → compare with historical patterns → check correlations → recommend