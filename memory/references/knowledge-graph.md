# Knowledge Graph (NetworkX)

Build, update, and query a knowledge graph of relationships between assets, signals, events, and strategies. Stored as GraphML files in `.memory/graphs/`.

## Installation

```bash
uv pip install networkx
```

## Graph Storage

```
.memory/
├── graphs/
│   ├── market.graphml      — stocks, sectors, indices, relationships
│   ├── signals.graphml     — geo signals → asset impact edges
│   └── strategies.graphml  — strategies → assets → performance
```

## Creating a Graph

```python
import networkx as nx
from pathlib import Path

GRAPH_DIR = Path(".memory/graphs")
GRAPH_DIR.mkdir(parents=True, exist_ok=True)

G = nx.DiGraph()

# Add stock nodes
G.add_node("RELIANCE.NS", type="stock", sector="Energy", market_cap="large")
G.add_node("NMDC.NS", type="stock", sector="Mining", market_cap="mid")
G.add_node("COALINDIA.NS", type="stock", sector="Mining", market_cap="large")

# Add signal nodes
G.add_node("earthquake_odisha", type="signal", source="USGS", region="Odisha")
G.add_node("monsoon_deficit", type="signal", source="Open-Meteo", region="India")

# Add edges (relationships)
G.add_edge("earthquake_odisha", "NMDC.NS", relation="negative_impact", strength=-0.3, lag_days=1)
G.add_edge("earthquake_odisha", "COALINDIA.NS", relation="negative_impact", strength=-0.15, lag_days=2)
G.add_edge("monsoon_deficit", "RELIANCE.NS", relation="positive_impact", strength=0.1, lag_days=30)

# Add sector relationships
G.add_edge("NMDC.NS", "Mining", relation="belongs_to")
G.add_edge("COALINDIA.NS", "Mining", relation="belongs_to")

# Save
nx.write_graphml(G, str(GRAPH_DIR / "signals.graphml"))
```

## Loading and Querying

```python
import networkx as nx

G = nx.read_graphml(".memory/graphs/signals.graphml")

# What affects NMDC?
predecessors = list(G.predecessors("NMDC.NS"))
for p in predecessors:
    edge = G.edges[p, "NMDC.NS"]
    print(f"{p} → NMDC.NS: {edge.get('relation')} (strength: {edge.get('strength')})")

# What does an earthquake in Odisha affect?
successors = list(G.successors("earthquake_odisha"))
for s in successors:
    edge = G.edges["earthquake_odisha", s]
    print(f"earthquake_odisha → {s}: {edge.get('relation')}")

# All nodes of type 'stock'
stocks = [n for n, d in G.nodes(data=True) if d.get("type") == "stock"]

# All nodes of type 'signal'
signals = [n for n, d in G.nodes(data=True) if d.get("type") == "signal"]

# Shortest path between two nodes
if nx.has_path(G, "earthquake_odisha", "Mining"):
    path = nx.shortest_path(G, "earthquake_odisha", "Mining")
    print(f"Path: {' → '.join(path)}")
```

## Updating the Graph

```python
G = nx.read_graphml(".memory/graphs/signals.graphml")

# Add new observation
G.add_node("cyclone_chennai", type="signal", source="Open-Meteo", region="Tamil Nadu")
G.add_edge("cyclone_chennai", "TATAMOTORS.NS", relation="negative_impact", strength=-0.2, lag_days=3,
           evidence="Chennai port disruption affects auto exports")

# Update existing edge with new data
if G.has_edge("earthquake_odisha", "NMDC.NS"):
    G.edges["earthquake_odisha", "NMDC.NS"]["strength"] = -0.35
    G.edges["earthquake_odisha", "NMDC.NS"]["last_updated"] = "2026-02-27"

# Save
nx.write_graphml(G, ".memory/graphs/signals.graphml")
```

## Building a Market Graph

```python
import networkx as nx
import yfinance as yf
import numpy as np

G = nx.Graph()

tickers = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "NMDC.NS"]
prices = yf.download(tickers, period="1y")["Close"]
corr = prices.pct_change().corr()

# Add stocks as nodes
for t in tickers:
    info = yf.Ticker(t).info
    G.add_node(t, type="stock", sector=info.get("sector", ""), name=info.get("shortName", ""))

# Add edges for correlated pairs (> 0.5 correlation)
for i, t1 in enumerate(tickers):
    for j, t2 in enumerate(tickers):
        if i < j and abs(corr.loc[t1, t2]) > 0.5:
            G.add_edge(t1, t2, correlation=round(corr.loc[t1, t2], 3))

nx.write_graphml(G, ".memory/graphs/market.graphml")
```

## Graph Analysis

```python
G = nx.read_graphml(".memory/graphs/market.graphml")

# Most connected stocks (highest degree)
degrees = sorted(G.degree(), key=lambda x: x[1], reverse=True)
print("Most connected:", degrees[:5])

# Clusters
if not G.is_directed():
    communities = list(nx.community.greedy_modularity_communities(G))
    for i, comm in enumerate(communities):
        print(f"Cluster {i}: {comm}")

# Central nodes (influence)
centrality = nx.betweenness_centrality(G)
print("Most central:", sorted(centrality.items(), key=lambda x: x[1], reverse=True)[:5])
```

## Combining with SQLite Memory

The graph complements the SQLite tables:
- **SQLite** — stores individual observations, analyses, backtest results (structured, searchable)
- **Graph** — stores relationships between entities (navigable, pattern discovery)

Workflow:
1. Store raw finding in SQLite `observations` table
2. Add the relationship to the graph (signal → asset edge)
3. Next session: query graph for related signals before starting analysis
