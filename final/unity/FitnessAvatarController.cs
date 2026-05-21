using UnityEngine;

/// <summary>
/// 서버에서 받은 SMPL-X (Axis-Angle) 관절 각도를 Unity 휴머노이드 뼈대에 적용하는 컨트롤러입니다.
///
/// SMPL-X 좌표계: 오른손 좌표계 (X-left, Y-up, Z-forward)
/// Unity 좌표계: 왼손 좌표계 (X-right, Y-up, Z-forward)
///
/// 변환 규칙: axis-angle 벡터의 X, Z 성분을 반전시킵니다.
/// </summary>
public class FitnessAvatarController : MonoBehaviour
{
    [Header("Bones (21 SMPL Body Joints)")]
    [Tooltip("SMPL-X 관절 순서에 맞게 Unity 뼈대(Transform)를 할당하세요.")]
    public Transform[] smplBones = new Transform[21];

    public Transform rootBone; // Pelvis (global_orient)

    [Header("Calibration")]
    [Tooltip("아바타가 누워있거나 뒤집혀 있다면 이 값을 조절하세요 (예: X=90, 180, -90 등)")]
    public Vector3 rootRotationOffset = new Vector3(0, 0, 0);

    [Header("Smoothing")]
    [Tooltip("Unity 측 추가 보간 강도 (0=즉시, 1=매우 느리게). 0.5 정도 추천")]
    [Range(0f, 0.95f)]
    public float lerpFactor = 0.5f;

    // 초기 상태(T-pose)의 로컬 회전값을 저장
    private Quaternion[] initialRotations;
    private Quaternion initialRootRotation;

    // 보간용 타겟 회전값
    private Quaternion[] targetRotations;
    private Quaternion targetRootRotation;
    private bool hasData = false;

    void Start()
    {
        // 아바타의 T-포즈(기본 상태) 회전값을 저장해둡니다.
        initialRotations = new Quaternion[smplBones.Length];
        targetRotations = new Quaternion[smplBones.Length];

        for (int i = 0; i < smplBones.Length; i++)
        {
            if (smplBones[i] != null)
            {
                initialRotations[i] = smplBones[i].localRotation;
                targetRotations[i] = smplBones[i].localRotation;
            }
        }

        if (rootBone != null)
        {
            initialRootRotation = rootBone.localRotation;
            targetRootRotation = rootBone.localRotation;
        }
    }

    /// <summary>
    /// 서버에서 받은 프레임 데이터를 적용합니다.
    /// </summary>
    /// <param name="globalOrient">길이 3 (Pelvis 회전, axis-angle)</param>
    /// <param name="bodyPose">길이 63 (21개 관절 * 3, axis-angle)</param>
    public void UpdatePose(float[] globalOrient, float[] bodyPose)
    {
        if (globalOrient == null || globalOrient.Length < 3 || bodyPose == null || bodyPose.Length < 63)
        {
            Debug.LogWarning($"[Avatar] Invalid data: orient={globalOrient?.Length}, pose={bodyPose?.Length}");
            return;
        }

        // 1. Root (Pelvis) 회전 타겟 설정
        if (rootBone != null)
        {
            Vector3 rootAxisAngle = new Vector3(globalOrient[0], globalOrient[1], globalOrient[2]);
            Quaternion rootRot = SmplAxisAngleToUnityQuat(rootAxisAngle);
            targetRootRotation = initialRootRotation * rootRot * Quaternion.Euler(rootRotationOffset);
        }

        // 2. 21개 세부 관절 회전 타겟 설정
        for (int i = 0; i < 21; i++)
        {
            if (i >= smplBones.Length || smplBones[i] == null) continue;

            Vector3 axisAngle = new Vector3(
                bodyPose[i * 3 + 0],
                bodyPose[i * 3 + 1],
                bodyPose[i * 3 + 2]
            );

            Quaternion jointRot = SmplAxisAngleToUnityQuat(axisAngle);
            targetRotations[i] = initialRotations[i] * jointRot;
        }

        hasData = true;
    }

    void LateUpdate()
    {
        if (!hasData) return;

        // Lerp로 부드럽게 보간하여 적용
        float t = 1f - lerpFactor;

        if (rootBone != null)
        {
            rootBone.localRotation = Quaternion.Slerp(rootBone.localRotation, targetRootRotation, t);
        }

        for (int i = 0; i < smplBones.Length; i++)
        {
            if (smplBones[i] != null)
            {
                smplBones[i].localRotation = Quaternion.Slerp(
                    smplBones[i].localRotation,
                    targetRotations[i],
                    t
                );
            }
        }
    }

    /// <summary>
    /// SMPL-X axis-angle (오른손 좌표계) → Unity Quaternion (왼손 좌표계) 변환
    ///
    /// SMPL-X: Right-handed (X-left, Y-up, Z-forward)
    /// Unity:  Left-handed  (X-right, Y-up, Z-forward)
    ///
    /// Handedness 전환 시 axis-angle의 X, Z 성분을 반전합니다.
    /// (Y축은 동일하므로 유지)
    /// </summary>
    private Quaternion SmplAxisAngleToUnityQuat(Vector3 axisAngle)
    {
        float angle = axisAngle.magnitude;
        if (angle < 1e-6f) return Quaternion.identity;

        Vector3 axis = axisAngle / angle;

        // 오른손→왼손 좌표계 변환: X축 반전, Z축 반전
        axis.x = -axis.x;
        axis.z = -axis.z;

        return Quaternion.AngleAxis(angle * Mathf.Rad2Deg, axis);
    }
}
