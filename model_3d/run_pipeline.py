"""Backward-compatible wrapper for the model_3d CLI pipeline runner.

`pipeline.py` owns the reusable frame-processing engine.
`pipeline_cli.py` owns command-line execution, QA checks, and local workflows.
This file stays as the user-facing entrypoint because existing commands and docs
already call `python model_3d/run_pipeline.py`.
"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from model_3d.pipeline_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
