from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Tuple

if __package__:
    from .config import get_split_config, resolve_split_name
else:
    from config import get_split_config, resolve_split_name


Keypoint = Tuple[float, float, float]
BBox = Tuple[float, float, float, float]


@dataclass(frozen=True)
class Pose2DRecord:
    split: str
    sample_index: int
    image_id: int
    annotation_id: Optional[int]
    image_path: Path
    width: int
    height: int
    bbox: BBox
    bbox_source: str
    bbox_score: float
    keypoints: Tuple[Keypoint, ...]
    num_visible_keypoints: int
    area: float
    category_id: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "split": self.split,
            "sample_index": self.sample_index,
            "image_id": self.image_id,
            "annotation_id": self.annotation_id,
            "image_path": str(self.image_path),
            "width": self.width,
            "height": self.height,
            "bbox": list(self.bbox),
            "bbox_source": self.bbox_source,
            "bbox_score": self.bbox_score,
            "num_visible_keypoints": self.num_visible_keypoints,
            "area": self.area,
            "category_id": self.category_id,
            "keypoints": [list(kp) for kp in self.keypoints],
        }


def _reshape_keypoints(flat_keypoints: Sequence[float]) -> Tuple[Keypoint, ...]:
    if len(flat_keypoints) % 3 != 0:
        raise ValueError("Keypoints should be a flat list of x, y, visibility triples.")

    triplets: List[Keypoint] = []
    for index in range(0, len(flat_keypoints), 3):
        x_coord = float(flat_keypoints[index])
        y_coord = float(flat_keypoints[index + 1])
        visibility = float(flat_keypoints[index + 2])
        triplets.append((x_coord, y_coord, visibility))
    return tuple(triplets)


def _count_visible_keypoints(keypoints: Sequence[Keypoint]) -> int:
    return sum(1 for _, _, visibility in keypoints if visibility > 0)


