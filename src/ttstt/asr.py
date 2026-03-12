"""ASR 엔진 모듈.

mlx-audio의 Qwen3-ASR 모델을 사용해 음성을 텍스트로 변환한다.
한국어 + 영어 혼합 환경에 최적화되어 있다.
"""

from __future__ import annotations

import numpy as np

from ttstt.config import ASRConfig

# 모델은 lazy load — 첫 호출 시에만 로드
_model = None
_current_model_id: str | None = None


def _load_model(config: ASRConfig):
    """ASR 모델을 로드한다. 이미 같은 모델이 로드되어 있으면 건너뛴다."""
    global _model, _current_model_id

    if _model is not None and _current_model_id == config.model:
        return _model

    from mlx_audio.stt.generate import load_model

    _model = load_model(config.model)
    _current_model_id = config.model
    return _model


def transcribe(audio: np.ndarray, config: ASRConfig) -> str:
    """오디오 데이터를 텍스트로 변환한다.

    Args:
        audio: 16kHz mono float32 numpy 배열.
        config: ASR 설정.

    Returns:
        인식된 텍스트 문자열.
    """
    model = _load_model(config)

    language = config.language if config.language else None

    result = model.generate(
        audio,
        max_tokens=config.max_tokens,
        language=language,
    )

    return result.text.strip()
