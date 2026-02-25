# Materials Science API Reference

## GPAW — Density Functional Theory

### Calculator Setup

```python
from gpaw import GPAW, PW

calc = GPAW(
    mode=PW(ecut),       # Plane-wave mode; ecut in eV (default 340)
    xc='PBE',            # Exchange-correlation: LDA, PBE, RPBE, PBE0, HSE06
    kpts=(k1, k2, k3),   # Monkhorst-Pack k-point grid
    convergence={
        'energy': 0.0005,  # eV/electron
        'density': 1e-4,
        'eigenstates': 1e-8,
    },
    txt='gpaw.txt',       # Output file (None for no output)
    occupations={'name': 'fermi-dirac', 'width': 0.1},  # Smearing in eV
    symmetry='off',       # 'off' to disable symmetry
)
```

### Modes

- **PW(ecut)**: Plane-wave mode — most accurate for periodic systems
- **LCAO(...)**: Linear combination of atomic orbitals — faster, less accurate
- **FD(...)**: Finite difference — real-space grid

### Exchange-Correlation Functionals

| Functional | Type | Use Case |
|-----------|------|----------|
| LDA | Local | Quick estimates, testing |
| PBE | GGA | General-purpose, most common |
| RPBE | GGA | Surface adsorption energies |
| PBE0 | Hybrid | More accurate band gaps |
| HSE06 | Hybrid | Accurate band gaps, expensive |

### PAW Datasets

```bash
gpaw install-data ~/gpaw-datasets
export GPAW_SETUP_PATH=~/gpaw-datasets
```

### Band Structure

```python
from gpaw import GPAW, PW

# Step 1: Ground state
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
bs.plot(filename='bandstructure.png')
```

### Density of States

```python
from gpaw import GPAW, PW
from gpaw.dos import DOSCalculator

calc = GPAW(mode=PW(500), xc='PBE', kpts=(12, 12, 12), txt='dos.txt')
atoms.calc = calc
atoms.get_potential_energy()

dos_calc = DOSCalculator.from_calculator(calc)
energies, dos = dos_calc.get_dos()
```

---

## CHGNet — Universal ML Potential

### Calculator

```python
from chgnet.model.dynamics import CHGNetCalculator

calc = CHGNetCalculator()  # Uses pre-trained CHGNet model
atoms.calc = calc
energy = atoms.get_potential_energy()
forces = atoms.get_forces()
stress = atoms.get_stress()
```

### Relaxation

```python
from chgnet.model.dynamics import CHGNetCalculator
from ase.optimize import BFGS
from ase.constraints import ExpCellFilter

atoms.calc = CHGNetCalculator()
ecf = ExpCellFilter(atoms)  # Allow cell relaxation
opt = BFGS(ecf, trajectory='relax.traj')
opt.run(fmax=0.05)
```

### Molecular Dynamics

```python
from chgnet.model.dynamics import CHGNetCalculator
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase.md.langevin import Langevin
from ase import units

atoms.calc = CHGNetCalculator()
MaxwellBoltzmannDistribution(atoms, temperature_K=300)
dyn = Langevin(atoms, timestep=1 * units.fs, temperature_K=300, friction=0.01)
dyn.run(steps=1000)
```

---

## MACE — Equivariant ML Potential

### Foundation Models

```python
from mace.calculators import mace_mp

# Pre-trained models: "small", "medium", "large"
calc = mace_mp(model="medium", default_dtype="float64")
atoms.calc = calc
```

### Custom Models

```python
from mace.calculators import MACECalculator

calc = MACECalculator(model_paths="path/to/model.pt", default_dtype="float64")
```

---

## ASE — Atomistic Simulation Environment

### Atoms Object

```python
from ase import Atoms
from ase.io import read, write

# Read structure
atoms = read("POSCAR")           # VASP format
atoms = read("structure.cif")    # CIF format

# Write structure
write("output.cif", atoms)
write("POSCAR", atoms, format="vasp")
```

### Optimizers

| Optimizer | Description | Use Case |
|-----------|-------------|----------|
| BFGS | Quasi-Newton | General purpose, most common |
| LBFGS | Limited-memory BFGS | Large systems |
| FIRE | Fast inertial relaxation | Difficult convergence |

```python
from ase.optimize import BFGS, LBFGS, FIRE

opt = BFGS(atoms, trajectory='opt.traj', logfile='opt.log')
opt.run(fmax=0.05)  # Force convergence in eV/Å
```

### Cell Optimization

```python
from ase.constraints import ExpCellFilter, StrainFilter

# Full cell + positions
ecf = ExpCellFilter(atoms)
opt = BFGS(ecf)
opt.run(fmax=0.05)

# Cell only (fixed fractional coordinates)
sf = StrainFilter(atoms)
opt = BFGS(sf)
opt.run(fmax=0.05)
```

### Molecular Dynamics

```python
from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
from ase.md.verlet import VelocityVerlet
from ase.md.langevin import Langevin
from ase import units

# NVE ensemble
MaxwellBoltzmannDistribution(atoms, temperature_K=300)
dyn = VelocityVerlet(atoms, timestep=1 * units.fs)
dyn.run(steps=1000)

# NVT ensemble (Langevin thermostat)
dyn = Langevin(atoms, timestep=1 * units.fs, temperature_K=300, friction=0.01)
dyn.run(steps=1000)
```

### Constraints

```python
from ase.constraints import FixAtoms, FixBondLength

# Fix bottom layer atoms
constraint = FixAtoms(indices=[0, 1, 2, 3])
atoms.set_constraint(constraint)
```
