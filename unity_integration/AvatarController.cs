using UnityEngine;

/// <summary>
/// 서버에서 받은 SMPL-X (Axis-Angle) 관절 각도를 Unity 휴머노이드 뼈대에 적용하는 컨트롤러입니다.
/// </summary>
public class AvatarController : MonoBehaviour
{
    [Header("Bones (21 SMPL Body Joints)")]
    [Tooltip("SMPL-X 관절 순서에 맞게 Unity 뼈대(Transform)를 할당하세요.")]
    public Transform[] smplBones = new Transform[21];
    
    public Transform rootBone; // Pelvis (global_orient)

    // 초기 상태(T-pose)의 로컬 회전값을 저장
    private Quaternion[] initialRotations;
    private Quaternion initialRootRotation;

    void Start()
    {
        // 아바타의 T-포즈(기본 상태) 회전값을 저장해둡니다.
        initialRotations = new Quaternion[smplBones.Length];
        for (int i = 0; i < smplBones.Length; i++)
        {
            if (smplBones[i] != null)
                initialRotations[i] = smplBones[i].localRotation;
        }

        if (rootBone != null)
            initialRootRotation = rootBone.localRotation;
    }

    /// <summary>
    /// 서버에서 받은 프레임 데이터를 적용합니다.
    /// </summary>
    /// <param name="globalOrient">길이 3 (Pelvis 회전)</param>
    /// <param name="bodyPose">길이 63 (21개 관절 * 3)</param>
    public void UpdatePose(float[] globalOrient, float[] bodyPose)
    {
        if (globalOrient == null || globalOrient.Length < 3 || bodyPose == null || bodyPose.Length < 63)
            return;

        // 1. Root (Pelvis) 회전 적용
        if (rootBone != null)
        {
            Vector3 rootAxisAngle = new Vector3(globalOrient[0], globalOrient[1], globalOrient[2]);
            Quaternion rootRot = AxisAngleToQuaternion(rootAxisAngle);
            rootBone.localRotation = initialRootRotation * rootRot;
        }

        // 2. 21개 세부 관절 회전 적용
        for (int i = 0; i < 21; i++)
        {
            if (i >= smplBones.Length || smplBones[i] == null) continue;

            // 배열에서 x, y, z 추출
            Vector3 axisAngle = new Vector3(
                bodyPose[i * 3 + 0],
                bodyPose[i * 3 + 1],
                bodyPose[i * 3 + 2]
            );

            // 변환된 쿼터니언을 로컬 회전에 곱해줌 (초기 포즈 기준)
            Quaternion jointRot = AxisAngleToQuaternion(axisAngle);
            smplBones[i].localRotation = initialRotations[i] * jointRot;
        }
    }

    /// <summary>
    /// SMPL-X (Axis-Angle, 오른손 좌표계) -> Unity (Quaternion, 왼손 좌표계) 변환 핵심 로직
    /// </summary>
    private Quaternion AxisAngleToQuaternion(Vector3 axisAngle)
    {
        float angle = axisAngle.magnitude;
        // 회전이 거의 없다면 초기화
        if (angle < 1e-5f) return Quaternion.identity;

        Vector3 axis = axisAngle / angle;
        
        // --- 좌표계 변환 (Coordinate Mapping) ---
        // SMPL-X와 Unity의 차이를 보정하기 위해 X축(또는 Z축)을 반전해야 합니다.
        // 일반적인 SMPL -> Unity 변환은 X축 반전을 사용합니다.
        axis.x = -axis.x; 

        // Unity의 AngleAxis는 Degree(각도)를 사용하므로 Radian을 Degree로 변환
        return Quaternion.AngleAxis(angle * Mathf.Rad2Deg, axis);
    }
}
