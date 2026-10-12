"""MoveNet Lightning pose estimation wrapper."""

from pathlib import Path

import numpy as np
import tensorflow as tf
import tensorflow_hub as hub

MOVENET_URL = "https://tfhub.dev/google/movenet/singlepose/lightning/4"
LOCAL_MODEL_DIR = Path("movenet-tensorflow2-singlepose-lightning-v4")
INPUT_SIZE = 192


class PoseEstimator:
    """Load MoveNet and run single-person keypoint inference."""

    def __init__(self) -> None:
        self._model: object | None = None

    def load(self) -> None:
        """Load local SavedModel first, then fall back to TensorFlow Hub."""
        if self._model is not None:
            return

        if LOCAL_MODEL_DIR.exists():
            module = tf.saved_model.load(str(LOCAL_MODEL_DIR))
        else:
            module = hub.load(MOVENET_URL)
        self._model = module.signatures["serving_default"]

    def predict(self, frame: np.ndarray) -> np.ndarray:
        """Predict 17 keypoints as shape=(17, 3) in [y, x, confidence]."""
        if self._model is None:
            raise RuntimeError("Model is not loaded. Call load() first.")

        rgb: np.ndarray = frame[:, :, ::-1]
        tensor = tf.expand_dims(tf.cast(rgb, tf.int32), axis=0)
        tensor = tf.cast(tf.image.resize_with_pad(tensor, INPUT_SIZE, INPUT_SIZE), tf.int32)

        outputs = self._model(input=tensor)
        keypoints: np.ndarray = outputs["output_0"].numpy()[0, 0, :, :]
        return keypoints.astype(np.float32)
