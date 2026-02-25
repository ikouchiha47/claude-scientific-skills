#!/usr/bin/env python3
"""
Fetch crystal structures from Materials DB and OpenMaterialsDB.

Materials DB (https://materials-db.fly.dev) — 145K Materials Project entries.
OpenMaterialsDB (https://openmaterialsdb.se) — 205K+ materials.

Usage:
    # Materials DB
    python fetch_materials.py --mpdb-search --formula "LiCoO2"
    python fetch_materials.py --mpdb-search --elements Li Co O
    python fetch_materials.py --mpdb-search --bandgap-min 1.0 --bandgap-max 3.0
    python fetch_materials.py --mpdb-get mp-149

    # OpenMaterialsDB
    python fetch_materials.py --search "NaCl"
    python fetch_materials.py --search "+Na +Cl"
    python fetch_materials.py --compound 101
    python fetch_materials.py --download 201 --output-dir /tmp/structures
"""

import argparse
import json
import re
import time
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: Required packages not installed.")
    print("Install with: uv pip install requests beautifulsoup4")
    raise SystemExit(1)

MPDB_BASE_URL = "https://materials-db.fly.dev"
BASE_URL = "https://openmaterialsdb.se"


# ---------------------------------------------------------------------------
# Materials DB API (https://materials-db.fly.dev)
# ---------------------------------------------------------------------------

