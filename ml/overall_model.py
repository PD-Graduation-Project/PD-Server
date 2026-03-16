"""
Overall (aggregate) prediction model.

Combines tremor, drawing, voice, and questionnaire scores into a single
PD probability using a weighted average.

Weights reflect the relative clinical reliability of each modality:
  - Questionnaire : 0.35  (demographic + symptom history)
  - Tremor        : 0.25  (motor signal)
  - Drawing       : 0.25  (fine motor control)
  - Voice         : 0.15  (vocal biomarkers)

If the questionnaire score cannot be computed (missing user data), the
remaining three scores are renormalised to still sum to 1.0.
"""

from loguru import logger

# Weights must sum to 1.0
_WEIGHTS = {
    "questionnaire": 0.35,
    "tremor": 0.25,
    "drawing": 0.25,
    "voice": 0.15,
}


def predict_overall(
    tremor_score: float,
    drawing_score: float,
    voice_score: float,
    user_id: int | None = None,
) -> float:
    """
    Compute an aggregate PD probability from the four modality scores.

    Runs the questionnaire model against the user's profile if user_id is
    provided, then combines all scores with the predefined weights.

    Args:
        tremor_score:  ml_score from the tremor TestSession (0.0–1.0)
        drawing_score: ml_score from the drawing TestSession (0.0–1.0)
        voice_score:   ml_score from the voice TestSession (0.0–1.0)
        user_id:       ID of the User whose questionnaire data to use.
                       If None or the prediction fails, questionnaire is
                       excluded and the other weights are renormalised.

    Returns:
        float: Overall probability of Parkinson's disease (0.0–1.0)
    """
    questionnaire_score = None

    if user_id is not None:
        try:
            from ml.predictor import predict_questionnaire

            questionnaire_score = predict_questionnaire(user_id)
            logger.info(
                f"Questionnaire score for user={user_id}: {questionnaire_score:.4f}"
            )
        except Exception as e:
            logger.warning(
                f"Questionnaire prediction failed for user={user_id}, excluding: {e}"
            )

    if questionnaire_score is not None:
        scores = {
            "questionnaire": questionnaire_score,
            "tremor": tremor_score,
            "drawing": drawing_score,
            "voice": voice_score,
        }
        weights = _WEIGHTS
    else:
        # Renormalise the remaining three weights to sum to 1.0
        scores = {
            "tremor": tremor_score,
            "drawing": drawing_score,
            "voice": voice_score,
        }
        total = sum(_WEIGHTS[k] for k in scores)
        weights = {k: _WEIGHTS[k] / total for k in scores}

    overall = sum(scores[k] * weights[k] for k in scores)
    logger.info(
        f"Overall score: {overall:.4f} "
        f"(tremor={tremor_score:.3f}, drawing={drawing_score:.3f}, "
        f"voice={voice_score:.3f}, questionnaire={questionnaire_score})"
    )
    return overall
