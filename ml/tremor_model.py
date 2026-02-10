"""
Tremor prediction model.
Currently returns a mock random prediction for development.
Replace with actual PyTorch model inference when ready.
"""

import random


def predict_tremor(test_session_id: int) -> float:
    """
    Generate a mock prediction for tremor test data.

    Args:
        test_session_id: The ID of the test session

    Returns:
        float: Probability of Parkinson's disease (0.0 = healthy, 1.0 = PD likely)
    """
    return random.uniform(0.0, 1.0)
