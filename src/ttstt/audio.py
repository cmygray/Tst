"""오디오 녹음 모듈.

sounddevice로 마이크 입력을 녹음한다.
스트림을 항상 열어두어 디바이스 연결(연속성 카메라 등)을 유지하고,
핫키로 프레임 수집만 on/off한다.
"""

from __future__ import annotations

import numpy as np
import sounddevice as sd


def list_input_devices() -> list[dict]:
    """사용 가능한 입력 디바이스 목록을 반환한다."""
    devices = sd.query_devices()
    inputs = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] > 0:
            inputs.append({"index": i, "name": d["name"]})
    return inputs


def get_default_input_device() -> str | None:
    """시스템 기본 입력 디바이스 이름을 반환한다."""
    try:
        default = sd.query_devices(kind="input")
        return default["name"]
    except Exception:
        return None


class Recorder:
    """마이크 녹음을 관리하는 클래스.

    스트림을 항상 열어두고, recording 플래그로 프레임 수집만 토글한다.
    이렇게 하면 연속성 카메라 등 디바이스 연결이 유지된다.
    """

    def __init__(self, sample_rate: int = 16000, channels: int = 1, device: str = ""):
        self.sample_rate = sample_rate
        self.channels = channels
        self._frames: list[np.ndarray] = []
        self._stream: sd.InputStream | None = None
        self.recording = False
        self._device_name: str | None = device or None

    def open_stream(self, device: str | None = None) -> None:
        """오디오 스트림을 열어 디바이스 연결을 유지한다."""
        self.close_stream()

        if device:
            self._device_name = device

        target = self._device_name or get_default_input_device()

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            device=target,
            callback=self._audio_callback,
        )
        self._stream.start()
        self._device_name = target

    def close_stream(self) -> None:
        """오디오 스트림을 닫는다."""
        if self._stream is not None:
            try:
                self._stream.stop()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self.recording = False

    def switch_device(self, device: str) -> None:
        """디바이스를 전환한다. 스트림을 다시 열어 연결을 유지한다."""
        self.open_stream(device)

    @property
    def current_device(self) -> str | None:
        return self._device_name

    def start(self) -> None:
        """프레임 수집을 시작한다. 스트림이 없으면 먼저 연다."""
        if self._stream is None:
            self.open_stream()
        self._frames = []
        self.recording = True

    def stop(self) -> np.ndarray:
        """프레임 수집을 종료하고 정규화된 오디오 데이터를 반환한다.

        스트림은 닫지 않는다 (디바이스 연결 유지).
        """
        self.recording = False

        if not self._frames:
            return np.array([], dtype=np.float32)

        audio = np.concatenate(self._frames, axis=0).flatten()
        self._frames = []
        return audio

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: object,
        status: sd.CallbackFlags,
    ) -> None:
        """sounddevice 콜백. recording 중일 때만 프레임을 누적한다."""
        if self.recording:
            self._frames.append(indata.copy())


