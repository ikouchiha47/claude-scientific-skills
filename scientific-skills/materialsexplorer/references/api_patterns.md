# API Patterns

## Materials DB (preferred)

**Base URL**: `https://materials-db.fly.dev`

145K Materials Project relaxation trajectories (MPtrj dataset, CC-BY). Clean JSON API.

### Stats

```
GET /api/stats
```

Returns material count, task count, etc.

### Get Material by ID

```
GET /api/material/{material_id}
GET /api/material/{material_id}?include=structure
```

- `material_id`: MP ID, e.g. `mp-149`
- `include=structure`: adds lattice and sites to response

### Search (POST JSON)

```
POST /api/search
Content-Type: application/json

{
  "formula": "LiCoO2",           // exact or prefix match
  "elements": ["Li", "Co", "O"], // materials containing ALL elements
  "chemical_system": ["Li", "Fe", "O"],  // materials with ONLY these elements
  "bandgap_min": 1.0,            // minimum bandgap in eV
  "bandgap_max": 3.0,            // maximum bandgap in eV
  "limit": 20,                   // max 50
  "cursor": "12345"              // from previous response's next_cursor
}
```

All fields optional. Combine for filtered searches.

**Response**:
```json
{
  "materials": [
    {"material_id": "mp-149", "formula": "Si", "bandgap": 0.613, ...}
  ],
  "next_cursor": "12345",
  "total": 42
}
```

### Health Check

```
GET /health
```

---

## OpenMaterialsDB

**Base URL**: `https://openmaterialsdb.se`

HTML-based, requires BeautifulSoup parsing.

### Endpoints

### Search Materials (POST)

```
POST /search
Content-Type: multipart/form-data

Parameters:
  query: str  — search string (formula, name, or species query)
```

**Response**: HTML page containing a table of results. Parse with BeautifulSoup.

**Extractable fields from HTML response**:
- `compound_cid` — compound ID, extracted from links (`/compound/<cid>/<formula>`)
- `formula` — chemical formula
- `name` — material name (if available)
- `spacegroup` — space group symbol

### Compound Details (GET)

```
GET /compound/<compound_cid>/<formula>
```

**Response**: HTML page with compound details including VASP structure IDs.

**Extractable fields**:
- `vasp_sid` — VASP structure IDs, extracted from download links
- Crystal system, lattice parameters, atomic positions

### Download POSCAR (GET)

```
GET /download?vasp_sid=<vasp_sid>
```

**Response**: POSCAR file content (VASP format crystal structure).

## HTML Parsing Patterns

### Search Results Table

```python
from bs4 import BeautifulSoup

soup = BeautifulSoup(response.text, 'html.parser')
rows = soup.find_all('tr')
for row in rows:
    links = row.find_all('a')
    for link in links:
        href = link.get('href', '')
        if '/compound/' in href:
            parts = href.strip('/').split('/')
            compound_cid = parts[1]
            formula = parts[2] if len(parts) > 2 else ''
    cells = row.find_all('td')
    # Extract spacegroup, name from table cells
```

### Compound Page — Extract VASP SIDs

```python
soup = BeautifulSoup(response.text, 'html.parser')
links = soup.find_all('a', href=True)
vasp_sids = []
for link in links:
    href = link['href']
    if 'vasp_sid=' in href:
        sid = href.split('vasp_sid=')[-1].split('&')[0]
        vasp_sids.append(sid)
```

## Error Handling

- **No results**: Search returns HTML with empty table or "No results" message
- **Invalid compound_cid**: Returns 404 or redirect to search page
- **Invalid vasp_sid**: Returns empty response or error page
- **Rate limiting**: Add delays between requests (1-2 seconds recommended)
