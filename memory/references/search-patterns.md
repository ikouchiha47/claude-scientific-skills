# Search Patterns

How the LLM should use memory during research sessions.

## Before Starting Research

Always check memory first. This avoids rediscovering known facts.

```bash
# What do we already know about this topic?
uv run python scripts/memory_store.py search observations "mining earthquake India"
uv run python scripts/memory_store.py search correlations "earthquake"
uv run python scripts/memory_store.py search analyses "NMDC"

# Any past strategies on these stocks?
uv run python scripts/memory_store.py search strategies "mining"
```

## Paginated Deep Search

For broad topics, paginate through results:

```bash
# Page 1
uv run python scripts/memory_store.py search observations "monsoon" --limit 10 --offset 0
# Page 2
uv run python scripts/memory_store.py search observations "monsoon" --limit 10 --offset 10
# Page 3
uv run python scripts/memory_store.py search observations "monsoon" --limit 10 --offset 20
```

Stop when results are empty or irrelevant.

## After Completing Analysis

Store everything useful:

```bash
# Store the observation
uv run python scripts/memory_store.py insert observations \
  '{"content": "...", "tags": "...", "source": "...", "confidence": "..."}'

# Store the analysis
uv run python scripts/memory_store.py insert analyses \
  '{"symbol": "...", "analysis_type": "...", "findings": "...", "recommendation": "..."}'

# Store any correlations discovered
uv run python scripts/memory_store.py insert correlations \
  '{"signal_type": "...", "asset": "...", "correlation_strength": ..., "direction": "...", "evidence": "..."}'

# Log the session
uv run python scripts/memory_store.py insert sessions \
  '{"query": "...", "skills_used": "geo-intelligence,yfinance,quant-models", "summary": "...", "status": "completed"}'
```

## Cross-Session Knowledge Building

Session 1: "Do earthquakes affect mining stocks?"
→ Discovers: NMDC drops on Odisha quakes, Coal India less affected
→ Stores observations + correlations

Session 2: "Best mining stocks to buy?"
→ Searches memory → Finds earthquake correlation
→ Factors it into analysis → Better recommendation

Session 3: "Backtest earthquake-based mining strategy"
→ Searches memory → Finds past correlations and observations
→ Builds strategy using known signals → Stores backtest results

Each session builds on the last. The memory compounds.