class Pose2DDataset:
    def __init__(self, split: str, bbox_source: str = "gt"):
        if bbox_source not in {"gt", "det"}:
            raise ValueError("bbox_source must be either 'gt' or 'det'.")

        self.split = resolve_split_name(split)
        self.bbox_source = bbox_source
        self.split_config = get_split_config(self.split)

        self.image_count = 0
        self.source_item_count = 0
        self.orphan_source_items = 0
        self.missing_image_files: List[str] = []
        self._missing_image_file_set = set()
        self.records = self._load_records()

    def _load_json(self, file_path: Path) -> Dict[str, object]:
        with file_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _load_records(self) -> List[Pose2DRecord]:
        coco = self._load_json(self.split_config.annotation_file)
        images = coco.get("images", [])
        image_by_id = {image["id"]: image for image in images}
        self.image_count = len(images)

        if self.bbox_source == "gt":
            raw_items = coco.get("annotations", [])
            return self._build_ground_truth_records(raw_items, image_by_id)

        with self.split_config.detection_file.open("r", encoding="utf-8") as file:
            raw_items = json.load(file)
        return self._build_detection_records(raw_items, image_by_id)

    def _build_ground_truth_records(
        self,
        annotations: Sequence[Dict[str, object]],
        image_by_id: Dict[int, Dict[str, object]],
    ) -> List[Pose2DRecord]:
        records: List[Pose2DRecord] = []
        self.source_item_count = len(annotations)

        for annotation in annotations:
            if int(annotation.get("category_id", 1)) != 1:
                continue

            image_id = int(annotation["image_id"])
            image_info = image_by_id.get(image_id)
            if image_info is None:
                self.orphan_source_items += 1
                continue

            image_path = self.split_config.image_dir / str(image_info["file_name"])
            self._register_missing_image(image_path)

            keypoints = _reshape_keypoints(annotation.get("keypoints", []))
            bbox = tuple(float(value) for value in annotation["bbox"])

            records.append(
                Pose2DRecord(
                    split=self.split,
                    sample_index=len(records),
                    image_id=image_id,
                    annotation_id=int(annotation["id"]),
                    image_path=image_path,
                    width=int(image_info["width"]),
                    height=int(image_info["height"]),
                    bbox=bbox,  # type: ignore[arg-type]
                    bbox_source="gt",
                    bbox_score=1.0,
                    keypoints=keypoints,
                    num_visible_keypoints=_count_visible_keypoints(keypoints),
                    area=float(annotation.get("area", bbox[2] * bbox[3])),
                    category_id=int(annotation.get("category_id", 1)),
                )
            )

        return records

    def _build_detection_records(
        self,
        detections: Sequence[Dict[str, object]],
        image_by_id: Dict[int, Dict[str, object]],
    ) -> List[Pose2DRecord]:
        records: List[Pose2DRecord] = []
        self.source_item_count = len(detections)

        empty_keypoints = tuple((0.0, 0.0, 0.0) for _ in range(17))

        for detection in detections:
            if int(detection.get("category_id", 1)) != 1:
                continue

            image_id = int(detection["image_id"])
            image_info = image_by_id.get(image_id)
            if image_info is None:
                self.orphan_source_items += 1
                continue

            image_path = self.split_config.image_dir / str(image_info["file_name"])
            self._register_missing_image(image_path)

            bbox = tuple(float(value) for value in detection["bbox"])
            records.append(
                Pose2DRecord(
                    split=self.split,
                    sample_index=len(records),
                    image_id=image_id,
                    annotation_id=None,
                    image_path=image_path,
                    width=int(image_info["width"]),
                    height=int(image_info["height"]),
                    bbox=bbox,  # type: ignore[arg-type]
                    bbox_source="det",
                    bbox_score=float(detection.get("score", 1.0)),
                    keypoints=empty_keypoints,
                    num_visible_keypoints=0,
                    area=float(bbox[2] * bbox[3]),
                    category_id=int(detection.get("category_id", 1)),
                )
            )

        return records

    def _register_missing_image(self, image_path: Path) -> None:
        if image_path.exists():
            return
        image_path_str = str(image_path)
        if image_path_str in self._missing_image_file_set:
            return
        self._missing_image_file_set.add(image_path_str)
        self.missing_image_files.append(image_path_str)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> Pose2DRecord:
        return self.records[index]

    def iter_batches(
        self,
        batch_size: int,
        shuffle: bool = False,
        seed: int = 42,
        drop_last: bool = False,
    ) -> Iterator[List[Pose2DRecord]]:
        if batch_size <= 0:
            raise ValueError("batch_size must be larger than 0.")

        indices = list(range(len(self.records)))
        if shuffle:
            random.Random(seed).shuffle(indices)

        for start in range(0, len(indices), batch_size):
            batch_indices = indices[start:start + batch_size]
            if drop_last and len(batch_indices) < batch_size:
                continue
            yield [self.records[index] for index in batch_indices]

    def summary(self) -> Dict[str, object]:
        unique_image_ids = len({record.image_id for record in self.records})
        visible_counts = [record.num_visible_keypoints for record in self.records if record.bbox_source == "gt"]
        mean_visible_keypoints = 0.0
        if visible_counts:
            mean_visible_keypoints = round(sum(visible_counts) / len(visible_counts), 2)

        return {
            "split": self.split,
            "bbox_source": self.bbox_source,
            "annotation_file": str(self.split_config.annotation_file),
            "image_dir": str(self.split_config.image_dir),
            "detection_file": str(self.split_config.detection_file),
            "declared_images": self.image_count,
            "records": len(self.records),
            "unique_images_with_records": unique_image_ids,
            "source_items": self.source_item_count,
            "orphan_source_items": self.orphan_source_items,
            "missing_image_files": len(self.missing_image_files),
            "mean_visible_keypoints": mean_visible_keypoints,
            "first_record": self.records[0].to_dict() if self.records else None,
        }
