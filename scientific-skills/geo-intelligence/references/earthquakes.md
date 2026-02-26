# USGS Earthquake API

Free, real-time earthquake data. No API key required.

## Base URL

```
https://earthquake.usgs.gov/fdsnws/event/1/query
```

## Query Parameters

| Parameter | Description | Example |
|-----------|-------------|---------|
| format | Response format | `geojson` |
| starttime | Start date | `2024-01-01` |
| endtime | End date | `2024-12-31` |
| minmagnitude | Minimum magnitude | `4.0` |
| maxmagnitude | Maximum magnitude | `9.0` |
| latitude | Center latitude | `28.6139` (Delhi) |
| longitude | Center longitude | `77.2090` |
| maxradiuskm | Radius from center | `500` |
| limit | Max results | `100` |
| orderby | Sort order | `time`, `magnitude` |

## Recent Significant Earthquakes

```python
import requests
import pandas as pd

resp = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params={
    "format": "geojson",
    "starttime": "2024-01-01",
    "minmagnitude": 5.0,
    "orderby": "magnitude",
    "limit": 20,
})
data = resp.json()

quakes = []
for f in data["features"]:
    p = f["properties"]
    c = f["geometry"]["coordinates"]
    quakes.append({
        "time": pd.Timestamp(p["time"], unit="ms"),
        "magnitude": p["mag"],
        "place": p["place"],
        "lat": c[1],
        "lon": c[0],
        "depth_km": c[2],
    })

df = pd.DataFrame(quakes)
print(df.to_string(index=False))
```

## Earthquakes Near India

```python
resp = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params={
    "format": "geojson",
    "starttime": "2023-01-01",
    "minmagnitude": 4.0,
    "latitude": 20.5937,
    "longitude": 78.9629,
    "maxradiuskm": 2000,
})
```

## Financial Relevance

- **Insurance stocks**: Major earthquakes → claims → stock dips (General Insurance Corp, New India Assurance)
- **Construction/cement**: Post-disaster reconstruction → demand spike (UltraTech, ACC, Ambuja)
- **Commodity prices**: Earthquakes near mining regions → supply disruption → price spikes
- **Reinsurance**: Global reinsurance costs rise after major events

## Rate Limits

No hard rate limit, but USGS asks for reasonable usage. Cache results when possible.
