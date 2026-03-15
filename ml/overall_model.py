"""
Overall (aggregate) prediction model.
Combines tremor, drawing, and voice scores into a single PD probability.
Currently returns a mock prediction for development.
Replace with actual model logic when ready.
"""

import random


def predict_overall(
    tremor_score: float,
    drawing_score: float,
    voice_score: float,
) -> float:
    """
    Compute an aggregate PD probability from the three individual test scores.

    Args:
        tremor_score:  ml_score from the tremor TestSession (0.0–1.0)
        drawing_score: ml_score from the drawing TestSession (0.0–1.0)
        voice_score:   ml_score from the voice TestSession (0.0–1.0)

    Returns:
        float: Overall probability of Parkinson's disease (0.0 = healthy, 1.0 = PD likely)
    """
    # TODO: replace with real multi-modal model inference
    _ = (tremor_score, drawing_score, voice_score)  # suppress unused-arg warnings
    return random.uniform(0.0, 1.0)
