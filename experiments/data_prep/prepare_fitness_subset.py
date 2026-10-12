from __future__ import annotations

import argparse
import io
import json
import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List, Tuple


BYTES_PER_GB = 1000 ** 3


@dataclass
class GroupStats:
    bytes: int = 0
    files: int = 0
    json_2d: int = 0
    json_3d: int = 0
    label_bytes: int = 0


def discover_dataset_root(cwd: Path) -> Path:
    candidates = sorted(path for path in cwd.iterdir() if path.is_dir() and path.name.startswith("013."))
    if not candidates:
        raise FileNotFoundError("Could not find the fitness dataset root directory.")
    return candidates[0]


def discover_training_dirs(dataset_root: Path) -> Tuple[Path, Path]:
    training_dir = next(path for path in dataset_root.iterdir() if path.is_dir() and "Training" in path.name)
    raw_dir = next(path for path in training_dir.iterdir() if path.is_dir() and any(p.name.endswith(".tar") or ".tar." in p.name for p in path.iterdir()))
    label_dir = next(path for path in training_dir.iterdir() if path.is_dir() and any(p.suffix.lower() == ".zip" for p in path.iterdir()))
    return raw_dir, label_dir


def analyze_raw_groups(raw_archive: Path) -> Tuple[str, Dict[str, GroupStats]]:
    day_name = ""
    groups: Dict[str, GroupStats] = {}
    with tarfile.open(raw_archive, "r") as tar:
        for member in tar:
            parts = [part for part in PurePosixPath(member.name).parts if part not in ("", ".")]
            if len(parts) < 2:
                continue
            if not day_name:
                day_name = parts[0]
            group_id = parts[1]
            stats = groups.setdefault(group_id, GroupStats())
            if member.isfile():
                stats.bytes += member.size
                stats.files += 1
    if not day_name:
        raise RuntimeError(f"No members found in raw archive: {raw_archive}")
    return day_name, groups


def find_matching_inner_zip(label_outer_zip: Path, day_name: str) -> Tuple[str, bytes]:
    with zipfile.ZipFile(label_outer_zip, "r") as outer_zip:
        inner_names = sorted(name for name in outer_zip.namelist() if name.lower().endswith(".zip"))
        for inner_name in inner_names:
            inner_bytes = outer_zip.read(inner_name)
            with zipfile.ZipFile(io.BytesIO(inner_bytes), "r") as inner_zip:
                day_names = {
                    PurePosixPath(name).parts[0]
                    for name in inner_zip.namelist()
                    if len(PurePosixPath(name).parts) >= 2
                }
            if day_name in day_names:
                return inner_name, inner_bytes
    raise RuntimeError(f"Could not find an inner label zip containing {day_name}.")


def analyze_label_groups(inner_zip_bytes: bytes) -> Dict[str, GroupStats]:
    groups: Dict[str, GroupStats] = {}
    with zipfile.ZipFile(io.BytesIO(inner_zip_bytes), "r") as inner_zip:
        for name in inner_zip.namelist():
            if not name.lower().endswith(".json"):
                continue
            base_name = PurePosixPath(name).name
            parts = base_name.split("-")
            if len(parts) < 3:
                continue
            group_id = parts[1]
            stats = groups.setdefault(group_id, GroupStats())
            if base_name.endswith("-3d.json"):
                stats.json_3d += 1
            else:
                stats.json_2d += 1
            stats.label_bytes += inner_zip.getinfo(name).file_size
    return groups


def select_groups(
    raw_groups: Dict[str, GroupStats],
    label_groups: Dict[str, GroupStats],
    target_raw_bytes: int,
    min_groups: int,
    val_groups: int,
) -> Tuple[List[str], List[str], Dict[str, object]]:
    common = sorted(set(raw_groups) & set(label_groups), key=lambda item: int(item))
    if not common:
        raise RuntimeError("No overlapping raw/label groups were found.")

    max_label_count = max(min(label_groups[group].json_2d, label_groups[group].json_3d) for group in common)
    candidates = [
        group
        for group in common
        if label_groups[group].json_2d == max_label_count and label_groups[group].json_3d == max_label_count
    ]
    candidates.sort(key=lambda group: (raw_groups[group].bytes, int(group)))

    selected: List[str] = []
    selected_bytes = 0
    for group in candidates:
        group_bytes = raw_groups[group].bytes
        if selected_bytes + group_bytes <= target_raw_bytes or len(selected) < min_groups:
            selected.append(group)
            selected_bytes += group_bytes

    if len(selected) < min_groups:
        raise RuntimeError("Could not reach the requested minimum group count.")
    if len(selected) <= val_groups:
        raise RuntimeError("Validation group count leaves no training data.")

    selected.sort(key=lambda item: int(item))
    validation = selected[-val_groups:]
    training = selected[:-val_groups]
    analysis = {
        "candidate_groups": candidates,
        "max_label_count_per_group": max_label_count,
        "selected_groups": selected,
        "selected_raw_bytes": selected_bytes,
    }
    return training, validation, analysis


