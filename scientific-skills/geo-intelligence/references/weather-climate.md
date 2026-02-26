# Weather & Climate Data

## Open-Meteo (Free, No Key)

### Current Weather

```python
import requests

resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
    "latitude": 19.076, "longitude": 72.8777,  # Mumbai
    "current_weather": True,
})
weather = resp.json()["current_weather"]
print(f"Temp: {weather['temperature']}°C, Wind: {weather['windspeed']} km/h")
```

### Forecast (7 days)

```python
resp = requests.get("https://api.open-meteo.com/v1/forecast", params={
    "latitude": 19.076, "longitude": 72.8777,
    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
    "timezone": "Asia/Kolkata",
    "forecast_days": 7,
})
daily = resp.json()["daily"]
for i in range(7):
    print(f"{daily['time'][i]}: {daily['temperature_2m_max'][i]}°C, Rain: {daily['precipitation_sum'][i]}mm")
```

### Historical Weather

```python
resp = requests.get("https://archive-api.open-meteo.com/v1/archive", params={
    "latitude": 19.076, "longitude": 72.8777,
    "start_date": "2023-06-01",
    "end_date": "2023-09-30",
    "daily": "temperature_2m_max,precipitation_sum",
    "timezone": "Asia/Kolkata",
})
# Useful for correlating monsoon intensity with agriculture stocks
```

## Key Indian Cities

| City | Lat | Lon | Relevance |
|------|-----|-----|-----------|
| Mumbai | 19.076 | 72.878 | Financial hub, flooding |
| Delhi | 28.614 | 77.209 | Government, pollution |
| Chennai | 13.083 | 80.270 | Auto manufacturing, cyclones |
| Kolkata | 22.572 | 88.364 | Eastern industry, flooding |
| Bangalore | 12.972 | 77.595 | IT sector, water crisis |

## Financial Relevance

- **Monsoon intensity**: Directly impacts agriculture stocks, rural consumption, fertilizer demand
- **Extreme heat**: Power demand spikes → energy stocks, productivity loss
- **Cyclones**: Shipping disruption, crop damage, insurance claims
- **Flooding**: Infrastructure damage, supply chain disruption
- **Drought**: Water-intensive industries (textiles, beverages, agriculture)

## Rate Limits

Open-Meteo: 10,000 requests/day (free). No key needed.
