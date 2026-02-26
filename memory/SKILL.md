---
name: memory
description: Persistent SQLite-based memory for AI agent sessions. Store observations, analyses, backtest results, and discovered correlations across sessions. Supports paginated search (LLM-driven, no vector DB). Use to build institutional knowledge over time — past findings inform future queries.
license: MIT
metadata:
    skill-author: Iko Uchiha
---

# Memory — Persistent Agent Knowledge Store

SQLite-based memory that persists across sessions. Store what you learn, search what you've learned before. No vector DB — the LLM reads and filters results directly via paginated search.

## Installation

```bash
uv pip install sqlite3  # Built into Python, no install needed
```

## Storage Location

Memory lives in `.memory/` at the project root:

```
.memory/
├── research.db     — observations, analyses, correlations
├── strategies.db   — backtest results and strategy performance
└── sessions.db     — session logs and query history
```

## Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `observations` | Facts learned during research | content, tags, source, confidence |
| `analyses` | Completed stock/market analyses | symbol, analysis_type, findings, recommendation |
| `strategies` | Backtest results | name, parameters, sharpe_ratio, total_return |
| `correlations` | Discovered signal-asset correlations | signal_type, asset, correlation_strength, direction |
| `sessions` | Session history | query, skills_used, summary |

## Quick Start

### Store an observation

```bash
uv run python scripts/memory_store.py insert observations \
  '{"content": "NMDC dropped 3% after M6.2 earthquake near Bellary mining region", "tags": "mining,earthquake,NMDC,geo-intelligence", "source": "USGS + yfinance", "confidence": "high"}'
```

### Search past knowledge

```bash
uv run python scripts/memory_store.py search observations "earthquake mining" --limit 10
```

### Store analysis results

```bash
uv run python scripts/memory_store.py insert analyses \
  '{"symbol": "RELIANCE.NS", "analysis_type": "technical", "timeframe": "1Y", "findings": "Bearish head and shoulders pattern forming, RSI at 58", "recommendation": "Wait for breakdown confirmation below 1380", "data_sources": "chart-scout,yfinance", "confidence": "medium"}'
```

### Store backtest results

```bash
uv run python scripts/memory_store.py insert strategies \
  '{"name": "RSI_mean_reversion", "symbols": "RELIANCE.NS", "parameters": "{\"rsi_low\": 30, \"rsi_high\": 70}", "total_return": 0.23, "sharpe_ratio": 1.4, "max_drawdown": -0.12, "backtest_period": "2020-2025"}'
```

### Store discovered correlations

```bash
uv run python scripts/memory_store.py insert correlations \
  '{"signal_type": "earthquake", "signal_source": "USGS", "asset": "GICRE.NS", "correlation_strength": -0.3, "direction": "negative", "lag_days": 1, "evidence": "Insurance stocks drop 1-3% on M6+ earthquakes within 500km of major cities"}'
```

### Check what you know

```bash
uv run python scripts/memory_store.py tables
uv run python scripts/memory_store.py recent observations --limit 5
uv run python scripts/memory_store.py search correlations "earthquake"
```

## Programmatic Usage

```python
from memory_store import insert, search, recent, list_tables

# Store
insert("observations", {
    "content": "Monsoon deficit in Maharashtra correlates with sugar stock declines",
    "tags": "monsoon,agriculture,sugar",
    "source": "Open-Meteo + yfinance",
    "confidence": "medium",
})

# Recall
results = search("observations", "monsoon agriculture", limit=10, offset=0)
for r in results:
    print(f"[{r['confidence']}] {r['content']}")

# Paginate through all correlations
page = 0
while True:
    batch = search("correlations", "earthquake", limit=10, offset=page * 10)
    if not batch:
        break
    for r in batch:
        print(f"{r['asset']}: {r['direction']} ({r['correlation_strength']})")
    page += 1
```

## Workflow Integration

The memory skill is meant to be used **during and after** every research session:

1. **Before researching**: Search memory for past findings on the topic
2. **During research**: Store observations and intermediate findings
3. **After analysis**: Store final analysis, recommendations, correlations
4. **After backtesting**: Store strategy results and parameters
5. **Next session**: Search memory to build on previous work
