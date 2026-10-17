"""
Run the whole barangay pipeline, steps 1 to 5, in order.

HOW TO RUN: open this file and press VS Code's Run button, or from the
project root:
    python -m scripts.pipeline.run_all

Safe to run again at any time. Every step keeps the work already done:
coordinates, climate and soil are only fetched for new barangays, and
the database step updates rows instead of duplicating them. If a step
fails (for example the climate service drops the connection), the run
stops there with the step's own message. Run this file again and it
carries on.
"""

# Lets the file run with VS Code's Run button (python path/to/file.py)
# as well as with python -m scripts....: puts the project root on the
# path, and imports `scripts` so .env is loaded before the app is.
if __package__ in (None, ""):
    import os as _os, sys as _sys
    _sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(
        _os.path.abspath(__file__)))))
    import scripts  # noqa: F401

import runpy
import sys
import time

STEPS = [
    ("1/5 map points", "scripts.pipeline.make_coords"),
    ("2/5 elevation", "scripts.pipeline.get_elevation"),
    ("3/5 climate", "scripts.pipeline.get_climate"),
    ("4/5 soil", "scripts.pipeline.get_soil"),
    ("5/5 write to the database", "scripts.pipeline.seed_reference_data"),
]


def main():
    started = time.time()
    for label, module in STEPS:
        print(f"\n========== Step {label} ==========\n", flush=True)
        # each step reads its own command-line options; give it none
        sys.argv = [module]
        try:
            runpy.run_module(module, run_name="__main__")
        except SystemExit as e:
            if e.code not in (None, 0):
                print(f"\nStopped at step {label}: {e.code}")
                print("Run this file again to carry on from there.")
                sys.exit(1)
        except Exception as e:
            print(f"\nStopped at step {label}: {type(e).__name__}: {e}")
            print("Run this file again to carry on from there.")
            sys.exit(1)

    minutes = (time.time() - started) / 60
    print(f"\nAll 5 steps done in {minutes:.1f} minutes.")


if __name__ == "__main__":
    main()
