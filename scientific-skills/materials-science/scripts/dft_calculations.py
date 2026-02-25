#!/usr/bin/env python3
"""
DFT calculations using GPAW.

Run ground-state DFT, band structure, DOS, and geometry optimization
calculations on crystal structures.

Usage:
    python dft_calculations.py --task ground_state --structure POSCAR
    python dft_calculations.py --task band_structure --structure POSCAR
    python dft_calculations.py --task dos --structure POSCAR
    python dft_calculations.py --task optimize --structure POSCAR --calculator gpaw
"""

import argparse
import json

try:
    from ase.io import read, write
except ImportError:
    print("Error: ASE not installed. Install with: uv pip install ase")
    raise SystemExit(1)


def run_ground_state(structure_file, xc="PBE", kpts=(4, 4, 4), ecut=500):
    """
    Run a ground-state DFT calculation with GPAW.

    Args:
        structure_file: Path to structure file (POSCAR, CIF, etc.).
        xc: Exchange-correlation functional (LDA, PBE, RPBE, PBE0, HSE06).
        kpts: Monkhorst-Pack k-point grid as tuple.
        ecut: Plane-wave cutoff energy in eV.

    Returns:
        Dict with energy, forces, stress.
    """
    from gpaw import GPAW, PW

    atoms = read(structure_file)
    calc = GPAW(
        mode=PW(ecut),
        xc=xc,
        kpts=kpts,
        convergence={"energy": 0.0005},
        txt="ground_state.txt",
    )
    atoms.calc = calc
    energy = atoms.get_potential_energy()
    forces = atoms.get_forces()
    stress = atoms.get_stress()

    calc.write("ground_state.gpw")

    result = {
        "energy_eV": energy,
        "energy_per_atom_eV": energy / len(atoms),
        "max_force_eV_per_A": float(abs(forces).max()),
        "formula": atoms.get_chemical_formula(),
        "n_atoms": len(atoms),
    }
    print(json.dumps(result, indent=2))
    return result


def run_band_structure(structure_file, xc="PBE", kpts=(8, 8, 8), ecut=500):
    """
    Calculate band structure using GPAW.

    Args:
        structure_file: Path to structure file.
        xc: Exchange-correlation functional.
        kpts: K-point grid for ground state.
        ecut: Plane-wave cutoff in eV.
    """
    from gpaw import GPAW, PW

    atoms = read(structure_file)

    # Ground state
    calc = GPAW(mode=PW(ecut), xc=xc, kpts=kpts, txt="gs.txt")
    atoms.calc = calc
    atoms.get_potential_energy()
    calc.write("gs.gpw")

    # Band structure
    calc = GPAW("gs.gpw").fixed_density(
        kpts={"path": "GXWLGK", "npoints": 100},
        symmetry="off",
    )
    bs = calc.band_structure()
    bs.plot(filename="bandstructure.png", emin=-10, emax=10)
    print("Band structure saved to bandstructure.png")


def run_dos(structure_file, xc="PBE", kpts=(12, 12, 12), ecut=500):
    """
    Calculate density of states using GPAW.

    Args:
        structure_file: Path to structure file.
        xc: Exchange-correlation functional.
        kpts: K-point grid (use dense grid for DOS).
        ecut: Plane-wave cutoff in eV.
    """
    from gpaw import GPAW, PW
    from gpaw.dos import DOSCalculator

    atoms = read(structure_file)
    calc = GPAW(mode=PW(ecut), xc=xc, kpts=kpts, txt="dos.txt")
    atoms.calc = calc
    atoms.get_potential_energy()

    dos_calc = DOSCalculator.from_calculator(calc)
    energies, dos = dos_calc.get_dos()

    try:
        import matplotlib.pyplot as plt

        plt.figure(figsize=(8, 5))
        plt.plot(energies, dos, "b-")
        plt.xlabel("Energy (eV)")
        plt.ylabel("DOS (states/eV)")
        plt.title(f"Density of States — {atoms.get_chemical_formula()}")
        plt.axvline(x=0, color="k", linestyle="--", alpha=0.5, label="Fermi level")
        plt.legend()
        plt.tight_layout()
        plt.savefig("dos.png", dpi=150)
        print("DOS saved to dos.png")
    except ImportError:
        print("matplotlib not available; saving raw data instead")
        import numpy as np

        np.savetxt("dos.dat", list(zip(energies, dos)), header="Energy(eV) DOS(states/eV)")
        print("DOS data saved to dos.dat")


