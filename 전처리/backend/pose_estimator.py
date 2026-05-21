"""MoveNet Lightning 모델 로드 및 단일 프레임 관절 추출."""

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub

MOVENET_URL = "https://tfhub.dev/google/movenet/singlepose/lightning/4"
INPUT_SIZE = 192


class PoseEstimator:
    """MoveNet Lightning 기반 포즈 추정기."""

    def __init__(self) -> None:
        """인스턴스를 초기화한다. 모델은 load() 호출 시 로드된다."""
        self._model: hub.KerasLayer | None = None

    def load(self) -> None:
        """MoveNet Lightning 모델을 tensorflow-hub에서 1회 로드한다."""
        if self._model is not None:
            return
        module = hub.load(MOVENET_URL)
        self._model = module.signatures["serving_default"]

    def predict(self, frame: np.ndarray) -> np.ndarray:
        """단일 프레임에서 17개 관절 좌표를 추출한다. shape=(17,3), dtype=float32, 각 행=[y,x,conf]."""
        if self._model is None:
            raise RuntimeError("모델이 로드되지 않았습니다. load()를 먼저 호출하세요.")

        rgb: np.ndarray = frame[:, :, ::-1]
        tensor = tf.expand_dims(tf.cast(rgb, tf.int32), axis=0)
        tensor = tf.cast(tf.image.resize_with_pad(tensor, INPUT_SIZE, INPUT_SIZE), tf.int32)

        outputs = self._model(input=tensor)
        keypoints: np.ndarray = outputs["output_0"].numpy()[0, 0, :, :]
        return keypoints.astype(np.float32)
