# Fitness Pose Viewer For Unity

This folder is a Unity import scaffold, not a full Unity project.

## What It Does

- Loads a fitness pose sequence JSON exported from this repository.
- Plays the 3D pose as a joint-and-bone skeleton in Unity.
- Optionally shows the original RGB frame sequence as a background image.

## Included Script

- `Assets/Scripts/FitnessPoseSequencePlayer.cs`

## Export JSON From This Repo

Run this from the repository root:

```powershell
python -m model_3d.export_fitness_unity --split train val --limit 2 --view view1
```

Sample output:

```text
artifacts/unity_fitness_viewer/sequences/train/D05-1-001_view1.json
artifacts/unity_fitness_viewer/sequences/train/D05-1-002_view1.json
artifacts/unity_fitness_viewer/sequences/val/D05-4-001_view1.json
artifacts/unity_fitness_viewer/sequences/val/D05-4-002_view1.json
artifacts/unity_fitness_viewer/sequences/manifest.json
```

## Import Into Unity

1. Copy `Assets/Scripts/FitnessPoseSequencePlayer.cs` into your Unity project's `Assets/Scripts`.
2. Create an empty GameObject in the scene.
3. Attach `FitnessPoseSequencePlayer` to it.
4. Set `Sequence File Path` to one exported JSON file.

Example:

```text
C:\Project\VR-Based-Real-Time-Agent\artifacts\unity_fitness_viewer\sequences\train\D05-1-001_view1.json
```

5. Press Play.

## Optional Background Image Setup

If you want the original frame sequence in the scene:

1. Add a `Canvas` and a `RawImage`, then assign it to `Background Raw Image`.
2. Or add a Quad and assign its renderer to `Background Renderer`.
3. Leave `Image Root Path` empty if the exported JSON already contains valid absolute image paths.
4. If you move the dataset, set `Image Root Path` to the folder that contains the raw split.

Example image root:

```text
C:\Project\VR-Based-Real-Time-Agent\013.피트니스자세\prepared_train_eval_body01_compact\raw\train
```

## Notes

- The current viewer renders a procedural skeleton with spheres and cylinders.
- It does not include a skinned humanoid mesh or FBX avatar.
- If you want a full character mesh later, the stable next step is retargeting these joint sequences to a rigged Unity avatar.
