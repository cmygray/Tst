"""회의 모드 모듈.

연속 녹음 → 청크 단위 전사 → 파일 append.
threading.Event 또는 SIGTERM/SIGINT로 graceful shutdown.
"""

from __future__ import annotations

import signal
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np

from tst import asr
from tst.audio import Recorder
from tst.config import ASRConfig, Config, load_config


def _format_timestamp(seconds: float) -> str:
    """초를 HH:MM:SS 형태�� 변환한다."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _build_asr_config(config: Config) -> ASRConfig:
    """회의 전용 ASR 설정을 만든다."""
    meeting = config.meeting
    asr_config = ASRConfig(
        model=meeting.asr.model,
        max_tokens=meeting.asr.max_tokens,
    )
    if meeting.asr.language:
        asr_config.language = meeting.asr.language
    if meeting.asr.system_prompt:
        asr_config.system_prompt = meeting.asr.system_prompt
    if meeting.asr.repetition_penalty > 0:
        asr_config.repetition_penalty = meeting.asr.repetition_penalty
    return asr_config


def run_meeting(
    config: Config,
    stop_event: threading.Event | None = None,
    recorder: Recorder | None = None,
) -> Path:
    """회의 ���드를 실��한다.

    Args:
        config: 앱 설정.
        stop_event: 외부��서 종료를 요청할 이벤트. None이면 내부 생성.
        recorder: 기존 Recorder 인스턴스. None이��� 새로 생성.

    Returns:
        출력 파일 경로.
    """
    if stop_event is None:
        stop_event = threading.Event()

    meeting = config.meeting
    output_dir = meeting.resolved_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = output_dir / f"{timestamp}.md"

    chunk_duration = meeting.chunk_duration
    sample_rate = config.audio.sample_rate

    asr_config = _build_asr_config(config)

    own_recorder = recorder is None
    if own_recorder:
        recorder = Recorder(
            sample_rate=sample_rate,
            channels=config.audio.channels,
            device=config.audio.device,
        )

    print(f"[tst-meeting] 출력: {output_path}", flush=True)
    print(f"[tst-meeting] 청크: {chunk_duration}초", flush=True)
    print("[tst-meeting] ASR ���델 로�� 중...", flush=True)

    asr._load_model(asr_config)
    print("[tst-meeting] ASR 모델 로드 완료", flush=True)

    with open(output_path, "w") as f:
        f.write(f"# 회의록 {timestamp}\n\n")

    if own_recorder:
        recorder.open_stream()
    recorder.start()

    elapsed = 0.0
    chunk_start = time.monotonic()

    try:
        while not stop_event.is_set():
            stop_event.wait(0.1)

            now = time.monotonic()
            if now - chunk_start < chunk_duration:
                continue

            frames = recorder._frames.copy()
            recorder._frames.clear()

            if not frames:
                chunk_start = now
                continue

            audio = np.concatenate(frames, axis=0).flatten()
            duration = len(audio) / sample_rate
            chunk_end_elapsed = elapsed + duration

            ts_start = _format_timestamp(elapsed)
            ts_end = _format_timestamp(chunk_end_elapsed)

            print(f"[tst-meeting] 전사 중... [{ts_start} ~ {ts_end}]", flush=True)
            text = asr.transcribe(audio, asr_config)

            if text.strip():
                with open(output_path, "a") as f:
                    f.write(f"[{ts_start} ~ {ts_end}]\n{text.strip()}\n\n")
                print(f"[tst-meeting] 청크 저장: {len(text)}자", flush=True)

            elapsed = chunk_end_elapsed
            chunk_start = now

    finally:
        recorder.recording = False
        frames = recorder._frames.copy()
        recorder._frames.clear()

        if frames:
            audio = np.concatenate(frames, axis=0).flatten()
            duration = len(audio) / sample_rate
            chunk_end_elapsed = elapsed + duration

            ts_start = _format_timestamp(elapsed)
            ts_end = _format_timestamp(chunk_end_elapsed)

            print(f"[tst-meeting] 마지막 청크 전사 중... [{ts_start} ~ {ts_end}]", flush=True)
            text = asr.transcribe(audio, asr_config)

            if text.strip():
                with open(output_path, "a") as f:
                    f.write(f"[{ts_start} ~ {ts_end}]\n{text.strip()}\n\n")

        if own_recorder:
            recorder.close_stream()
        print(f"[tst-meeting] 종료. 출력: {output_path}", flush=True)

    return output_path


def main() -> None:
    """CLI 엔트리포인���."""
    stop_event = threading.Event()

    def _signal_handler(signum, frame):
        stop_event.set()

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    config = load_config()
    run_meeting(config, stop_event=stop_event)
