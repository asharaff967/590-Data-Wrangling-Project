"""Shared immutable raw-run validation for stock builds and history audits.

Read the declared files only after checking the exact manifest file set. Source
checksums and row counts must agree before either stage uses a record.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .pull import raw_folder, sha256


def daily_file_names(start: str, end: str) -> list[str]:
    return [f"daily_{year}.csv" for year in range(int(start[:4]), int(end[:4]) + 1)]


def read_raw_run(root, start: str, end: str) -> tuple[Path, dict, dict[str, pd.DataFrame]]:
    """Validate a completed raw manifest, every saved checksum and every row count."""
    folder = raw_folder(root, start, end)
    manifest_path = folder / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing {manifest_path}; run stocks-pull first")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "complete":
        raise ValueError("Raw run is incomplete; inspect the pull error before building or auditing")
    if (manifest["start"], manifest["end"]) != (start, end):
        raise ValueError("Manifest dates do not match requested window")

    expected = {"seed_names.csv", "pilot_securities.csv", "names.csv", "membership.csv",
                *daily_file_names(start, end)}
    entries = manifest["files"]
    if len(entries) != len(expected) or {entry["name"] for entry in entries} != expected:
        raise ValueError("Manifest is missing required files or contains duplicates/unexpected files")

    frames = {}
    for entry in entries:
        path = folder / entry["name"]
        if sha256(path) != entry["sha256"]:
            raise ValueError(f"Raw checksum mismatch: {path}")
        frame = pd.read_csv(path)
        if len(frame) != entry["rows"]:
            raise ValueError(f"Raw row count mismatch: {path}")
        frames[entry["name"]] = frame
    return folder, manifest, frames


def daily_source_rows(frames: dict[str, pd.DataFrame], start: str, end: str) -> pd.DataFrame:
    """Concatenate annual files in year order, preserving CSV line provenance."""
    return pd.concat([
        frames[name].assign(source_file=name, source_row=range(2, len(frames[name]) + 2))
        for name in daily_file_names(start, end)
    ], ignore_index=True)
