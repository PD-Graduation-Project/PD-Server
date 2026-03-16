"""
ML Prediction module.
Interfaces the _FINAL_SCRIPTS prediction pipeline with the Flask server.
"""

from ml.predictor import (
    predict_drawing,
    predict_questionnaire,
    predict_tremor,
    predict_voice,
)

__all__ = [
    "predict_tremor",
    "predict_drawing",
    "predict_voice",
    "predict_questionnaire",
]
