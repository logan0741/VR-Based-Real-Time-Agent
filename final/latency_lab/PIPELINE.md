# Latency Pipeline

```text
sample_coco17_keypoints.json
  -> synthetic viewer sender
  -> /ws/pose
  -> immediate relay broadcast
  -> app receiver latency sample
  -> backend processing result
  -> app receiver processed sample
  -> JSON/MD report
```

The relay sample represents live skeleton latency. The processed sample
represents feedback/score/reps latency.
