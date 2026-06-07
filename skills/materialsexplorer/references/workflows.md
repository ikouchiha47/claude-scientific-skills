# MaterialsExplorer Workflows

## Workflow 1: Materials DB — Search and Retrieve Structure

Search the Materials DB JSON API (preferred for structured queries).

```python
from fetch_materials import mpdb_search, mpdb_get_material

# Search by formula
data = mpdb_search(formula="LiCoO2")
for m in data["materials"]:
    print(f"{m['material_id']}: {m['formula']}, bandgap={m.get('bandgap', 'N/A')} eV")

# Get full structure for a material
material = mpdb_get_material("mp-149", include_structure=True)
print(f"Formula: {material['formula']}")
print(f"Lattice: {material['structure']['lattice']}")
print(f"Sites: {len(material['structure']['sites'])} atoms")
```

## Workflow 2: Materials DB — Bandgap Screening

```python
from fetch_materials import mpdb_search

# Find semiconductors with bandgap 1-2 eV containing Li
data = mpdb_search(formula="Li", bandgap_min=1.0, bandgap_max=2.0)
for m in data["materials"]:
    print(f"{m['material_id']}: {m['formula']}, Eg={m['bandgap']:.3f} eV")
```

## Workflow 3: Materials DB — Chemical System Search

```python
from fetch_materials import mpdb_search

# Find all materials in the Li-Fe-O system
data = mpdb_search(chemical_system=["Li", "Fe", "O"])
for m in data["materials"]:
    print(f"{m['material_id']}: {m['formula']}")

# Paginate through results
cursor = data.get("next_cursor")
while cursor:
    data = mpdb_search(chemical_system=["Li", "Fe", "O"], cursor=cursor)
    for m in data["materials"]:
        print(f"{m['material_id']}: {m['formula']}")
    cursor = data.get("next_cursor")
```

## Workflow 4: OpenMaterialsDB — Search → Download → pymatgen Structure

Complete pipeline from search query to pymatgen Structure object.

```python
from fetch_materials import search_materials, get_compound_details, download_poscar, to_pymatgen_structure

# Step 1: Search
results = search_materials("+Ti +O")
print(f"Found {len(results)} compounds")

# Step 2: Get details for first result
details = get_compound_details(results[0]['compound_cid'], results[0]['formula'])

# Step 3: Download POSCAR
poscar_path = download_poscar(details['vasp_sids'][0], output_dir="./structures")

# Step 4: Convert to pymatgen
structure = to_pymatgen_structure(poscar_path)
print(f"Formula: {structure.composition.reduced_formula}")
print(f"Space group: {structure.get_space_group_info()}")
print(f"Volume: {structure.volume:.2f} Å³")
```

## Workflow 5: Batch Download All Structures for a Formula

```python
from batch_download import batch_download

# Download all TiO2 structures
metadata = batch_download("TiO2", output_dir="./tio2_structures")
print(f"Downloaded {len(metadata)} structures")

# metadata is a list of dicts with formula, compound_cid, vasp_sid, file_path
```

## Workflow 6: Composition Analysis

```python
from fetch_materials import search_materials, to_pymatgen_structure
from pymatgen.core import Composition

# Analyze composition
comp = Composition("Li2Fe2P2O8")
print(f"Reduced formula: {comp.reduced_formula}")
print(f"Elements: {[str(e) for e in comp.elements]}")
print(f"Weight: {comp.weight:.2f} g/mol")
print(f"Anonymous formula: {comp.anonymized_formula}")
```

## Workflow 7: Format Conversion

```python
from pymatgen.core import Structure

# Load POSCAR and convert to other formats
structure = Structure.from_file("POSCAR")

# To CIF
structure.to(filename="structure.cif")

# To JSON
structure.to(filename="structure.json")

# To POSCAR (with different name)
structure.to(filename="POSCAR_new", fmt="poscar")
```

## Workflow 8: Filter and Screen Materials

```python
from fetch_materials import search_materials, get_compound_details, download_poscar, to_pymatgen_structure

# Search for perovskites (ABO3 pattern)
results = search_materials("+Ca +Ti +O")

for r in results:
    details = get_compound_details(r['compound_cid'], r['formula'])
    if not details['vasp_sids']:
        continue
    poscar_path = download_poscar(details['vasp_sids'][0], output_dir="./screening")
    structure = to_pymatgen_structure(poscar_path)
    if structure is None:
        continue

    # Filter by number of atoms
    if len(structure) <= 20:
        print(f"{r['formula']}: {len(structure)} atoms, V={structure.volume:.1f} Å³")
```
