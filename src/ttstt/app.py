"""메인 앱 오케스트레이션 모듈.

rumps 메뉴바 앱으로 동작한다.
- 메뉴바 아이콘으로 상태 표시
- 입력 디바이스 실시간 선택
- 글로벌 단축키로 녹음 토글
- ASR → 후처리 → 클립보드 swap → 붙여넣기
"""

from __future__ import annotations

import sys
import threading

import rumps

from ttstt import asr, clipboard, postprocess, sounds
from ttstt.audio import Recorder, list_input_devices
from ttstt.config import Config, load_config
from ttstt.hotkey import check_accessibility, listen, listen_tap_hold


class TtsttApp(rumps.App):
    """ttstt 메뉴바 앱."""

    ICON_IDLE = "🎤"
    ICON_RECORDING = "⏺"
    ICON_PROCESSING = "⏳"

    def __init__(self, config: Config):
        super().__init__("ttstt", title=self.ICON_IDLE, quit_button=None)
        self.config = config
        self.recorder = Recorder(
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            device=config.audio.device,
        )
        self._processing = False

        # 메뉴 구성
        self._status_item = rumps.MenuItem("대기 중", callback=None)
        self._status_item.set_callback(None)
        self._device_menu = rumps.MenuItem("입력 디바이스")
        self._populate_devices()
        if config.hotkey.mode == "tap_hold":
            hotkey_label = f"단축키: {config.hotkey.key} 탭+홀드"
        else:
            hotkey_label = f"단축키: {config.hotkey.modifier}+{config.hotkey.key}"
        self._hotkey_item = rumps.MenuItem(hotkey_label, callback=None)
        self._hotkey_item.set_callback(None)
        self._quit_item = rumps.MenuItem("종료", callback=self._on_quit)

        self.menu = [
            self._status_item,
            None,  # separator
            self._device_menu,
            self._hotkey_item,
            None,
            self._quit_item,
        ]

    def _on_quit(self, _) -> None:
        self.recorder.close_stream()
        rumps.quit_application()

    def _populate_devices(self) -> None:
        """디바이스 목록을 메뉴에 채운다."""
        devices = list_input_devices()
        current = self.recorder.current_device

        if self._device_menu._menu is not None:
            self._device_menu.clear()
        for dev in devices:
            name = dev["name"]
            item = rumps.MenuItem(name, callback=self._on_device_select)
            if current and current == name:
                item.state = 1
            self._device_menu.add(item)

    @rumps.timer(3)
    def _refresh_devices(self, _) -> None:
        """3초마다 디바이스 목록을 갱신한다."""
        devices = list_input_devices()
        current = self.recorder.current_device

        # 변경 없으면 체크 상태만 갱신
        new_names = [d["name"] for d in devices]
        old_names = [item.title for item in self._device_menu.values()]
        if new_names == old_names:
            for item in self._device_menu.values():
                item.state = 1 if item.title == current else 0
            return

        self._populate_devices()

    def _on_device_select(self, sender: rumps.MenuItem) -> None:
        """디바이스를 선택한다."""
        self.recorder.switch_device(sender.title)
        self._set_status("대기 중")

    def _set_status(self, text: str, icon: str | None = None) -> None:
        self._status_item.title = text
        if icon:
            self.title = icon

    def on_toggle(self) -> None:
        """핫키 콜백. 녹음 시작/종료를 토글한다."""
        if self._processing:
            return

        if not self.recorder.recording:
            self._start_recording()
        else:
            self._stop_and_process()

    def on_record_start(self) -> None:
        """녹음 시작 콜백 (tap_hold 모드용)."""
        if self._processing or self.recorder.recording:
            return
        self._start_recording()

    def on_record_stop(self) -> None:
        """녹음 중지 콜백 (tap_hold 모드용)."""
        if not self.recorder.recording:
            return
        self._stop_and_process()

    def _start_recording(self) -> None:
        if not sounds.play(self.config.sound.start):
            print(f"⚠ 사운드 '{self.config.sound.start}'을(를) 찾을 수 없습니다.")
        self.recorder.start()
        self._set_status("녹음 중...", self.ICON_RECORDING)

    def _stop_and_process(self) -> None:
        audio_data = self.recorder.stop()
        if not sounds.play(self.config.sound.stop):
            print(f"⚠ 사운드 '{self.config.sound.stop}'을(를) 찾을 수 없습니다.")
        self._set_status("인식 중...", self.ICON_PROCESSING)

        self._processing = True
        thread = threading.Thread(target=self._process_pipeline, args=(audio_data,))
        thread.daemon = True
        thread.start()

    def _process_pipeline(self, audio_data) -> None:
        try:
            if audio_data.size == 0:
                print("[ttstt] 녹음 데이터 없음 (0 frames)")
                self._set_status("녹음 없음", self.ICON_IDLE)
                return

            duration = len(audio_data) / self.config.audio.sample_rate
            print(f"[ttstt] 오디오 {duration:.1f}초, 인식 중...")

            text = asr.transcribe(audio_data, self.config.asr)
            print(f"[ttstt] ASR 결과: '{text}'")

            if not text:
                self._set_status("인식 실패", self.ICON_IDLE)
                return

            if self.config.postprocess.enabled:
                self._set_status("교정 중...", self.ICON_PROCESSING)
                text = postprocess.correct(text, self.config.postprocess)
                print(f"[ttstt] 교정 결과: '{text}'")

            clipboard.paste_text(text)
            self._set_status("대기 중", self.ICON_IDLE)

        except Exception as e:
            print(f"[ttstt] 오류: {e}")
            self._set_status(f"오류: {e}", self.ICON_IDLE)
        finally:
            self._processing = False


def main() -> None:
    """엔트리포인트."""
    config = load_config()

    if not check_accessibility():
        rumps.alert(
            title="ttstt — 접근성 권한 필요",
            message=(
                "시스템 설정 > 개인 정보 보호 및 보안 > 접근성에서 "
                "ttstt를 허용해주세요.\n\n권한을 부여한 후 다시 실행해주세요."
            ),
        )
        sys.exit(1)

    app = TtsttApp(config)

    # 스트림을 열어 디바이스 연결 유지
    app.recorder.open_stream()

    # ASR 모델을 미리 로드 (첫 인식 지연 제거)
    def _preload():
        from ttstt.asr import _load_model
        _load_model(config.asr)

    threading.Thread(target=_preload, daemon=True).start()

    # 글로벌 핫키를 별도 스레드에서 실행
    if config.hotkey.mode == "tap_hold":
        hotkey_thread = threading.Thread(
            target=listen_tap_hold,
            args=(
                config.hotkey.key,
                app.on_record_start,
                app.on_record_stop,
                config.hotkey.hold_threshold,
            ),
            daemon=True,
        )
    else:
        hotkey_thread = threading.Thread(
            target=listen,
            args=(config.hotkey.modifier, config.hotkey.key, app.on_toggle),
            daemon=True,
        )
    hotkey_thread.start()

    # rumps 이벤트 루프 (메인 스레드)
    app.run()
