using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using UnityEngine.UI;

[Serializable]
public class FitnessPoseSequence
{
    public int formatVersion;
    public string sequenceId;
    public string split;
    public string viewName;
    public float frameRate;
    public int frameCount;
    public float unitsPerMeter;
    public string coordinateSystem;
    public FitnessPoseVector3 rootReference;
    public float groundOffset;
    public string exerciseType;
    public string exerciseName;
    public string exerciseCategory;
    public string sourceLabel2D;
    public string sourceLabel3D;
    public string[] jointNames;
    public FitnessPoseBoneLink[] boneLinks;
    public FitnessPoseFrame[] frames;
}

[Serializable]
public class FitnessPoseBoneLink
{
    public string name;
    public int fromIndex;
    public int toIndex;
}

[Serializable]
public class FitnessPoseFrame
{
    public int index;
    public float timeSec;
    public string imagePath;
    public string imageRelativePath;
    public FitnessPoseVector3[] joints;
    public FitnessPoseVector2Confidence[] screenJoints;
    public float[] confidence;
}

[Serializable]
public class FitnessPoseVector3
{
    public float x;
    public float y;
    public float z;

    public Vector3 ToUnityVector()
    {
        return new Vector3(x, y, z);
    }
}

[Serializable]
public class FitnessPoseVector2Confidence
{
    public float x;
    public float y;
    public float confidence;
}

public class FitnessPoseSequencePlayer : MonoBehaviour
{
    [Header("Sequence Source")]
    public TextAsset sequenceJson;
    public string sequenceFilePath = "";

    [Header("Playback")]
    public bool playOnStart = true;
    public bool loop = true;
    public float playbackSpeed = 1.0f;

    [Header("Background Frames")]
    public bool showBackgroundFrames = true;
    public string imageRootPath = "";
    public RawImage backgroundRawImage;
    public Renderer backgroundRenderer;

    [Header("Skeleton")]
    public float jointRadius = 0.03f;
    public float boneRadius = 0.012f;
    public Material jointMaterial;
    public Material boneMaterial;

    private FitnessPoseSequence _sequence;
    private Transform[] _jointTransforms;
    private Transform[] _boneTransforms;
    private FitnessPoseBoneLink[] _boneLinks;
    private readonly Dictionary<string, Texture2D> _textureCache = new Dictionary<string, Texture2D>();
    private Transform _skeletonRoot;
    private float _playbackTime;
    private int _currentFrameIndex = -1;
    private bool _isPlaying;

    private void Start()
    {
        LoadSequence();
        if (_sequence == null || _sequence.frames == null || _sequence.frames.Length == 0)
        {
            Debug.LogError("FitnessPoseSequencePlayer could not load a sequence.");
            return;
        }

        BuildSkeleton();
        ApplyFrame(0);

        if (playOnStart)
        {
            Play();
        }
    }

    private void Update()
    {
        if (!_isPlaying || _sequence == null || _sequence.frames == null || _sequence.frames.Length == 0)
        {
            return;
        }

        _playbackTime += Time.deltaTime * Mathf.Max(0.0f, playbackSpeed);
        int frameIndex = Mathf.FloorToInt(_playbackTime * Mathf.Max(0.001f, _sequence.frameRate));
        if (loop)
        {
            frameIndex %= _sequence.frames.Length;
        }
        else if (frameIndex >= _sequence.frames.Length)
        {
            frameIndex = _sequence.frames.Length - 1;
            _isPlaying = false;
        }

        if (frameIndex != _currentFrameIndex)
        {
            ApplyFrame(frameIndex);
        }
    }

    [ContextMenu("Load Sequence")]
    public void LoadSequence()
    {
        string json = GetSequenceJson();
        if (string.IsNullOrWhiteSpace(json))
        {
            Debug.LogError("No sequence JSON was provided.");
            return;
        }

        _sequence = JsonUtility.FromJson<FitnessPoseSequence>(json);
        if (_sequence == null)
        {
            Debug.LogError("Failed to parse fitness pose sequence JSON.");
        }
    }

    public void Play()
    {
        _isPlaying = true;
    }

    public void Pause()
    {
        _isPlaying = false;
    }

    public void Stop()
    {
        _isPlaying = false;
        _playbackTime = 0.0f;
        ApplyFrame(0);
    }

    public void SetFrame(int frameIndex)
    {
        Pause();
        ApplyFrame(frameIndex);
    }

    private string GetSequenceJson()
    {
        if (sequenceJson != null)
        {
            return sequenceJson.text;
        }

        if (string.IsNullOrWhiteSpace(sequenceFilePath))
        {
            return string.Empty;
        }

        string resolvedPath = ResolveFilePath(sequenceFilePath);
        if (!File.Exists(resolvedPath))
        {
            Debug.LogError($"Sequence JSON file was not found: {resolvedPath}");
            return string.Empty;
        }

        return File.ReadAllText(resolvedPath);
    }