def ensure_safe_output_path(destination_root: Path, relative_parts: Iterable[str]) -> Path:
    relative_path = Path(*relative_parts)
    target_path = (destination_root / relative_path).resolve()
    root_path = destination_root.resolve()
    try:
        target_path.relative_to(root_path)
    except ValueError as exc:
        raise RuntimeError(f"Unsafe output path detected: {target_path}") from exc
    return target_path


def extract_raw_subset(
    raw_archive: Path,
    day_name: str,
    train_groups: List[str],
    val_groups: List[str],
    train_root: Path,
    val_root: Path,
) -> Dict[str, Dict[str, int]]:
    split_stats = {
        "train": {"bytes": 0, "files": 0},
        "val": {"bytes": 0, "files": 0},
    }
    train_set = set(train_groups)
    val_set = set(val_groups)

    with tarfile.open(raw_archive, "r") as tar:
        for member in tar:
            parts = [part for part in PurePosixPath(member.name).parts if part not in ("", ".")]
            if len(parts) < 2 or parts[0] != day_name:
                continue
            group_id = parts[1]
            split_name = ""
            destination_root: Path | None = None
            if group_id in train_set:
                split_name = "train"
                destination_root = train_root
            elif group_id in val_set:
                split_name = "val"
                destination_root = val_root
            if destination_root is None:
                continue

            target_path = ensure_safe_output_path(destination_root, parts)
            if member.isdir():
                target_path.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            source = tar.extractfile(member)
            if source is None:
                continue
            with source, target_path.open("wb") as output_file:
                shutil.copyfileobj(source, output_file, length=1024 * 1024)
            split_stats[split_name]["bytes"] += member.size
            split_stats[split_name]["files"] += 1

    return split_stats


def extract_label_subset(
    inner_zip_bytes: bytes,
    day_name: str,
    train_groups: List[str],
    val_groups: List[str],
    train_root: Path,
    val_root: Path,
) -> Dict[str, Dict[str, int]]:
    split_stats = {
        "train": {"bytes": 0, "files": 0},
        "val": {"bytes": 0, "files": 0},
    }
    train_set = set(train_groups)
    val_set = set(val_groups)

    with zipfile.ZipFile(io.BytesIO(inner_zip_bytes), "r") as inner_zip:
        for info in inner_zip.infolist():
            if info.is_dir() or not info.filename.lower().endswith(".json"):
                continue
            parts = [part for part in PurePosixPath(info.filename).parts if part not in ("", ".")]
            if len(parts) < 2 or parts[0] != day_name:
                continue

            file_name = parts[-1]
            name_parts = file_name.split("-")
            if len(name_parts) < 3:
                continue
            group_id = name_parts[1]

            split_name = ""
            destination_root: Path | None = None
            if group_id in train_set:
                split_name = "train"
                destination_root = train_root
            elif group_id in val_set:
                split_name = "val"
                destination_root = val_root
            if destination_root is None:
                continue

            target_path = ensure_safe_output_path(destination_root, parts)
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with inner_zip.open(info, "r") as source, target_path.open("wb") as output_file:
                shutil.copyfileobj(source, output_file, length=1024 * 1024)
            split_stats[split_name]["bytes"] += info.file_size
            split_stats[split_name]["files"] += 1

    return split_stats


def count_files_and_bytes(root: Path) -> Dict[str, int]:
    stats = {"bytes": 0, "files": 0}
    for path in root.rglob("*"):
        if path.is_file():
            stats["bytes"] += path.stat().st_size
            stats["files"] += 1
    return stats


