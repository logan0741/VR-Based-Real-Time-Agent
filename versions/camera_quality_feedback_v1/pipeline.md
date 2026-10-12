# Pipeline Notes

## Before

```text
viewer keypoints
-> normalize
-> rep detector
-> DTW/score
-> feedback
-> app score/reps/final samples
```

몸이 화면 밖으로 벗어나도 normalize/rep/score 경로에 들어갈 수 있었다.

## After

```text
viewer keypoints
-> camera visibility gate
   -> fail: feedback only, countable=false
   -> pass: normalize -> rep detector -> DTW/score -> feedback
-> app
   -> countable=false: message only
   -> countable=true: score/reps/final samples update
```

## Why

카메라가 전신을 잡지 못한 frame은 자세 품질 문제가 아니라 입력 품질 문제다. 따라서 운동 점수와 횟수에 섞이면 평가가 왜곡된다.
