using UnityEngine;
using UnityEngine.UI;

/// <summary>
/// 서버에서 계산된 실시간 자세 피드백과 점수를 Unity UI에 표시하는 매니저
/// </summary>
public class UIManager : MonoBehaviour
{
    [Header("UI Elements")]
    public Text scoreText;
    public Text feedbackLabelText;
    
    // 점수에 따라 색상을 변경할 이미지 (원형 프로그레스 바 등)
    public Image scoreRingImage;

    [Header("Colors")]
    public Color goodColor = new Color(0.0f, 0.9f, 0.46f);  // #00e676
    public Color warningColor = new Color(1.0f, 0.57f, 0.0f); // #ff9100
    public Color badColor = new Color(1.0f, 0.24f, 0.0f);    // #ff3d00

    /// <summary>
    /// 웹소켓 클라이언트에서 새로운 점수가 들어올 때마다 호출됩니다.
    /// </summary>
    public void UpdateScore(int score, string label)
    {
        if (scoreText != null)
            scoreText.text = score.ToString();

        if (feedbackLabelText != null)
            feedbackLabelText.text = label;

        // 점수에 따른 UI 색상 변경 로직
        Color targetColor = badColor;
        if (score >= 80)
            targetColor = goodColor;
        else if (score >= 50)
            targetColor = warningColor;

        if (scoreRingImage != null)
            scoreRingImage.color = targetColor;
        if (scoreText != null)
            scoreText.color = targetColor;
        if (feedbackLabelText != null)
            feedbackLabelText.color = targetColor;
    }
}
