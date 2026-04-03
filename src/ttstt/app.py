"""메인 앱 오케스트레이션 모듈.

rumps 메뉴바 앱으로 동작한다.
- 메뉴바 아이콘으로 상태 표시
- 입력 디바이스 실시간 선택
- 글로벌 단축키로 녹음 토글
- ASR → 후처리 → 클립보드 swap → 붙여넣기
"""

from __future__ import annotations

import fcntl
import sys
import threading
import webbrowser
from pathlib import Path

import rumps

from ttstt import asr, clipboard, postprocess, sounds
from ttstt.audio import Recorder, list_input_devices
from ttstt.config import Config, load_config, save_settings
from ttstt.highlight import hide_highlight, show_highlight
from ttstt.hotkey import check_accessibility, listen, listen_tap_hold


class TtsttApp(rumps.App):
    """ttstt 메뉴바 앱."""

    _ICONS_BASE = Path(__file__).parent / "icons"

    def __init__(self, config: Config):
        icons_dir = self._resolve_icons_dir(config.appearance.icon_theme)
        icon_path = str(icons_dir / "stt-idle@2x.png")
        super().__init__("ttstt", icon=icon_path, title=None, quit_button=None)
        is_template = config.appearance.icon_theme == "speech-bubble"
        self.template = is_template
        self.config = config
        self.recorder = Recorder(
            sample_rate=config.audio.sample_rate,
            channels=config.audio.channels,
            device=config.audio.device,
        )
        self._processing = False
        self._hotkey_stop_event: threading.Event | None = None
        self._hotkey_thread: threading.Thread | None = None

        self._hotkey_active = True

        # 회의 모드 상태
        self._meeting_active = False
        self._meeting_stop_event: threading.Event | None = None
        self._meeting_thread: threading.Thread | None = None

        # 메뉴 구성
        self._status_item = rumps.MenuItem("대기 중", callback=None)
        self._status_item.set_callback(None)
        self._device_menu = rumps.MenuItem("입력 디바이스")
        self._populate_devices()
        self._pause_item = rumps.MenuItem("일시정지", callback=self._on_pause)
        self._meeting_item = rumps.MenuItem("회의 시작", callback=self._on_meeting)
        self._settings_item = rumps.MenuItem("설정", callback=self._on_settings)
        self._quit_item = rumps.MenuItem("종료", callback=self._on_quit)

        self.menu = [
            self._status_item,
            None,
            self._device_menu,
            self._pause_item,
            self._meeting_item,
            None,
            self._settings_item,
            self._quit_item,
        ]

    def _on_pause(self, _) -> None:
        if self._hotkey_active:
            if self._hotkey_stop_event:
                self._hotkey_stop_event.set()
            self._hotkey_active = False
            self._pause_item.title = "재개"
            self._set_status("일시정지")
        else:
            self.start_hotkey()
            self._hotkey_active = True
            self._pause_item.title = "일시정지"
            self._set_status("대기 중")

    def _on_meeting(self, _) -> None:
        if not self._meeting_active:
            self._start_meeting()
        else:
            self._stop_meeting()

    def _start_meeting(self) -> None:
        """회의 모드를 시작한다. 핫키 전사를 정지하고 회의 녹음을 시작."""
        # 핫키 정지
        if self._hotkey_stop_event:
            self._hotkey_stop_event.set()
        self._hotkey_active = False
        self._pause_item.title = "재개"

        # 회의 시작
        from ttstt.meeting import run_meeting

        self._meeting_stop_event = threading.Event()
        self._meeting_thread = threading.Thread(
            target=self._run_meeting_thread,
            daemon=True,
        )
        self._meeting_active = True
        self._meeting_item.title = "회의 종료"
        self._pause_item.set_callback(None)  # 회의 중 일시정지 비활성
        self._set_status("회의 중")
        self._meeting_thread.start()

    def _run_meeting_thread(self) -> None:
        """회의 모드 스레드."""
        from ttstt.meeting import run_meeting
        try:
            run_meeting(
                self.config,
                stop_event=self._meeting_stop_event,
                recorder=self.recorder,
            )
        except Exception as e:
            print(f"[ttstt-meeting] 오류: {e}", flush=True)

    def _stop_meeting(self) -> None:
        """회의 모드를 종료하고 핫키 전사를 재개."""
        if self._meeting_stop_event:
            self._meeting_stop_event.set()
        # 스레드 종료 대기 (최대 30초 — 마지막 청크 전사 시간)
        if self._meeting_thread:
            self._meeting_thread.join(timeout=30)

        self._meeting_active = False
        self._meeting_item.title = "회의 시작"
        self._pause_item.set_callback(self._on_pause)

        # 핫키 재개
        self.start_hotkey()
        self._hotkey_active = True
        self._pause_item.title = "일시정지"
        self._set_status("대기 중")

    def start_hotkey(self) -> None:
        """핫키 리스너 스레드를 시작한다."""
        self._hotkey_stop_event = threading.Event()
        hk = self.config.hotkey
        if hk.mode == "tap_hold":
            tap_hold_modifier = "" if hk.modifier == "없음" else hk.modifier
            self._hotkey_thread = threading.Thread(
                target=listen_tap_hold,
                args=(
                    hk.key,
                    self.on_record_start,
                    self.on_record_stop,
                    hk.hold_threshold,
                    self.on_repaste,
                ),
                kwargs={
                    "stop_event": self._hotkey_stop_event,
                    "modifier": tap_hold_modifier,
                },
                daemon=True,
            )
        else:
            self._hotkey_thread = threading.Thread(
                target=listen,
                args=(hk.modifier, hk.key, self.on_toggle),
                kwargs={
                    "extra_bindings": [
                        (hk.repaste_modifier, hk.repaste_key, self.on_repaste),
                    ],
                    "stop_event": self._hotkey_stop_event,
                },
                daemon=True,
            )
        self._hotkey_thread.start()

    def _restart_hotkey(self) -> None:
        if self._hotkey_stop_event:
            self._hotkey_stop_event.set()
        # join하지 않음 — 메인 스레드 블로킹 방지. 옛 스레드는 자연 종료됨.
        self.start_hotkey()

    def _on_settings(self, _) -> None:
        from ttstt.settings import show_settings
        show_settings(
            self.config.hotkey, self.config.appearance,
            self._on_settings_saved, asr_model=self.config.asr.model,
        )

    def _on_settings_saved(self, result) -> None:
        from ttstt.settings import SettingsResult
        result: SettingsResult
        # 설정 창에서 노출하지 않는 값 보존
        result.hotkey.hold_threshold = self.config.hotkey.hold_threshold

        self.config.hotkey = result.hotkey
        self.config.appearance = result.appearance
        asr_changed = result.asr_model and result.asr_model != self.config.asr.model
        if asr_changed:
            self.config.asr.model = result.asr_model
        save_settings(
            result.hotkey, result.appearance,
            asr=self.config.asr if asr_changed else None,
        )

        # 아이콘 즉시 변경
        icons_dir = self._resolve_icons_dir(result.appearance.icon_theme)
        self.icon = str(icons_dir / "stt-idle@2x.png")
        self.template = result.appearance.icon_theme == "speech-bubble"

        # 핫키 재시작
        self._restart_hotkey()

        print(f"[ttstt] 설정 적용됨: theme={result.appearance.icon_theme}, "
              f"mode={result.hotkey.mode}, key={result.hotkey.key}")

    def _on_quit(self, _) -> None:
        self.recorder.close_stream()
        rumps.quit_application()

    def notify_update(self, version: str, url: str) -> None:
        """업데이트가 있으면 메뉴에 항목을 추가한다. 아무 스레드에서 호출 가능."""
        item = rumps.MenuItem(
            f"업데이트 있음 (v{version})", callback=lambda _: webbrowser.open(url),
        )
        self.menu.insert_before(self._settings_item.title, item)

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

    @classmethod
    def _resolve_icons_dir(cls, theme: str) -> Path:
        if theme == "blob":
            return cls._ICONS_BASE / "blob-dark"
        return cls._ICONS_BASE / "speech-bubble"

    def _set_status(self, text: str, icon: str | None = None) -> None:
        self._status_item.title = text
        if icon:
            icons_dir = self._resolve_icons_dir(self.config.appearance.icon_theme)
            self.icon = str(icons_dir / icon)

    def on_toggle(self) -> None:
        """핫키 콜백. 녹음 시작/종료를 토글한다."""
        if self._processing:
            return

        if not self.recorder.recording:
            show_highlight()
            self._start_recording()
        else:
            self._stop_and_process()

    def on_record_start(self) -> None:
        """녹음 시작 콜백 (tap_hold 모드용)."""
        if self._processing or self.recorder.recording:
            return
        show_highlight()
        self._start_recording()

    def on_record_stop(self) -> None:
        """녹음 중지 콜백 (tap_hold 모드용)."""
        if not self.recorder.recording:
            return
        self._stop_and_process()

    def on_repaste(self) -> None:
        """재붙여넣기 핫키 콜백."""
        if self._processing or self.recorder.recording:
            return
        if not clipboard.repaste_last():
            print("[ttstt] 재붙여넣기할 텍스트 없음")

    def _start_recording(self) -> None:
        if not sounds.play(self.config.sound.start):
            print(f"⚠ 사운드 '{self.config.sound.start}'을(를) 찾을 수 없습니다.")
        self.recorder.start()
        self._set_status("녹음 중...", "stt-recording@2x.png")

    def _stop_and_process(self) -> None:
        audio_data = self.recorder.stop()
        if not sounds.play(self.config.sound.stop):
            print(f"⚠ 사운드 '{self.config.sound.stop}'을(를) 찾을 수 없습니다.")
        self._set_status("인식 중...", "stt-processing@2x.png")

        self._processing = True
        thread = threading.Thread(target=self._process_pipeline, args=(audio_data,))
        thread.daemon = True
        thread.start()

    def _process_pipeline(self, audio_data) -> None:
        try:
            if audio_data.size == 0:
                print("[ttstt] 녹음 데이터 없음 (0 frames)")
                self._set_status("녹음 없음", "stt-idle@2x.png")
                return

            duration = len(audio_data) / self.config.audio.sample_rate
            print(f"[ttstt] 오디오 {duration:.1f}초, 인식 중...")

            text = asr.transcribe(audio_data, self.config.asr)
            print(f"[ttstt] ASR 결과: '{text}'")

            if not text:
                self._set_status("인식 실패", "stt-idle@2x.png")
                return

            if self.config.postprocess.enabled:
                self._set_status("교정 중...", "stt-processing@2x.png")
                text = postprocess.correct(text, self.config.postprocess)
                print(f"[ttstt] 교정 결과: '{text}'")

            clipboard.paste_text(text)
            self._set_status("대기 중", "stt-idle@2x.png")

        except Exception as e:
            print(f"[ttstt] 오류: {e}")
            self._set_status(f"오류: {e}", "stt-idle@2x.png")
        finally:
            self._processing = False
            hide_highlight()


