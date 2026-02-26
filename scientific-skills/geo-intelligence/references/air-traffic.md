# Air Traffic Data (OpenSky Network)

Free live and historical flight tracking. No key required for basic access.

## Base URL

```
https://opensky-network.org/api
```

## Live Aircraft

```python
import requests
import pandas as pd

# All aircraft currently over India
resp = requests.get("https://opensky-network.org/api/states/all", params={
    "lamin": 8, "lomin": 68, "lamax": 37, "lomax": 97,
})
states = resp.json()["states"]
print(f"Aircraft over India right now: {len(states)}")

# Parse into DataFrame
columns = ["icao24", "callsign", "origin_country", "time_position", "last_contact",
           "longitude", "latitude", "baro_altitude", "on_ground", "velocity",
           "true_track", "vertical_rate", "sensors", "geo_altitude",
           "squawk", "spi", "position_source"]
df = pd.DataFrame(states, columns=columns)
print(df[["callsign", "origin_country", "latitude", "longitude", "baro_altitude"]].head(10))
```

## Flights by Aircraft

```python
import time

# Flights for a specific aircraft in last 24h
now = int(time.time())
resp = requests.get("https://opensky-network.org/api/flights/aircraft", params={
    "icao24": "800640",  # Air India aircraft
    "begin": now - 86400,
    "end": now,
})
```

## Airport Arrivals/Departures

```python
# Arrivals at Mumbai (VABB)
resp = requests.get("https://opensky-network.org/api/flights/arrival", params={
    "airport": "VABB",
    "begin": now - 86400,
    "end": now,
})
arrivals = resp.json()
print(f"Mumbai arrivals (24h): {len(arrivals)}")
```

## Major Indian Airports (ICAO codes)

| Airport | ICAO | City |
|---------|------|------|
| Mumbai | VABB | Mumbai |
| Delhi | VIDP | New Delhi |
| Bangalore | VOBL | Bangalore |
| Chennai | VOMM | Chennai |
| Hyderabad | VOHS | Hyderabad |
| Kolkata | VECC | Kolkata |

## Financial Relevance

- **Flight volume trends**: Economic activity proxy — more flights = more business travel = healthy economy
- **Airline stocks**: Track actual flight counts vs capacity (IndiGo, SpiceJet, Air India)
- **Tourism**: International arrival trends → hotel, travel stocks
- **Cargo flights**: Trade activity indicator
- **Route changes**: Geopolitical events cause airspace closures → fuel cost impact

## Rate Limits

- Anonymous: 100 requests/day, 5-second interval
- Registered (free): 400 requests/day
- Register at https://opensky-network.org/
