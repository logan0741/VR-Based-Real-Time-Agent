from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

if __package__:
    from .config import RESULTS_DIR
    from .dataset import Pose2DDataset, Pose2DRecord
else:
    from config import RESULTS_DIR
    from dataset import Pose2DDataset, Pose2DRecord


def _record_preview(record: Pose2DRecord) -> Dict[str, object]:
    return {
        "sample_index": record.sample_index,
        "image_id": record.image_id,
        "image_path": str(record.image_path),
        "bbox": list(record.bbox),
        "bbox_source": record.bbox_source,
        "num_visible_keypoints": record.num_visible_keypoints,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Framework-agnostic pose_2d training loop scaffold.")
    parser.add_argument("--split", default="train", help="Dataset split to use.")
    parser.add_argument("--bbox-source", default="gt", choices=("gt", "det"))
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--max-batches", type=int, default=2)
    parser.add_argument("--shuffle", action="store_true")
    parser.add_argument(
        "--output-path",
        type=Path,
        default=RESULTS_DIR / "batch_preview.json",
        help="Where to save the preview JSON.",
    )
    args = parser.parse_args()

    dataset = Pose2DDataset(args.split, bbox_source=args.bbox_source)
    summary = dataset.summary()

    print(f"split        : {summary['split']}")
    print(f"bbox source  : {summary['bbox_source']}")
    print(f"record count : {summary['records']}")
    print(f"image count  : {summary['declared_images']}")
    print(f"missing imgs : {summary['missing_image_files']}")
    print()

    preview_batches: List[Dict[str, object]] = []
    for batch_index, batch in enumerate(
        dataset.iter_batches(args.batch_size, shuffle=args.shuffle),
        start=1,
    ):
        batch_preview = [_record_preview(record) for record in batch[: min(3, len(batch))]]
        preview_batches.append(
            {
                "batch_index": batch_index,
                "batch_size": len(batch),
                "preview_records": batch_preview,
            }
        )
        print(f"batch {batch_index}: {len(batch)} records")

        # Replace this block with model forward / loss / backward once the real trainer is ready.
        if batch_index >= args.max_batches:
            break

    payload = {
        "dataset_summary": summary,
        "preview_batches": preview_batches,
    }
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    args.output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"preview saved to: {args.output_path}")


if __name__ == "__main__":
    main()