_lock_file = None


def _acquire_single_instance() -> None:
    """파일 락으로 단일 인스턴스를 보장한다. 프로세스 종료 시 OS가 자동 해제."""
    global _lock_file
    lock_path = "/tmp/ttstt.lock"
    _lock_file = open(lock_path, "w")
    try:
        fcntl.flock(_lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[ttstt] 이미 실행 중입니다.")
        sys.exit(1)


def main() -> None:
    """엔트리포인트."""
    # stdout을 line-buffered로 설정 (파일 리다이렉트 시에도 즉시 출력)
    sys.stdout.reconfigure(line_buffering=True)
    _acquire_single_instance()
    config = load_config()

    if not check_accessibility():
        sys.exit(1)

    app = TtsttApp(config)

    # 스트림을 열어 디바이스 연결 유지
    app.recorder.open_stream()

    # ASR 모델을 미리 로드 (첫 인식 지연 제거)
    def _preload():
        from ttstt.asr import _load_model
        _load_model(config.asr)

    threading.Thread(target=_preload, daemon=True).start()

    # 업데이트 체크 (백그라운드)
    def _check_updates():
        from ttstt.updates import check_update
        result = check_update()
        if result:
            version, url = result
            app.notify_update(version, url)

    threading.Thread(target=_check_updates, daemon=True).start()

    # 글로벌 핫키를 별도 스레드에서 실행
    app.start_hotkey()

    # rumps 이벤트 루프 (메인 스레드)
    app.run()
