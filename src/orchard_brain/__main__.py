"""Command-line demo for the orchard_brain package.

Run with::

    python -m src.orchard_brain --temperature 28.5 --humidity 55 --ec 200 --ph 6.3

or, once installed::

    orchard-brain --temperature 28.5 --humidity 55 --ec 200 --ph 6.3

By default prints the full explainable report.  Use ``--json`` for the
machine-readable ``BrainResult``.
"""
from __future__ import annotations

import argparse
import json

from .engine import OrchardBrain


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="orchard-brain",
        description="Explainable orchard intelligence engine for durian cultivation.",
    )
    parser.add_argument("--temperature", type=float, default=28.5, help="Air temperature (°C)")
    parser.add_argument("--humidity", type=float, default=55.0, help="Relative humidity / soil-moisture proxy (%%)")
    parser.add_argument("--ec", type=float, default=200.0, help="Fertigation EC (µS/cm)")
    parser.add_argument("--ph", type=float, default=6.3, help="Soil/water pH")
    parser.add_argument(
        "--soil-moisture",
        type=float,
        default=None,
        help="Measured soil volumetric water content (%%). If omitted, humidity is used as a proxy.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the machine-readable BrainResult instead of the text report.",
    )
    args = parser.parse_args(argv)

    brain = OrchardBrain()

    if args.json:
        result = brain.evaluate_raw(
            temperature=args.temperature,
            humidity=args.humidity,
            ec=args.ec,
            ph=args.ph,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(
            brain.evaluate_full_raw(
                temperature=args.temperature,
                humidity=args.humidity,
                ec=args.ec,
                ph=args.ph,
                soil_moisture=args.soil_moisture,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