def run_geometry_optimization(structure_file, calculator="gpaw", xc="PBE",
                              kpts=(4, 4, 4), ecut=400, fmax=0.05):
    """
    Optimize geometry (atomic positions and cell).

    Args:
        structure_file: Path to structure file.
        calculator: Calculator to use — 'gpaw', 'chgnet', or 'mace'.
        xc: Exchange-correlation functional (GPAW only).
        kpts: K-point grid (GPAW only).
        ecut: Plane-wave cutoff in eV (GPAW only).
        fmax: Force convergence criterion in eV/Å.

    Returns:
        Dict with optimized energy and structure info.
    """
    from ase.optimize import BFGS
    from ase.constraints import ExpCellFilter

    atoms = read(structure_file)

    if calculator == "gpaw":
        from gpaw import GPAW, PW
        atoms.calc = GPAW(mode=PW(ecut), xc=xc, kpts=kpts, txt="opt.txt")
    elif calculator == "chgnet":
        from chgnet.model.dynamics import CHGNetCalculator
        atoms.calc = CHGNetCalculator()
    elif calculator == "mace":
        from mace.calculators import mace_mp
        atoms.calc = mace_mp(model="medium", default_dtype="float64")
    else:
        print(f"Error: Unknown calculator '{calculator}'")
        raise SystemExit(1)

    ecf = ExpCellFilter(atoms)
    opt = BFGS(ecf, trajectory="optimization.traj", logfile="optimization.log")
    opt.run(fmax=fmax)

    write("POSCAR_optimized", atoms, format="vasp")

    result = {
        "energy_eV": atoms.get_potential_energy(),
        "energy_per_atom_eV": atoms.get_potential_energy() / len(atoms),
        "max_force_eV_per_A": float(abs(atoms.get_forces()).max()),
        "volume_A3": atoms.get_volume(),
        "calculator": calculator,
    }
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DFT calculations with GPAW")
    parser.add_argument(
        "--task",
        required=True,
        choices=["ground_state", "band_structure", "dos", "optimize"],
        help="Calculation type",
    )
    parser.add_argument("--structure", required=True, help="Path to structure file")
    parser.add_argument(
        "--calculator",
        default="gpaw",
        choices=["gpaw", "chgnet", "mace"],
        help="Calculator for optimization (default: gpaw)",
    )
    parser.add_argument("--xc", default="PBE", help="XC functional (default: PBE)")
    parser.add_argument(
        "--kpoints",
        nargs=3,
        type=int,
        default=[4, 4, 4],
        help="K-point grid (default: 4 4 4)",
    )
    parser.add_argument(
        "--ecut", type=float, default=500, help="Plane-wave cutoff in eV (default: 500)"
    )
    parser.add_argument(
        "--fmax", type=float, default=0.05, help="Force convergence in eV/Å (default: 0.05)"
    )
    args = parser.parse_args()

    kpts = tuple(args.kpoints)

    if args.task == "ground_state":
        run_ground_state(args.structure, xc=args.xc, kpts=kpts, ecut=args.ecut)
    elif args.task == "band_structure":
        run_band_structure(args.structure, xc=args.xc, kpts=kpts, ecut=args.ecut)
    elif args.task == "dos":
        run_dos(args.structure, xc=args.xc, kpts=kpts, ecut=args.ecut)
    elif args.task == "optimize":
        run_geometry_optimization(
            args.structure,
            calculator=args.calculator,
            xc=args.xc,
            kpts=kpts,
            ecut=args.ecut,
            fmax=args.fmax,
        )
