# Energy & Grid Data (EIA)

US Energy Information Administration — comprehensive energy data.

## API Key

Free at https://www.eia.gov/opendata/register.php

## Base URL

```
https://api.eia.gov/v2/
```

## Crude Oil Prices

```python
import requests
import os
import pandas as pd

API_KEY = os.environ.get("EIA_API_KEY")

resp = requests.get(f"https://api.eia.gov/v2/petroleum/pri/spt/data/", params={
    "api_key": API_KEY,
    "frequency": "daily",
    "data[0]": "value",
    "facets[product][]": "EPCBRENT",  # Brent crude
    "sort[0][column]": "period",
    "sort[0][direction]": "desc",
    "length": 30,
})
data = resp.json()["response"]["data"]
df = pd.DataFrame(data)
print(df[["period", "product-name", "value"]].head(10))
```

## US Oil Inventories

```python
# Weekly crude oil stocks (key market mover)
resp = requests.get(f"https://api.eia.gov/v2/petroleum/stoc/wstk/data/", params={
    "api_key": API_KEY,
    "frequency": "weekly",
    "data[0]": "value",
    "facets[product][]": "EPC0",  # Crude oil
    "sort[0][column]": "period",
    "sort[0][direction]": "desc",
    "length": 20,
})
```

## Natural Gas

```python
# Henry Hub natural gas spot price
resp = requests.get(f"https://api.eia.gov/v2/natural-gas/pri/fut/data/", params={
    "api_key": API_KEY,
    "frequency": "daily",
    "data[0]": "value",
    "sort[0][column]": "period",
    "sort[0][direction]": "desc",
    "length": 30,
})
```

## Electricity Generation

```python
# US electricity generation by source
resp = requests.get(f"https://api.eia.gov/v2/electricity/rto/fuel-type-data/data/", params={
    "api_key": API_KEY,
    "frequency": "hourly",
    "data[0]": "value",
    "length": 100,
})
```

## Financial Relevance

- **Oil inventories**: Weekly draw/build → oil price direction → ONGC, Oil India, Reliance, IOC
- **Brent crude price**: India imports ~85% of oil — rising crude = negative for INR, OMCs
- **Natural gas**: Power generation costs, fertilizer input costs
- **Renewable generation**: Solar/wind capacity growth → clean energy stocks
- **Power demand**: Economic activity proxy — rising demand = industrial growth

## Rate Limits

EIA API: No explicit limit, but 1 request/second recommended.

## Environment Variable

```bash
export EIA_API_KEY="your_key_here"
```