    private void BuildSkeleton()
    {
        if (_skeletonRoot != null)
        {
            DestroyImmediate(_skeletonRoot.gameObject);
        }

        _skeletonRoot = new GameObject("FitnessPoseSkeleton").transform;
        _skeletonRoot.SetParent(transform, false);

        string[] jointNames = _sequence.jointNames ?? Array.Empty<string>();
        _jointTransforms = new Transform[jointNames.Length];
        for (int index = 0; index < jointNames.Length; index++)
        {
            GameObject jointObject = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            jointObject.name = $"Joint_{index:D2}_{jointNames[index]}";
            jointObject.transform.SetParent(_skeletonRoot, false);
            jointObject.transform.localScale = Vector3.one * Mathf.Max(0.0001f, jointRadius * 2.0f);
            ApplyMaterial(jointObject, jointMaterial);
            _jointTransforms[index] = jointObject.transform;
        }

        _boneLinks = _sequence.boneLinks ?? Array.Empty<FitnessPoseBoneLink>();
        _boneTransforms = new Transform[_boneLinks.Length];
        for (int index = 0; index < _boneLinks.Length; index++)
        {
            GameObject boneObject = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            boneObject.name = $"Bone_{index:D2}_{_boneLinks[index].name}";
            boneObject.transform.SetParent(_skeletonRoot, false);
            ApplyMaterial(boneObject, boneMaterial);
            _boneTransforms[index] = boneObject.transform;
        }
    }

    private void ApplyFrame(int frameIndex)
    {
        if (_sequence == null || _sequence.frames == null || _sequence.frames.Length == 0)
        {
            return;
        }

        frameIndex = Mathf.Clamp(frameIndex, 0, _sequence.frames.Length - 1);
        _currentFrameIndex = frameIndex;
        _playbackTime = frameIndex / Mathf.Max(0.001f, _sequence.frameRate);

        FitnessPoseFrame frame = _sequence.frames[frameIndex];
        if (frame.joints == null || _jointTransforms == null)
        {
            return;
        }

        int jointCount = Mathf.Min(frame.joints.Length, _jointTransforms.Length);
        for (int index = 0; index < jointCount; index++)
        {
            _jointTransforms[index].localPosition = frame.joints[index].ToUnityVector();
        }

        for (int index = 0; index < _boneLinks.Length; index++)
        {
            FitnessPoseBoneLink link = _boneLinks[index];
            if (link.fromIndex < 0 || link.fromIndex >= jointCount || link.toIndex < 0 || link.toIndex >= jointCount)
            {
                continue;
            }
            UpdateBoneTransform(
                _boneTransforms[index],
                _jointTransforms[link.fromIndex].localPosition,
                _jointTransforms[link.toIndex].localPosition
            );
        }

        if (showBackgroundFrames)
        {
            ApplyBackgroundFrame(frame);
        }
    }

    private void UpdateBoneTransform(Transform boneTransform, Vector3 start, Vector3 end)
    {
        Vector3 direction = end - start;
        float length = direction.magnitude;
        if (length <= 0.0001f)
        {
            boneTransform.gameObject.SetActive(false);
            return;
        }

        boneTransform.gameObject.SetActive(true);
        boneTransform.localPosition = (start + end) * 0.5f;
        boneTransform.localRotation = Quaternion.FromToRotation(Vector3.up, direction.normalized);
        boneTransform.localScale = new Vector3(
            Mathf.Max(0.0001f, boneRadius * 2.0f),
            length * 0.5f,
            Mathf.Max(0.0001f, boneRadius * 2.0f)
        );
    }

    private void ApplyBackgroundFrame(FitnessPoseFrame frame)
    {
        string imagePath = ResolveImagePath(frame);
        if (string.IsNullOrWhiteSpace(imagePath) || !File.Exists(imagePath))
        {
            return;
        }

        Texture2D texture = LoadTexture(imagePath);
        if (texture == null)
        {
            return;
        }

        if (backgroundRawImage != null)
        {
            backgroundRawImage.texture = texture;
            backgroundRawImage.SetNativeSize();
        }

        if (backgroundRenderer != null)
        {
            backgroundRenderer.material.mainTexture = texture;
        }
    }

    private string ResolveImagePath(FitnessPoseFrame frame)
    {
        if (!string.IsNullOrWhiteSpace(frame.imagePath) && File.Exists(frame.imagePath))
        {
            return frame.imagePath;
        }

        if (string.IsNullOrWhiteSpace(frame.imageRelativePath) || string.IsNullOrWhiteSpace(imageRootPath))
        {
            return string.Empty;
        }

        string root = ResolveFilePath(imageRootPath);
        string relative = frame.imageRelativePath.Replace("/", Path.DirectorySeparatorChar.ToString());
        return Path.Combine(root, relative);
    }

    private Texture2D LoadTexture(string filePath)
    {
        if (_textureCache.TryGetValue(filePath, out Texture2D cached))
        {
            return cached;
        }

        byte[] imageBytes = File.ReadAllBytes(filePath);
        Texture2D texture = new Texture2D(2, 2, TextureFormat.RGBA32, false);
        if (!texture.LoadImage(imageBytes))
        {
            Destroy(texture);
            Debug.LogWarning($"Failed to load image frame: {filePath}");
            return null;
        }

        texture.name = Path.GetFileNameWithoutExtension(filePath);
        _textureCache[filePath] = texture;
        return texture;
    }

    private static void ApplyMaterial(GameObject target, Material material)
    {
        if (material == null)
        {
            return;
        }

        Renderer renderer = target.GetComponent<Renderer>();
        if (renderer != null)
        {
            renderer.material = material;
        }
    }

    private static string ResolveFilePath(string path)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return string.Empty;
        }

        if (Path.IsPathRooted(path))
        {
            return path;
        }

        return Path.GetFullPath(Path.Combine(Application.dataPath, "..", path));
    }
}
