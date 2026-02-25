# Materials Science Workflows

## Workflow 1: Ground State DFT with GPAW

```python
from ase.io import read
from gpaw import GPAW, PW

atoms = read("POSCAR")
calc = GPAW(
    mode=PW(500),
    xc='PBE',
    kpts=(8, 8, 8),
    convergence={'energy': 0.0005},
    txt='ground_state.txt',
)
atoms.calc = calc
energy = atoms.get_potential_energy()
forces = atoms.get_forces()
stress = atoms.get_stress()

print(f"Energy: {energy:.4f} eV")
print(f"Max force: {abs(forces).max():.4f} eV/Å")

calc.write('ground_state.gpw')
```

## Workflow 2: Geometry Optimization — Calculator Comparison

```python
from ase.io import read
from ase.optimize import BFGS
from ase.constraints import ExpCellFilter
import time

structure_file = "POSCAR"

# GPAW (DFT)
atoms = read(structure_file)
from gpaw import GPAW, PW
atoms.calc = GPAW(mode=PW(400), xc='PBE', kpts=(4, 4, 4), txt=None)
ecf = ExpCellFilter(atoms)
t0 = time.time()
BFGS(ecf).run(fmax=0.05)
print(f"GPAW: E={atoms.get_potential_energy():.4f} eV, time={time.time()-t0:.1f}s")

# CHGNet (ML)
atoms = read(structure_file)
from chgnet.model.dynamics import CHGNetCalculator
atoms.calc = CHGNetCalculator()
ecf = ExpCellFilter(atoms)
t0 = time.time()
BFGS(ecf).run(fmax=0.05)
print(f"CHGNet: E={atoms.get_potential_energy():.4f} eV, time={time.time()-t0:.1f}s")

# MACE (ML)
atoms = read(structure_file)
from mace.calculators import mace_mp
atoms.calc = mace_mp(model="medium", default_dtype="float64")
ecf = ExpCellFilter(atoms)
t0 = time.time()
BFGS(ecf).run(fmax=0.05)
print(f"MACE: E={atoms.get_potential_energy():.4f} eV, time={time.time()-t0:.1f}s")
```

## Workflow 3: Band Structure + DOS with GPAW

```python
from ase.io import read
from gpaw import GPAW, PW
from gpaw.dos import DOSCalculator

atoms = read("POSCAR")

# Step 1: Self-consistent ground state
calc = GPAW(mode=PW(500), xc='PBE', kpts=(8, 8, 8), txt='gs.txt')
atoms.calc = calc
atoms.get_potential_energy()
calc.write('gs.gpw')

# Step 2: Band structure (non-self-consistent)
calc = GPAW('gs.gpw').fixed_density(
    kpts={'path': 'GXWLGK', 'npoints': 100},
    symmetry='off',
)
bs = calc.band_structure()
bs.plot(filename='bandstructure.png', emin=-10, emax=10)

# Step 3: DOS
calc = GPAW('gs.gpw').fixed_density(kpts=(12, 12, 12))
atoms.calc = calc
atoms.get_potential_energy()
dos_calc = DOSCalculator.from_calculator(calc)
energies, dos = dos_calc.get_dos()

import matplotlib.pyplot as plt
plt.plot(energies, dos)
plt.xlabel('Energy (eV)')
plt.ylabel('DOS (states/eV)')
plt.savefig('dos.png', dpi=150)
```

## Workflow 4: Molecular Dynamics with CHGNet/MACE

```python
from ase.io import read
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase.md.langevin import Langevin
from ase.io.trajectory import Trajectory
from ase import units

atoms = read("POSCAR")
atoms = atoms.repeat((2, 2, 2))  # Create supercell for MD

# Choose calculator
from chgnet.model.dynamics import CHGNetCalculator
atoms.calc = CHGNetCalculator()

# Initialize velocities
MaxwellBoltzmannDistribution(atoms, temperature_K=300)

# Langevin dynamics (NVT)
dyn = Langevin(atoms, timestep=1 * units.fs, temperature_K=300, friction=0.01)
traj = Trajectory('md.traj', 'w', atoms)
dyn.attach(traj.write, interval=10)

def print_status():
    T = atoms.get_kinetic_energy() / (1.5 * units.kB * len(atoms))
    print(f"Step {dyn.nsteps}: T={T:.1f} K, E={atoms.get_potential_energy():.4f} eV")

dyn.attach(print_status, interval=100)
dyn.run(steps=1000)
```

