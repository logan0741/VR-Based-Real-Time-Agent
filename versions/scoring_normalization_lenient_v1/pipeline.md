# Pipeline Notes

## Existing Pipeline

```text
viewer MoveNet keypoints [y, x, confidence]
-> PoseNormalizer
   -> subtract hip/origin
   -> divide by shoulder-hip scale
   -> smooth origin/scale with buffer
-> DTW distance
-> ScoreEngine distance -> score
-> FeedbackEngine threshold -> message/bad_joints
```

## What Changed

```text
DTW distance is the same
Score conversion is softer
Feedback threshold is softer
```

This version does not change rep counting.

## Why Not Full Rotation Normalization Yet

Rotation normalization can improve fairness, but it can also distort exercises where torso lean or arm angle is the actual signal. It should be tested as a separate version after this lenient scoring version.
