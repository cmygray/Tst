"""후처리 LLM 모듈.

mlx-lm을 사용해 ASR 결과를 교정한다.
한국어+영어 혼합 텍스트의 오탈자 수정, 문장 부호 정리 등을 수행.
기본적으로 비활성화되어 있으며, 설정으로 켤 수 있다.
"""

from __future__ import annotations

import re

from tst.config import PostprocessConfig

# 모델은 lazy load
_model = None
_tokenizer = None
_current_model_id: str | None = None


def _load_model(config: PostprocessConfig):
    """후처리 LLM 모델을 로드한다."""
    global _model, _tokenizer, _current_model_id

    if _model is not None and _current_model_id == config.model:
        return _model, _tokenizer

    from mlx_lm import load

    _model, _tokenizer = load(config.model)
    _current_model_id = config.model
    return _model, _tokenizer


def correct(text: str, config: PostprocessConfig) -> str:
    """ASR 결과 텍스트를 LLM으로 교정한다.

    Args:
        text: ASR이 출력한 원본 텍스트.
        config: 후처리 설정.

    Returns:
        교정된 텍스트. 후처리가 비활성화되어 있으면 원본을 그대로 반환.
    """
    if not config.enabled:
        return text

    if not text.strip():
        return text

    model, tokenizer = _load_model(config)

    from mlx_lm import generate

    messages = [
        {"role": "system", "content": config.system_prompt},
        {"role": "user", "content": text + " /no_think"},
    ]

    prompt = tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
        enable_thinking=False,
    )

    result = generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=config.max_tokens,
    )

    if not result:
        return text

    # Qwen3 thinking 블록 제거
    result = re.sub(r"<think>.*?</think>", "", result, flags=re.DOTALL)
    return result.strip() or text