## Workflow 5: Equation of State / Bulk Modulus

```python
from ase.io import read
from ase.eos import EquationOfState
import numpy as np

atoms = read("POSCAR")

# Choose calculator
from chgnet.model.dynamics import CHGNetCalculator
atoms.calc = CHGNetCalculator()

# Vary volume
cell = atoms.get_cell()
volumes = []
energies = []

for scale in np.linspace(0.95, 1.05, 9):
    a = atoms.copy()
    a.set_cell(cell * scale, scale_atoms=True)
    a.calc = CHGNetCalculator()
    e = a.get_potential_energy()
    volumes.append(a.get_volume())
    energies.append(e)
    print(f"scale={scale:.3f}, V={volumes[-1]:.2f} Å³, E={e:.4f} eV")

eos = EquationOfState(volumes, energies, eos='birchmurnaghan')
v0, e0, B = eos.fit()
print(f"\nEquilibrium volume: {v0:.2f} Å³")
print(f"Bulk modulus: {B / units.kJ * 1e24:.1f} GPa")
eos.plot(filename='eos.png')
```

## Workflow 6: Surface Energy Calculation

```python
from ase.io import read
from ase.build import surface, add_vacuum
from ase.optimize import BFGS
from ase.constraints import FixAtoms

# Build slab
slab = surface(read("POSCAR"), (1, 1, 1), layers=6, vacuum=10.0)

# Fix bottom half
z_positions = slab.positions[:, 2]
z_mid = (z_positions.max() + z_positions.min()) / 2
fixed = [i for i, z in enumerate(z_positions) if z < z_mid]
slab.set_constraint(FixAtoms(indices=fixed))

# Calculate
from chgnet.model.dynamics import CHGNetCalculator
slab.calc = CHGNetCalculator()
opt = BFGS(slab)
opt.run(fmax=0.05)

E_slab = slab.get_potential_energy()
n_layers = 6
# Surface energy = (E_slab - n_bulk * E_bulk) / (2 * A)
```

## Workflow 7: High-Throughput Screening with ML Potentials

```python
from ase.io import read
from pathlib import Path
from chgnet.model.dynamics import CHGNetCalculator
from ase.optimize import BFGS
from ase.constraints import ExpCellFilter

structures_dir = Path("./structures")
results = []

for poscar in sorted(structures_dir.glob("POSCAR_*")):
    atoms = read(str(poscar))
    atoms.calc = CHGNetCalculator()

    ecf = ExpCellFilter(atoms)
    opt = BFGS(ecf, logfile=None)
    opt.run(fmax=0.05, steps=200)

    energy_per_atom = atoms.get_potential_energy() / len(atoms)
    results.append({
        "file": poscar.name,
        "formula": atoms.get_chemical_formula(),
        "energy_per_atom": energy_per_atom,
        "volume": atoms.get_volume(),
    })
    print(f"{poscar.name}: {energy_per_atom:.4f} eV/atom")

# Sort by stability
results.sort(key=lambda x: x["energy_per_atom"])
print("\nMost stable structures:")
for r in results[:5]:
    print(f"  {r['formula']}: {r['energy_per_atom']:.4f} eV/atom")
```

## Workflow 8: MaterialsExplorer → Materials Science Pipeline

```python
import sys
from pathlib import Path

# Fetch structures using materialsexplorer
sys.path.insert(0, str(Path("../materialsexplorer/scripts")))
from fetch_materials import search_materials, get_compound_details, download_poscar

results = search_materials("TiO2")
details = get_compound_details(results[0]["compound_cid"], results[0]["formula"])
poscar_path = download_poscar(details["vasp_sids"][0], output_dir="./downloaded")

# Run ML relaxation
from ase.io import read
from chgnet.model.dynamics import CHGNetCalculator
from ase.optimize import BFGS
from ase.constraints import ExpCellFilter

atoms = read(str(poscar_path))
atoms.calc = CHGNetCalculator()
ecf = ExpCellFilter(atoms)
opt = BFGS(ecf, trajectory="tio2_relax.traj")
opt.run(fmax=0.05)

print(f"Relaxed energy: {atoms.get_potential_energy():.4f} eV")
print(f"Energy/atom: {atoms.get_potential_energy() / len(atoms):.4f} eV/atom")
```
