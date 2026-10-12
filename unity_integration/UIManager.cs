using UnityEngine;

/// <summary>
/// 서버에서 계산된 실시간 자세 피드백과 점수를 Unity 구형 OnGUI로 표시하는 매니저
/// (초보자용: 별도의 UI 패키지 설치나 Canvas 설정이 필요 없습니다!)
/// </summary>
public class UIManager : MonoBehaviour
{
    private int currentScore = 0;
    private string currentFeedback = "대기 중...";
    private Color currentColor = Color.white;

    /// <summary>
    /// 웹소켓 클라이언트에서 새로운 점수가 들어올 때마다 호출됩니다.
    /// </summary>
    public void UpdateScore(int score, string label)
    {
        currentScore = score;
        currentFeedback = label;

        // 점수에 따른 텍스트 색상 변경
        if (score >= 80)
            currentColor = new Color(0.0f, 0.9f, 0.46f); // 초록색
        else if (score >= 50)
            currentColor = new Color(1.0f, 0.57f, 0.0f); // 주황색
        else
            currentColor = new Color(1.0f, 0.24f, 0.0f); // 빨간색
    }

    /// <summary>
    /// Unity 내장 기능으로 화면 왼쪽 위에 글씨를 바로 그려줍니다.
    /// </summary>
    private void OnGUI()
    {
        GUIStyle style = new GUIStyle();
        style.fontSize = 50; // 글씨 크기
        style.normal.textColor = currentColor;
        
        // 화면 좌표 (X: 50, Y: 50) 위치에 폭 800, 높이 100으로 글씨를 씁니다.
        GUI.Label(new Rect(50, 50, 800, 100), $"점수: {currentScore}", style);
        GUI.Label(new Rect(50, 120, 800, 100), $"상태: {currentFeedback}", style);
    }
}
