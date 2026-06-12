# Pipeline Notes

## Feedback Event Pipeline

```text
FeedbackEngine analyzes current frame
-> FeedbackPolicy.consider()
   -> accept new event: feedback_event=true
   -> hold current event: feedback_event=false
-> server sends visible feedback every frame
-> app shows message every frame
-> app stores logs/final samples only when feedback_event=true
```

## Mirror Pipeline

```text
App button
-> userMirror state
-> SkeletonCanvas2D mirror prop
-> normalizeToCanvas flips x coordinate
```

## Scoring

This version intentionally keeps original scoring strictness. It solves repeated feedback accumulation separately from scoring.
