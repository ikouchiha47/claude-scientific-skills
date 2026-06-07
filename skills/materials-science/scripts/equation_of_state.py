#!/usr/bin/env python3
"""
Equation of state and bulk modulus calculations.

Fit Birch-Murnaghan equation of state to energy-volume data to determine
equilibrium volume, bulk modulus, and pressure derivative.

Usage:
    python equation_of_state.py --structure POSCAR --calculator chgnet
    python equation_of_state.py --structure POSCAR --calculator mace --strain-range 0.08 --n-points 11
"""

import argparse
import json

import numpy as np

try:
    from ase.io import read
    from ase.eos import EquationOfState
    from ase import units
except ImportError:
    print("Error: ASE not installed. Install with: uv pip install ase")
    raise SystemExit(1)


def calculate_eos(structure_file, calculator="chgnet", strain_range=0.05,
                  n_points=9, eos_type="birchmurnaghan"):
    """
    Calculate equation of state by varying unit cell volume.

    Args:
        structure_file: Path to structure file.
        calculator: Calculator name — 'chgnet', 'mace', or 'gpaw'.
        strain_range: Maximum fractional strain (default: 0.05 = ±5%).
        n_points: Number of volume points (default: 9).
        eos_type: EOS model — 'birchmurnaghan', 'murnaghan', 'birch', 'vinet'.

    Returns:
        Dict with equilibrium volume, energy, and bulk modulus.
    """
    atoms = read(structure_file)
    cell = atoms.get_cell()

    # Set up calculator
    if calculator == "chgnet":
        from chgnet.model.dynamics import CHGNetCalculator
        make_calc = CHGNetCalculator
    elif calculator == "mace":
        from mace.calculators import mace_mp
        make_calc = lambda: mace_mp(model="medium", default_dtype="float64")
    elif calculator == "gpaw":
        from gpaw import GPAW, PW
        make_calc = lambda: GPAW(mode=PW(500), xc="PBE", kpts=(8, 8, 8), txt=None)
    else:
        print(f"Error: Unknown calculator '{calculator}'")
        raise SystemExit(1)

    scales = np.linspace(1 - strain_range, 1 + strain_range, n_points)
    volumes = []
    energies = []

    print(f"Calculating EOS with {calculator} ({n_points} points, ±{strain_range*100:.0f}% strain)")

    for i, scale in enumerate(scales):
        a = atoms.copy()
        a.set_cell(cell * scale, scale_atoms=True)
        a.calc = make_calc()
        e = a.get_potential_energy()
        v = a.get_volume()
        volumes.append(v)
        energies.append(e)
        print(f"  [{i+1}/{n_points}] scale={scale:.4f}, V={v:.2f} Å³, E={e:.4f} eV")

    # Fit EOS
    eos = EquationOfState(volumes, energies, eos=eos_type)
    v0, e0, B = eos.fit()

    # Convert bulk modulus to GPa
    B_GPa = B / units.kJ * 1e24

    result = {
        "formula": atoms.get_chemical_formula(),
        "calculator": calculator,
        "eos_type": eos_type,
        "equilibrium_volume_A3": float(v0),
        "equilibrium_energy_eV": float(e0),
        "bulk_modulus_GPa": float(B_GPa),
        "n_atoms": len(atoms),
        "volume_per_atom_A3": float(v0 / len(atoms)),
    }

    print(f"\nResults:")
    print(f"  Equilibrium volume: {v0:.2f} Å³")
    print(f"  Equilibrium energy: {e0:.4f} eV")
    print(f"  Bulk modulus: {B_GPa:.1f} GPa")

    # Plot
    try:
        eos.plot(filename="eos.png")
        print("  EOS plot saved to eos.png")
    except Exception:
        pass

    # Save raw data
    np.savetxt(
        "eos_data.dat",
        list(zip(volumes, energies)),
        header="Volume(Å³) Energy(eV)",
    )
    print("  Raw data saved to eos_data.dat")

    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Equation of state and bulk modulus calculation"
    )
    parser.add_argument("--structure", required=True, help="Path to structure file")
    parser.add_argument(
        "--calculator",
        default="chgnet",
        choices=["chgnet", "mace", "gpaw"],
        help="Calculator (default: chgnet)",
    )
    parser.add_argument(
        "--strain-range",
        type=float,
        default=0.05,
        help="Max fractional strain (default: 0.05)",
    )
    parser.add_argument(
        "--n-points",
        type=int,
        default=9,
        help="Number of volume points (default: 9)",
    )
    parser.add_argument(
        "--eos-type",
        default="birchmurnaghan",
        choices=["birchmurnaghan", "murnaghan", "birch", "vinet"],
        help="EOS model (default: birchmurnaghan)",
    )
    args = parser.parse_args()

    calculate_eos(
        args.structure,
        calculator=args.calculator,
        strain_range=args.strain_range,
        n_points=args.n_points,
        eos_type=args.eos_type,
    )
