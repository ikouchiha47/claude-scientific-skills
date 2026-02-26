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
3. **Verify dependencies** — after writing code, confirm all imports are installed (`uv pip install` if missing)
4. **Lint** — run `uv run ruff check` on any new/modified Python files

### Other languages

Use language-specific sandboxing (nix, npm/npx, cargo, etc.) — do not install globally.

## Skills Structure

Each skill lives under `scientific-skills/<skill-name>/` with:
- `SKILL.md` — main documentation (frontmatter + usage)
- `references/` — detailed reference docs
- `scripts/` — executable Python scripts
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