def mpdb_search(formula=None, elements=None, chemical_system=None,
                bandgap_min=None, bandgap_max=None, limit=20, cursor=None):
    """
    Search Materials DB for materials.

    Args:
        formula: Chemical formula (exact or prefix match, e.g. "LiCoO2" or "Li").
        elements: List of elements — materials containing ALL listed elements.
        chemical_system: List of elements — materials with ONLY these elements (subset).
        bandgap_min: Minimum bandgap in eV.
        bandgap_max: Maximum bandgap in eV.
        limit: Max results per page (default 20, max 50).
        cursor: Pagination cursor from previous response.

    Returns:
        Dict with keys: materials (list), next_cursor (str or None), total (int).
        Each material has: material_id, formula, bandgap, etc.
    """
    payload = {}
    if formula is not None:
        payload["formula"] = formula
    if elements is not None:
        payload["elements"] = elements
    if chemical_system is not None:
        payload["chemical_system"] = chemical_system
    if bandgap_min is not None:
        payload["bandgap_min"] = bandgap_min
    if bandgap_max is not None:
        payload["bandgap_max"] = bandgap_max
    if limit != 20:
        payload["limit"] = limit
    if cursor is not None:
        payload["cursor"] = cursor

    response = requests.post(
        f"{MPDB_BASE_URL}/api/search",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def mpdb_get_material(material_id, include_structure=False):
    """
    Get a material by its Materials Project ID.

    Args:
        material_id: MP ID (e.g. "mp-149").
        include_structure: If True, include lattice and sites in response.

    Returns:
        Dict with material metadata and optionally structure data.
    """
    params = {}
    if include_structure:
        params["include"] = "structure"

    response = requests.get(
        f"{MPDB_BASE_URL}/api/material/{material_id}",
        params=params,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def mpdb_stats():
    """Get Materials DB statistics (material count, task count, etc.)."""
    response = requests.get(f"{MPDB_BASE_URL}/api/stats", timeout=10)
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# OpenMaterialsDB API (https://openmaterialsdb.se)
# ---------------------------------------------------------------------------


def search_materials(query):
    """
    Search OpenMaterialsDB for materials matching a query.

    Args:
        query: Search string — formula (e.g. "NaCl"), name (e.g. "Silicon"),
               or species query (e.g. "+Na +Cl" for contains, "#Ca #O" for exact).

    Returns:
        List of dicts with keys: formula, compound_cid, name, spacegroup.
    """
    response = requests.post(
        f"{BASE_URL}/search",
        data={"query": query},
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    rows = soup.find_all("tr")
    for row in rows:
        links = row.find_all("a")
        compound_cid = None
        formula = ""
        for link in links:
            href = link.get("href", "")
            match = re.search(r"/compound/(\d+)/([^/\"']+)", href)
            if match:
                compound_cid = match.group(1)
                formula = match.group(2)
                break

        if compound_cid is None:
            continue

        cells = row.find_all("td")
        name = ""
        spacegroup = ""
        if len(cells) >= 3:
            name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
            spacegroup = cells[-1].get_text(strip=True)

        results.append({
            "formula": formula,
            "compound_cid": compound_cid,
            "name": name,
            "spacegroup": spacegroup,
        })

    return results


def get_compound_details(compound_cid, formula=""):
    """
    Get details for a specific compound from OpenMaterialsDB.

    Args:
        compound_cid: Compound ID from search results.
        formula: Chemical formula (used in URL construction).

    Returns:
        Dict with keys: compound_cid, formula, vasp_sids, structure_info.
    """
    url = f"{BASE_URL}/compound/{compound_cid}/{formula}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    vasp_sids = []
    for link in soup.find_all("a", href=True):
        href = link["href"]
        match = re.search(r"vasp_sid=(\d+)", href)
        if match:
            sid = match.group(1)
            if sid not in vasp_sids:
                vasp_sids.append(sid)

    return {
        "compound_cid": compound_cid,
        "formula": formula,
        "vasp_sids": vasp_sids,
        "structure_info": soup.title.string if soup.title else "",
    }


def download_poscar(vasp_sid, output_dir="."):
    """
    Download a POSCAR file from OpenMaterialsDB.

    Args:
        vasp_sid: VASP structure ID.
        output_dir: Directory to save the file.

    Returns:
        Path to the downloaded POSCAR file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    url = f"{BASE_URL}/download"
    response = requests.get(url, params={"vasp_sid": vasp_sid}, timeout=30)
    response.raise_for_status()

    output_path = output_dir / f"POSCAR_{vasp_sid}"
    output_path.write_text(response.text)
    print(f"Downloaded: {output_path}")
    return output_path


def to_pymatgen_structure(poscar_path):
    """
    Convert a POSCAR file to a pymatgen Structure object.

    Args:
        poscar_path: Path to a POSCAR file.

    Returns:
        pymatgen Structure object, or None if parsing fails.
    """
    try:
        from pymatgen.core import Structure
        return Structure.from_file(str(poscar_path))
    except ImportError:
        print("Error: pymatgen not installed. Install with: uv pip install pymatgen")
        return None
    except Exception as e:
        print(f"Error parsing {poscar_path}: {e}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch crystal structures from Materials DB and OpenMaterialsDB"
    )

    # Materials DB arguments
    mpdb_group = parser.add_argument_group("Materials DB (materials-db.fly.dev)")
    mpdb_group.add_argument(
        "--mpdb-search",
        action="store_true",
        help="Search Materials DB",
    )
    mpdb_group.add_argument(
        "--mpdb-get",
        help="Get material by MP ID (e.g. mp-149)",
    )
    mpdb_group.add_argument(
        "--formula",
        help="Formula for Materials DB search (exact or prefix)",
    )
    mpdb_group.add_argument(
        "--elements",
        nargs="+",
        help="Elements filter (materials containing ALL listed elements)",
    )
    mpdb_group.add_argument(
        "--chemical-system",
        nargs="+",
        help="Chemical system (materials with ONLY these elements)",
    )
    mpdb_group.add_argument(
        "--bandgap-min",
        type=float,
        help="Minimum bandgap in eV",
    )
    mpdb_group.add_argument(
        "--bandgap-max",
        type=float,
        help="Maximum bandgap in eV",
    )

    # OpenMaterialsDB arguments
    omdb_group = parser.add_argument_group("OpenMaterialsDB (openmaterialsdb.se)")
    omdb_group.add_argument(
        "--search",
        help="Search query (formula, name, or species like '+Na +Cl')",
    )
    omdb_group.add_argument(
        "--compound",
        help="Get details for a compound by its ID",
    )
    omdb_group.add_argument(
        "--download",
        help="Download POSCAR by VASP structure ID",
    )

    parser.add_argument(
        "--output-dir",
        default=".",
        help="Output directory for downloads (default: current directory)",
    )
    args = parser.parse_args()

    if args.mpdb_search:
        data = mpdb_search(
            formula=args.formula,
            elements=args.elements,
            chemical_system=args.chemical_system,
            bandgap_min=args.bandgap_min,
            bandgap_max=args.bandgap_max,
        )
        materials = data.get("materials", [])
        if not materials:
            print("No results found.")
        else:
            print(f"Found {len(materials)} result(s):")
            for m in materials:
                bg = m.get("bandgap")
                bg_str = f", bandgap={bg:.3f} eV" if bg is not None else ""
                print(f"  {m.get('material_id', '?')} — {m.get('formula', '?')}{bg_str}")
            if data.get("next_cursor"):
                print(f"\nMore results available (cursor: {data['next_cursor']})")

    elif args.mpdb_get:
        material = mpdb_get_material(args.mpdb_get, include_structure=True)
        print(json.dumps(material, indent=2))

    elif args.search:
        results = search_materials(args.search)
        if not results:
            print("No results found.")
        else:
            print(f"Found {len(results)} result(s):")
            for r in results:
                print(
                    f"  {r['formula']} — cid={r['compound_cid']}, "
                    f"spacegroup={r['spacegroup']}, name={r['name']}"
                )

    elif args.compound:
        details = get_compound_details(args.compound)
        print(json.dumps(details, indent=2))

    elif args.download:
        download_poscar(args.download, output_dir=args.output_dir)

    else:
        parser.print_help()
