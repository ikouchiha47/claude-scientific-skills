---
name: materialsexplorer
description: Search and download crystal structures from Materials DB (145K Materials Project entries) and OpenMaterialsDB (205K+ materials). Use for finding materials by formula/elements/bandgap/chemical system, downloading structures, and converting to pymatgen Structure objects for computational analysis.
license: Apache-2.0 license
metadata:
    skill-author: K-Dense Inc.
---

# MaterialsExplorer

Search and download crystal structures from two databases:

1. **Materials DB** (`https://materials-db.fly.dev`) — 145K Materials Project relaxation trajectories (MPtrj dataset), JSON API with structured search by formula, elements, chemical system, and bandgap range
2. **OpenMaterialsDB** (`https://openmaterialsdb.se`) — 205K+ materials, HTML-based search by formula/name/species

**Prefer Materials DB** for structured queries (formula, elements, bandgap filtering, MP IDs). Use OpenMaterialsDB for name-based searches or when Materials DB lacks coverage.

## Installation

```bash
uv pip install pymatgen requests beautifulsoup4
```

## When to Use

- Finding crystal structures by chemical formula, elements, or bandgap range
- Looking up Materials Project entries by MP ID (e.g. `mp-149`)
- Downloading structures for DFT or ML potential calculations
- Screening materials by composition or electronic properties
- Building pymatgen Structure/Composition objects from database entries

## Data Sources

### Materials DB (preferred)

JSON REST API. Search by formula, elements, chemical system, bandgap range. Returns MP IDs, formula, bandgap, and full structure (lattice + sites).

```python
from fetch_materials import mpdb_search, mpdb_get_material

# Search by formula
results = mpdb_search(formula="LiCoO2")

# Search by elements (materials containing all listed elements)
results = mpdb_search(elements=["Li", "Co", "O"])

# Search by chemical system (materials with ONLY these elements)
results = mpdb_search(chemical_system=["Li", "Fe", "O"])

# Search by bandgap range
results = mpdb_search(bandgap_min=1.0, bandgap_max=3.0)

# Combined search
results = mpdb_search(formula="Li", bandgap_min=1.0, bandgap_max=3.0)

# Get material by MP ID (with structure)
material = mpdb_get_material("mp-149", include_structure=True)
```

### OpenMaterialsDB

HTML scraping. Search by formula, name, or species operators.

- **Contains species**: `+Na +Cl` — find materials containing Na and Cl
- **Exact species**: `#Ca #O` — find materials with exactly Ca and O
- **Formula**: `NaCl` or `SiO2` — search by chemical formula
- **Name**: `Silicon` — search by material name

```python
from fetch_materials import search_materials, get_compound_details, download_poscar, to_pymatgen_structure

results = search_materials("Silicon")
details = get_compound_details(results[0]['compound_cid'], results[0]['formula'])
poscar_path = download_poscar(details['vasp_sids'][0], output_dir="/tmp/structures")
structure = to_pymatgen_structure(poscar_path)
```

## CLI Usage

```bash
# Materials DB: search by formula
python scripts/fetch_materials.py --mpdb-search --formula "LiCoO2"

# Materials DB: search by elements
python scripts/fetch_materials.py --mpdb-search --elements Li Co O

# Materials DB: search by bandgap range
python scripts/fetch_materials.py --mpdb-search --bandgap-min 1.0 --bandgap-max 3.0

# Materials DB: get material by MP ID
python scripts/fetch_materials.py --mpdb-get mp-149

# OpenMaterialsDB: search
python scripts/fetch_materials.py --search "NaCl"

# OpenMaterialsDB: get compound details
python scripts/fetch_materials.py --compound 101

# OpenMaterialsDB: download POSCAR
python scripts/fetch_materials.py --download 201 --output-dir /tmp/structures

# Batch download all structures for a formula
python scripts/batch_download.py --formula "TiO2" --output-dir /tmp/tio2
```

## Integration

- Use with **materials-science** skill for DFT/ML calculations on downloaded structures
- Use with **matplotlib** or **plotly** skills to visualize structure properties
