from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

if __package__:
    from .config import DEFAULT_SPLITS, SUMMARY_DIR, get_split_config, resolve_split_name
    from .dataset import Pose2DDataset
else:
    from config import DEFAULT_SPLITS, SUMMARY_DIR, get_split_config, resolve_split_name
    from dataset import Pose2DDataset


def _print_dataset_summary(summary: Dict[str, object]) -> None:
    split = summary["split"]
    source = summary["bbox_source"]
    print(f"[{split} | {source}]")
    print(f"  annotation file       : {summary['annotation_file']}")
    print(f"  image dir             : {summary['image_dir']}")
    print(f"  declared images       : {summary['declared_images']}")
    print(f"  loaded records        : {summary['records']}")
    print(f"  unique images used    : {summary['unique_images_with_records']}")
    print(f"  orphan source items   : {summary['orphan_source_items']}")
    print(f"  missing image files   : {summary['missing_image_files']}")
    if source == "gt":
        print(f"  mean visible keypoint : {summary['mean_visible_keypoints']}")

    first_record = summary.get("first_record")
    if first_record:
        print(f"  first image           : {first_record['image_path']}")
    print()


def inspect_split(split: str) -> Dict[str, object]:
    normalized_split = resolve_split_name(split)
    split_config = get_split_config(normalized_split)

    gt_dataset = Pose2DDataset(normalized_split, bbox_source="gt")
    det_dataset = Pose2DDataset(normalized_split, bbox_source="det")

    gt_summary = gt_dataset.summary()
    det_summary = det_dataset.summary()

    _print_dataset_summary(gt_summary)
    _print_dataset_summary(det_summary)

    return {
        "split": normalized_split,
        "paths": {
            "annotation_file": str(split_config.annotation_file),
            "image_dir": str(split_config.image_dir),
            "detection_file": str(split_config.detection_file),
        },
        "gt": gt_summary,
        "det": det_summary,
    }


def build_report(splits: List[str]) -> Dict[str, object]:
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "splits": [inspect_split(split) for split in splits],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the local pose_2d dataset scaffold.")
    parser.add_argument(
        "--splits",
        nargs="+",
        default=list(DEFAULT_SPLITS),
        help="Splits to inspect. Examples: train valid test valid_100",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=SUMMARY_DIR / "dataset_report.json",
        help="Where to save the JSON report.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if missing image files or orphan items are found.",
    )
    args = parser.parse_args()

    normalized_splits = [resolve_split_name(split) for split in args.splits]
    report = build_report(normalized_splits)

    args.report_path.parent.mkdir(parents=True, exist_ok=True)
    args.report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"JSON report saved to: {args.report_path}")

    if args.strict:
        has_error = False
        for split_report in report["splits"]:
            for source_key in ("gt", "det"):
                summary = split_report[source_key]
                if summary["missing_image_files"] > 0 or summary["orphan_source_items"] > 0:
                    has_error = True
        if has_error:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
