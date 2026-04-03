"""ASR 모델 벤치마크 — 1.7B-8bit vs 0.6B-4bit/8bit 비교."""

import time
import numpy as np

MODELS = [
    "mlx-community/Qwen3-ASR-1.7B-8bit",
    "mlx-community/Qwen3-ASR-0.6B-8bit",
    "mlx-community/Qwen3-ASR-0.6B-4bit",
]

# 10초 무음 + 간단한 톤 (실제 음성 대신 모델 로드/추론 속도 측정용)
SAMPLE_RATE = 16000
DURATION = 5
audio = np.random.randn(SAMPLE_RATE * DURATION).astype(np.float32) * 0.01


def bench(model_id: str):
    from mlx_audio.stt.generate import load_model

    print(f"\n{'='*50}")
    print(f"모델: {model_id}")
    print(f"{'='*50}")

    t0 = time.perf_counter()
    model = load_model(model_id)
    load_time = time.perf_counter() - t0
    print(f"로드 시간: {load_time:.2f}s")

    # warmup
    model.generate(audio, max_tokens=64)

    # 3회 측정
    times = []
    for i in range(3):
        t0 = time.perf_counter()
        result = model.generate(audio, max_tokens=256)
        elapsed = time.perf_counter() - t0
        times.append(elapsed)
        print(f"  run {i+1}: {elapsed:.2f}s — \"{result.text.strip()[:80]}\"")

    avg = sum(times) / len(times)
    print(f"평균 추론: {avg:.2f}s ({DURATION}초 오디오)")

    # 메모리 확인
    try:
        import mlx.core as mx
        peak = mx.metal.get_peak_memory() / 1024**2
        active = mx.metal.get_active_memory() / 1024**2
        print(f"메모리: peak={peak:.0f}MB, active={active:.0f}MB")
        mx.metal.reset_peak_memory()
    except Exception:
        pass

    del model


if __name__ == "__main__":
    for m in MODELS:
        bench(m)
