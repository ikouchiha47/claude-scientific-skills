#!/usr/bin/env python3
"""
Machine learning interatomic potential calculations.

Fast relaxation, molecular dynamics, and calculator comparison using
CHGNet and MACE ML potentials.

Usage:
    python ml_potentials.py --task relax --calculator chgnet --structure POSCAR
    python ml_potentials.py --task md --calculator mace --structure POSCAR --temperature 300 --steps 1000
    python ml_potentials.py --task compare --structure POSCAR
"""

import argparse
import json
import time

try:
    from ase.io import read, write
    from ase import units
except ImportError:
    print("Error: ASE not installed. Install with: uv pip install ase")
    raise SystemExit(1)


def _get_calculator(name):
    """Get an ASE calculator by name."""
    if name == "chgnet":
        from chgnet.model.dynamics import CHGNetCalculator
        return CHGNetCalculator()
    elif name == "mace":
        from mace.calculators import mace_mp
        return mace_mp(model="medium", default_dtype="float64")
    else:
        raise ValueError(f"Unknown calculator: {name}")


def relax_with_chgnet(structure_file, fmax=0.05):
    """
    Relax a structure using CHGNet universal ML potential.

    Args:
        structure_file: Path to structure file.
        fmax: Force convergence criterion in eV/Å.

    Returns:
        Dict with relaxed energy and structure info.
    """
    from ase.optimize import BFGS
    from ase.constraints import ExpCellFilter

    atoms = read(structure_file)
    atoms.calc = _get_calculator("chgnet")

    ecf = ExpCellFilter(atoms)
    opt = BFGS(ecf, trajectory="chgnet_relax.traj", logfile="chgnet_relax.log")
    opt.run(fmax=fmax)

    write("POSCAR_chgnet_relaxed", atoms, format="vasp")

    result = {
        "calculator": "chgnet",
        "energy_eV": atoms.get_potential_energy(),
        "energy_per_atom_eV": atoms.get_potential_energy() / len(atoms),
        "max_force_eV_per_A": float(abs(atoms.get_forces()).max()),
        "volume_A3": atoms.get_volume(),
        "n_steps": opt.nsteps,
    }
    print(json.dumps(result, indent=2))
    return result


def relax_with_mace(structure_file, fmax=0.05):
    """
    Relax a structure using MACE equivariant ML potential.

    Args:
        structure_file: Path to structure file.
        fmax: Force convergence criterion in eV/Å.

    Returns:
        Dict with relaxed energy and structure info.
    """
    from ase.optimize import BFGS
    from ase.constraints import ExpCellFilter

    atoms = read(structure_file)
    atoms.calc = _get_calculator("mace")

    ecf = ExpCellFilter(atoms)
    opt = BFGS(ecf, trajectory="mace_relax.traj", logfile="mace_relax.log")
    opt.run(fmax=fmax)

    write("POSCAR_mace_relaxed", atoms, format="vasp")

    result = {
        "calculator": "mace",
        "energy_eV": atoms.get_potential_energy(),
        "energy_per_atom_eV": atoms.get_potential_energy() / len(atoms),
        "max_force_eV_per_A": float(abs(atoms.get_forces()).max()),
        "volume_A3": atoms.get_volume(),
        "n_steps": opt.nsteps,
    }
    print(json.dumps(result, indent=2))
    return result


def run_md(structure_file, calculator="chgnet", temperature=300, steps=1000,
           timestep=1.0, supercell=None):
    """
    Run molecular dynamics simulation.

    Args:
        structure_file: Path to structure file.
        calculator: Calculator name ('chgnet' or 'mace').
        temperature: Temperature in Kelvin.
        steps: Number of MD steps.
        timestep: Timestep in femtoseconds.
        supercell: Supercell repetition as tuple, e.g. (2,2,2).

    Returns:
        Dict with MD simulation summary.
    """
    from ase.md.velocitydistribution import MaxwellBoltzmannDistribution
    from ase.md.langevin import Langevin
    from ase.io.trajectory import Trajectory

    atoms = read(structure_file)
    if supercell:
        atoms = atoms.repeat(supercell)

    atoms.calc = _get_calculator(calculator)
    MaxwellBoltzmannDistribution(atoms, temperature_K=temperature)

    dyn = Langevin(
        atoms,
        timestep=timestep * units.fs,
        temperature_K=temperature,
        friction=0.01,
    )

    traj = Trajectory("md.traj", "w", atoms)
    dyn.attach(traj.write, interval=10)

    energies = []

    def collect():
        e = atoms.get_potential_energy()
        T = atoms.get_kinetic_energy() / (1.5 * units.kB * len(atoms))
        energies.append({"step": dyn.nsteps, "energy_eV": e, "temperature_K": float(T)})
        if dyn.nsteps % 100 == 0:
            print(f"Step {dyn.nsteps}: T={T:.1f} K, E={e:.4f} eV")

    dyn.attach(collect, interval=10)

    t0 = time.time()
    dyn.run(steps=steps)
    elapsed = time.time() - t0

    result = {
        "calculator": calculator,
        "n_atoms": len(atoms),
        "temperature_K": temperature,
        "steps": steps,
        "elapsed_s": elapsed,
        "final_energy_eV": energies[-1]["energy_eV"],
        "final_temperature_K": energies[-1]["temperature_K"],
    }
    print(json.dumps(result, indent=2))
    return result


def compare_calculators(structure_file):
    """
    Compare energies and forces from different calculators on the same structure.

    Args:
        structure_file: Path to structure file.

    Returns:
        Dict with comparison results.
    """
    atoms_ref = read(structure_file)
    results = {}

    calculators = {"chgnet": "chgnet", "mace": "mace"}

    for name, calc_name in calculators.items():
        atoms = atoms_ref.copy()
        try:
            atoms.calc = _get_calculator(calc_name)
            t0 = time.time()
            energy = atoms.get_potential_energy()
            forces = atoms.get_forces()
            elapsed = time.time() - t0

            results[name] = {
                "energy_eV": energy,
                "energy_per_atom_eV": energy / len(atoms),
                "max_force_eV_per_A": float(abs(forces).max()),
                "mean_force_eV_per_A": float(abs(forces).mean()),
                "time_s": elapsed,
            }
        except Exception as e:
            results[name] = {"error": str(e)}

    print(json.dumps(results, indent=2))
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="ML potential calculations with CHGNet and MACE"
    )
    parser.add_argument(
        "--task",
        required=True,
        choices=["relax", "md", "compare"],
        help="Task to perform",
    )
    parser.add_argument("--structure", required=True, help="Path to structure file")
    parser.add_argument(
        "--calculator",
        default="chgnet",
        choices=["chgnet", "mace"],
        help="ML calculator (default: chgnet)",
    )
    parser.add_argument(
        "--temperature", type=float, default=300, help="MD temperature in K (default: 300)"
    )
    parser.add_argument(
        "--steps", type=int, default=1000, help="MD steps (default: 1000)"
    )
    parser.add_argument(
        "--fmax", type=float, default=0.05, help="Force convergence in eV/Å (default: 0.05)"
    )
    args = parser.parse_args()

    if args.task == "relax":
        if args.calculator == "chgnet":
            relax_with_chgnet(args.structure, fmax=args.fmax)
        else:
            relax_with_mace(args.structure, fmax=args.fmax)
    elif args.task == "md":
        run_md(
            args.structure,
            calculator=args.calculator,
            temperature=args.temperature,
            steps=args.steps,
        )
    elif args.task == "compare":
        compare_calculators(args.structure)