def write_summary(output_root: Path, summary: Dict[str, object]) -> None:
    summary_path = output_root / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Fitness Subset Summary",
        "",
        f"- Source raw archive: `{summary['source']['raw_archive']}`",
        f"- Source label archive: `{summary['source']['label_outer_zip']}`",
        f"- Source inner label zip: `{summary['source']['label_inner_zip']}`",
        f"- Day folder: `{summary['source']['day_name']}`",
        f"- Train groups: `{', '.join(summary['selection']['train_groups'])}`",
        f"- Val groups: `{', '.join(summary['selection']['val_groups'])}`",
        f"- Extracted raw total (GB): `{summary['totals']['raw_total_gb']}`",
        f"- Extracted label total (MB): `{summary['totals']['label_total_mb']}`",
        "",
        "See `summary.json` for detailed counts and byte sizes.",
    ]
    (output_root / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a compact train/val subset from the fitness pose dataset.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=None,
        help="Path to the dataset root. If omitted, the script auto-discovers the local 013.* directory.",
    )
    parser.add_argument(
        "--raw-archive",
        default="body_01.tar",
        help="Raw tar archive name to use.",
    )
    parser.add_argument(
        "--target-raw-gb",
        type=float,
        default=20.0,
        help="Target maximum raw extraction size in decimal GB.",
    )
    parser.add_argument(
        "--min-groups",
        type=int,
        default=3,
        help="Minimum number of groups to keep before splitting.",
    )
    parser.add_argument(
        "--val-groups",
        type=int,
        default=1,
        help="Number of groups reserved for validation.",
    )
    parser.add_argument(
        "--output-name",
        default="prepared_train_eval_body01_compact",
        help="Name of the output folder created under the dataset root.",
    )
    args = parser.parse_args()

    cwd = Path.cwd()
    dataset_root = args.dataset_root or discover_dataset_root(cwd)
    raw_dir, label_dir = discover_training_dirs(dataset_root)
    raw_archive = raw_dir / args.raw_archive
    if not raw_archive.exists():
        raise FileNotFoundError(f"Raw archive not found: {raw_archive}")

    label_outer_zip = max(
        (path for path in label_dir.iterdir() if path.suffix.lower() == ".zip"),
        key=lambda path: path.stat().st_size,
    )

    day_name, raw_groups = analyze_raw_groups(raw_archive)
    label_inner_name, label_inner_bytes = find_matching_inner_zip(label_outer_zip, day_name)
    label_groups = analyze_label_groups(label_inner_bytes)

    train_groups, val_groups, selection_analysis = select_groups(
        raw_groups=raw_groups,
        label_groups=label_groups,
        target_raw_bytes=int(args.target_raw_gb * BYTES_PER_GB),
        min_groups=args.min_groups,
        val_groups=args.val_groups,
    )

    output_root = dataset_root / args.output_name
    if output_root.exists():
        raise FileExistsError(f"Output directory already exists: {output_root}")

    raw_train_root = output_root / "raw" / "train"
    raw_val_root = output_root / "raw" / "val"
    label_train_root = output_root / "labels" / "train"
    label_val_root = output_root / "labels" / "val"
    for path in (raw_train_root, raw_val_root, label_train_root, label_val_root):
        path.mkdir(parents=True, exist_ok=True)

    raw_split_stats = extract_raw_subset(
        raw_archive=raw_archive,
        day_name=day_name,
        train_groups=train_groups,
        val_groups=val_groups,
        train_root=raw_train_root,
        val_root=raw_val_root,
    )
    label_split_stats = extract_label_subset(
        inner_zip_bytes=label_inner_bytes,
        day_name=day_name,
        train_groups=train_groups,
        val_groups=val_groups,
        train_root=label_train_root,
        val_root=label_val_root,
    )

    raw_total = count_files_and_bytes(output_root / "raw")
    label_total = count_files_and_bytes(output_root / "labels")

    summary = {
        "source": {
            "dataset_root": str(dataset_root),
            "raw_archive": str(raw_archive),
            "label_outer_zip": str(label_outer_zip),
            "label_inner_zip": label_inner_name,
            "day_name": day_name,
        },
        "selection": {
            "train_groups": train_groups,
            "val_groups": val_groups,
            "candidate_groups": selection_analysis["candidate_groups"],
            "selected_groups": selection_analysis["selected_groups"],
            "max_label_count_per_group": selection_analysis["max_label_count_per_group"],
        },
        "group_stats": {
            group: {
                "raw_bytes": raw_groups[group].bytes,
                "raw_files": raw_groups[group].files,
                "label_json_2d": label_groups[group].json_2d,
                "label_json_3d": label_groups[group].json_3d,
                "label_bytes": label_groups[group].label_bytes,
            }
            for group in selection_analysis["selected_groups"]
        },
        "extracted": {
            "raw": raw_split_stats,
            "labels": label_split_stats,
        },
        "totals": {
            "raw_total_bytes": raw_total["bytes"],
            "raw_total_gb": round(raw_total["bytes"] / BYTES_PER_GB, 3),
            "raw_total_files": raw_total["files"],
            "label_total_bytes": label_total["bytes"],
            "label_total_mb": round(label_total["bytes"] / (1000 ** 2), 3),
            "label_total_files": label_total["files"],
        },
    }
    write_summary(output_root, summary)

    print(f"Prepared dataset root: {output_root}")
    print(f"Train groups: {', '.join(train_groups)}")
    print(f"Val groups: {', '.join(val_groups)}")
    print(f"Raw total: {summary['totals']['raw_total_gb']} GB")
    print(f"Labels total: {summary['totals']['label_total_mb']} MB")


if __name__ == "__main__":
    main()
