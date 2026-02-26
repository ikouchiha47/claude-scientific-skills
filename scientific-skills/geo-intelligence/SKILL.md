---
name: geo-intelligence
description: Access free geospatial and event data for financial signal generation and risk assessment. Includes USGS earthquakes, Open-Meteo weather, OpenSky air traffic, GDELT geopolitical events, UN Comtrade shipping/trade flows, and EIA energy data. All sources are free APIs returning JSON. Use for alternative data signals, disaster impact analysis, and macroeconomic proxies.
license: MIT
metadata:
    skill-author: Iko Uchiha
---

# Geo-Intelligence — Geospatial & Event Data for Financial Signals

Free, open-source geospatial and event data that can serve as alternative signals for financial analysis, risk assessment, and macroeconomic monitoring.

## Installation

```bash
uv pip install requests pandas
```

## Data Sources

| Source | Data | API Key | Financial Relevance |
|--------|------|---------|---------------------|
| USGS | Earthquakes | No | Insurance, construction, commodities |
| Open-Meteo | Weather forecasts & history | No | Agriculture, energy, shipping |
| OpenSky | Live & historical flights | No (basic) | Airlines, tourism, economic activity |
| GDELT | Geopolitical events | No | Defense, emerging markets, geopolitical risk |
| UN Comtrade | International trade flows | Yes (free) | Supply chain, trade disruption |
| EIA | US energy data | Yes (free) | Energy stocks, oil/gas, economic activity |

## Quick Examples

### Recent earthquakes near a region
```python
import requests
resp = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params={
    "format": "geojson", "starttime": "2024-01-01", "minmagnitude": 5
})
for eq in resp.json()["features"][:5]:
    p = eq["properties"]
    print(f"M{p['mag']} - {p['place']} ({p['time']})")
```

### Current weather for a city
```python
resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
    "latitude": 19.076, "longitude": 72.8777,  # Mumbai
    "current_weather": True
})
print(resp.json()["current_weather"])
```

### Live flights over India
```python
resp = requests.get("https://opensky-network.org/api/states/all", params={
    "lamin": 8, "lomin": 68, "lamax": 37, "lomax": 97  # India bounding box
})
print(f"Aircraft over India: {len(resp.json()['states'])}")
```

See `references/` for detailed API docs, query parameters, and financial correlation examples.
