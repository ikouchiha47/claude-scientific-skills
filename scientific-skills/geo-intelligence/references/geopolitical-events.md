# GDELT — Geopolitical Events Database

The largest open dataset of global events, updated every 15 minutes. Tracks protests, conflicts, diplomacy, disasters, and more across 300+ categories.

## Accessing GDELT

GDELT data is available via BigQuery (free tier) and direct file downloads.

### Quick Access via GDELT DOC API

```python
import requests
import pandas as pd

# Search for events mentioning India
resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
    "query": "India economy",
    "mode": "artlist",
    "maxrecords": 50,
    "format": "json",
    "timespan": "7d",
})
articles = resp.json().get("articles", [])
for a in articles[:5]:
    print(f"{a['seendate'][:10]} - {a['title'][:80]}")
    print(f"  Tone: {a.get('tone', 'N/A')}")
```

### Tone/Sentiment Tracking

```python
# Track sentiment about a topic over time
resp = requests.get("https://api.gdeltproject.org/api/v2/doc/doc", params={
    "query": "Indian stock market",
    "mode": "timelinetone",
    "format": "json",
    "timespan": "30d",
})
# Returns daily average tone (positive/negative sentiment)
```

### Event Geo-Mapping

```python
resp = requests.get("https://api.gdeltproject.org/api/v2/geo/geo", params={
    "query": "protest India",
    "format": "geojson",
    "timespan": "7d",
})
# Returns GeoJSON of event locations
```

## GDELT Event Categories (CAMEO codes)

| Code Range | Category | Financial Relevance |
|------------|----------|---------------------|
| 01 | Public statements | Market sentiment |
| 02 | Appeals | Diplomatic signals |
| 03 | Express intent to cooperate | Trade deals, FDI |
| 04 | Consult | Bilateral relations |
| 10 | Demand | Trade tensions |
| 13 | Threaten | Geopolitical risk |
| 14 | Protest | Political instability |
| 17 | Coerce | Sanctions, tariffs |
| 18 | Assault | Conflict escalation |
| 19 | Fight | War/military action |
| 20 | Use unconventional mass violence | Extreme risk |

## Financial Relevance

- **Conflict escalation**: Defense stocks up, emerging markets down
- **Trade tensions**: Tariff announcements → affected sector stocks
- **Political instability**: Protests, elections → currency and market volatility
- **Diplomatic events**: Trade deals, summits → positive for bilateral trade stocks
- **Tone trends**: Declining sentiment about an economy → leading indicator for markets

## Rate Limits

DOC API: No hard limit but be reasonable. BigQuery: 1TB/month free tier.
