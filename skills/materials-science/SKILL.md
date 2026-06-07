---
name: materials-science
description: Computational materials science with GPAW (DFT), CHGNet (universal ML potential), MACE (equivariant ML), and ASE (atomistic simulations). Use for ground-state DFT, geometry optimization, band structure, DOS, molecular dynamics, equation of state, and high-throughput screening.
license: Apache-2.0 license
metadata:
    skill-author: K-Dense Inc.
---

# Materials Science

Computational materials science toolkit combining density functional theory (DFT) and machine learning interatomic potentials.

## Installation

```bash
uv pip install gpaw chgnet mace-torch ase pymatgen
```

For GPAW PAW datasets:
```bash
gpaw install-data ~/gpaw-datasets
```

## When to Use

- **DFT calculations**: Ground state energy, electronic structure, band structure, DOS
- **Geometry optimization**: Relax atomic positions and cell parameters
- **Molecular dynamics**: Finite-temperature simulations
- **Equation of state**: Bulk modulus, equilibrium volume
- **High-throughput screening**: Fast ML-based screening of many structures
- **Surface energy**: Slab calculations for surface properties

## Related Skills

- **materialsexplorer** — Fetch crystal structures from OpenMaterialsDB as input
- **matplotlib** / **plotly** — Visualize band structures, DOS, EOS curves

## Calculator Decision Guide

| Calculator | Speed | Accuracy | Best For |
|-----------|-------|----------|----------|
| **GPAW** | Slow | High (DFT) | Publication-quality results, electronic structure |
| **CHGNet** | Fast | Good (ML) | Screening, relaxation, MD of bulk materials |
| **MACE** | Fast | High (ML) | Accurate ML predictions, molecules and materials |

## Quick Start

### Ground State DFT with GPAW

```python
from ase.io import read
from gpaw import GPAW, PW

atoms = read("POSCAR")
calc = GPAW(mode=PW(500), xc='PBE', kpts=(4, 4, 4), txt='gpaw.txt')
atoms.calc = calc
energy = atoms.get_potential_energy()
print(f"Total energy: {energy:.4f} eV")
```

### Fast Relaxation with CHGNet

```python
from ase.io import read
from chgnet.model.dynamics import CHGNetCalculator
from ase.optimize import BFGS

atoms = read("POSCAR")
atoms.calc = CHGNetCalculator()
opt = BFGS(atoms, trajectory='relax.traj')
opt.run(fmax=0.05)
```

### Relaxation with MACE

```python
from ase.io import read
from mace.calculators import mace_mp
from ase.optimize import BFGS

atoms = read("POSCAR")
atoms.calc = mace_mp(model="medium", default_dtype="float64")
opt = BFGS(atoms, trajectory='relax.traj')
opt.run(fmax=0.05)
```

## CLI Usage

```bash
# DFT ground state
python scripts/dft_calculations.py --task ground_state --structure POSCAR --xc PBE --kpoints 4 4 4

# Band structure
python scripts/dft_calculations.py --task band_structure --structure POSCAR

# ML relaxation
python scripts/ml_potentials.py --task relax --calculator chgnet --structure POSCAR

# Molecular dynamics
python scripts/ml_potentials.py --task md --calculator mace --structure POSCAR --temperature 300 --steps 1000

# Equation of state
python scripts/equation_of_state.py --structure POSCAR --calculator chgnet
```
