"""회의 모드 모듈.

연속 녹음 → 청크 단위 전사 → 파일 append.
SIGTERM/SIGINT로 graceful shutdown.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from datetime import datetime

import numpy as np

from ttstt import asr
from ttstt.audio import Recorder
from ttstt.config import Config, load_config


def _check_existing_process() -> bool:
    """기존 ttstt 프로세스가 실행 중인지 확인한다."""
    import subprocess

    result = subprocess.run(
        ["pgrep", "-f", "ttstt.app:main"],
        capture_output=True,
    )
    return result.returncode == 0


def _format_timestamp(seconds: float) -> str:
    """초를 HH:MM:SS 형태로 변환한다."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def run_meeting(config: Config) -> None:
    """회의 모드를 실행한다."""
    if _check_existing_process():
        print("[ttstt-meeting] 오류: ttstt 앱이 이미 실행 중입니다. 종료 후 다시 시도하세요.",
              file=sys.stderr)
        sys.exit(1)

    meeting = config.meeting
    output_dir = meeting.resolved_output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    output_path = output_dir / f"{timestamp}.md"

    chunk_duration = meeting.chunk_duration
    sample_rate = config.audio.sample_rate

    # ASR 설정을 meeting 전용으로 오버라이드
    asr_config = config.asr
    asr_config.model = meeting.asr.model
    asr_config.max_tokens = meeting.asr.max_tokens
    if meeting.asr.language:
        asr_config.language = meeting.asr.language
    if meeting.asr.system_prompt:
        asr_config.system_prompt = meeting.asr.system_prompt
    if meeting.asr.repetition_penalty > 0:
        asr_config.repetition_penalty = meeting.asr.repetition_penalty

    recorder = Recorder(
        sample_rate=sample_rate,
        channels=config.audio.channels,
        device=config.audio.device,
    )

    # Graceful shutdown
    shutdown = False

    def _signal_handler(signum, frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    # 출력 파일 경로를 stdout에 출력 (에이전트가 캡처)
    print(f"[ttstt-meeting] 출력: {output_path}")
    print(f"[ttstt-meeting] 청크: {chunk_duration}초")
    print(f"[ttstt-meeting] PID: {os.getpid()}")
    print("[ttstt-meeting] 녹음 시작...")

    # ASR 모델 프리로드
    asr._load_model(asr_config)
    print("[ttstt-meeting] ASR 모델 로드 완료")

    # 헤더 작성
    with open(output_path, "w") as f:
        f.write(f"# 회의록 {timestamp}\n\n")

    recorder.open_stream()
    recorder.start()

    elapsed = 0.0
    chunk_start = time.monotonic()

    try:
        while not shutdown:
            time.sleep(0.1)

            now = time.monotonic()
            if now - chunk_start < chunk_duration:
                continue

            # 프레임 drain (녹음은 계속)
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

            print(f"[ttstt-meeting] 전사 중... [{ts_start} ~ {ts_end}]")
            text = asr.transcribe(audio, asr_config)

            if text.strip():
                with open(output_path, "a") as f:
                    f.write(f"[{ts_start} ~ {ts_end}]\n{text.strip()}\n\n")
                print(f"[ttstt-meeting] 청크 저장: {len(text)}자")

            elapsed = chunk_end_elapsed
            chunk_start = now

    finally:
        # 마지막 청크 플러시
        recorder.recording = False
        frames = recorder._frames.copy()
        recorder._frames.clear()

        if frames:
            audio = np.concatenate(frames, axis=0).flatten()
            duration = len(audio) / sample_rate
            chunk_end_elapsed = elapsed + duration

            ts_start = _format_timestamp(elapsed)
            ts_end = _format_timestamp(chunk_end_elapsed)

            print(f"[ttstt-meeting] 마지막 청크 전사 중... [{ts_start} ~ {ts_end}]")
            text = asr.transcribe(audio, asr_config)

            if text.strip():
                with open(output_path, "a") as f:
                    f.write(f"[{ts_start} ~ {ts_end}]\n{text.strip()}\n\n")

        recorder.close_stream()
        print(f"[ttstt-meeting] 종료. 출력: {output_path}")


def main() -> None:
    """엔트리포인트."""
    config = load_config()
    run_meeting(config)
