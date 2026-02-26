# Shipping & Trade Data

## UN Comtrade (International Trade Flows)

Global import/export data by country and commodity.

### API Key

Free registration at https://comtradeplus.un.org/ — required for API access.

### Query Trade Data

```python
import requests
import os

API_KEY = os.environ.get("COMTRADE_API_KEY")

# India's top imports from China, 2023
resp = requests.get("https://comtradeapi.un.org/data/v1/get/C/A/HS", params={
    "reporterCode": "699",  # India
    "partnerCode": "156",   # China
    "period": "2023",
    "flowCode": "M",        # Imports
    "subscription-key": API_KEY,
})
data = resp.json().get("data", [])
for item in sorted(data, key=lambda x: x.get("primaryValue", 0), reverse=True)[:10]:
    print(f"{item['cmdDesc']}: ${item['primaryValue']:,.0f}")
```

### Country Codes (common)

| Country | Code |
|---------|------|
| India | 699 |
| China | 156 |
| USA | 842 |
| Japan | 392 |
| Germany | 276 |
| UAE | 784 |

### Financial Relevance

- **Trade deficit widening**: Currency pressure, import-dependent stocks suffer
- **Commodity import volumes**: Oil, gold, electronics — predict demand
- **Export growth**: IT services, pharma, textiles — sector strength signals
- **Trade route disruption**: Red Sea/Suez issues → shipping costs → inflation

## AIS Shipping Data (Concept)

Automatic Identification System (AIS) tracks vessel positions globally. While real-time AIS data requires paid services (MarineTraffic, VesselFinder), the concept is valuable:

- **Oil tanker tracking**: Monitor crude oil shipments to predict supply
- **Container ship volumes**: Global trade activity proxy
- **Port congestion**: Supply chain bottleneck detection
- **Route changes**: Geopolitical risk indicator (ships avoiding conflict zones)

Free AIS data is available historically via research programs (e.g., MarineCadastre for US waters).

## Indian Port Activity

Key ports to monitor for trade signals:
- **JNPT (Mumbai)**: India's largest container port
- **Mundra**: Adani Ports — largest private port
- **Chennai**: Auto exports
- **Visakhapatnam**: Steel, coal imports
