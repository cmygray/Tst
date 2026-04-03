"""글로벌 단축키 모듈.

pyobjc-framework-Quartz의 CGEventTap을 사용해 글로벌 핫키를 감지한다.
macOS 접근성(Accessibility) 권한이 필요하다.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

import ctypes
import ctypes.util

import Quartz

# ANSI 가상 키코드 매핑
_KEY_CODES: dict[str, int] = {
    "a": 0x00, "b": 0x0B, "c": 0x08, "d": 0x02, "e": 0x0E,
    "f": 0x03, "g": 0x05, "h": 0x04, "i": 0x22, "j": 0x26,
    "k": 0x28, "l": 0x25, "m": 0x2E, "n": 0x2D, "o": 0x1F,
    "p": 0x23, "q": 0x0C, "r": 0x0F, "s": 0x01, "t": 0x11,
    "u": 0x20, "v": 0x09, "w": 0x0D, "x": 0x07, "y": 0x10,
    "z": 0x06,
    "\\": 0x2A,
    "space": 0x31,
    ";": 0x29,
}

# 설정 UI에서 사용할 키 목록
KEY_OPTIONS = list(_KEY_CODES.keys())

# 설정 UI에서 사용할 modifier 프리셋
MODIFIER_OPTIONS = [
    "없음", "option", "cmd", "shift", "ctrl",
    "cmd+shift", "cmd+option", "ctrl+shift", "cmd+ctrl",
]

# modifier 문자열 → CGEventFlag 매핑
_MODIFIER_FLAGS: dict[str, int] = {
    "cmd": Quartz.kCGEventFlagMaskCommand,
    "shift": Quartz.kCGEventFlagMaskShift,
    "option": Quartz.kCGEventFlagMaskAlternate,
    "alt": Quartz.kCGEventFlagMaskAlternate,
    "ctrl": Quartz.kCGEventFlagMaskControl,
}


def _parse_modifier(modifier_str: str) -> int:
    """'cmd+shift' 형태의 문자열을 CGEventFlag 비트마스크로 변환한다."""
    flags = 0
    for part in modifier_str.lower().split("+"):
        part = part.strip()
        if part in _MODIFIER_FLAGS:
            flags |= _MODIFIER_FLAGS[part]
    return flags


def check_accessibility() -> bool:
    """접근성 권한이 부여되었는지 확인한다.

    권한이 없으면 macOS가 시스템 설정 접근성 패널을 자동으로 열어준다.
    """
    _cf = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreFoundation"))
    _as = ctypes.cdll.LoadLibrary(
        "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"
    )

    # kAXTrustedCheckOptionPrompt CFString 상수
    prompt_key = ctypes.c_void_p.in_dll(_as, "kAXTrustedCheckOptionPrompt")

    # CFDictionary 생성: {kAXTrustedCheckOptionPrompt: kCFBooleanTrue}
    cf_true = ctypes.c_void_p.in_dll(_cf, "kCFBooleanTrue")

    _cf.CFDictionaryCreate.restype = ctypes.c_void_p
    _cf.CFDictionaryCreate.argtypes = [
        ctypes.c_void_p,  # allocator
        ctypes.POINTER(ctypes.c_void_p),  # keys
        ctypes.POINTER(ctypes.c_void_p),  # values
        ctypes.c_long,  # numValues
        ctypes.c_void_p,  # keyCallBacks
        ctypes.c_void_p,  # valueCallBacks
    ]
    keys = (ctypes.c_void_p * 1)(prompt_key)
    values = (ctypes.c_void_p * 1)(cf_true)
    options = _cf.CFDictionaryCreate(None, keys, values, 1, None, None)

    _as.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
    _as.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
    trusted = _as.AXIsProcessTrustedWithOptions(options)

    _cf.CFRelease.argtypes = [ctypes.c_void_p]
    _cf.CFRelease(options)

    return trusted


def _setup_stop_watcher(
    stop_event: threading.Event | None,
    tap,
    run_loop,
) -> None:
    """stop_event가 set되면 CGEventTap을 비활성화하고 CFRunLoop를 중지한다."""
    if stop_event is None:
        return

    def _watcher():
        stop_event.wait()
        Quartz.CGEventTapEnable(tap, False)
        Quartz.CFRunLoopStop(run_loop)

    threading.Thread(target=_watcher, daemon=True).start()


Binding = tuple[str, str, Callable[[], None]]


def listen(modifier: str, key: str, on_toggle: Callable[[], None],
           extra_bindings: list[Binding] | None = None,
           stop_event: threading.Event | None = None) -> None:
    """글로벌 핫키를 등록하고 이벤트 루프를 실행한다.

    Args:
        modifier: 'cmd+shift' 형태의 modifier 문자열.
        key: 알파벳 소문자 한 글자.
        on_toggle: 핫키가 눌렸을 때 호출할 콜백.
        extra_bindings: 추가 (modifier, key, callback) 바인딩 목록.
    """
    # 모든 바인딩을 (keycode, flags, callback) 으로 변환
    bindings: list[tuple[int, int, Callable[[], None]]] = []

    def _add_binding(mod: str, k: str, cb: Callable[[], None]) -> None:
        keycode = _KEY_CODES.get(k.lower())
        if keycode is None:
            raise ValueError(f"지원하지 않는 키: {k}")
        bindings.append((keycode, _parse_modifier(mod), cb))

    _add_binding(modifier, key, on_toggle)
    for mod, k, cb in extra_bindings or []:
        _add_binding(mod, k, cb)

    all_modifier_mask = (
        Quartz.kCGEventFlagMaskCommand
        | Quartz.kCGEventFlagMaskShift
        | Quartz.kCGEventFlagMaskAlternate
        | Quartz.kCGEventFlagMaskControl
    )

    def callback(proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            Quartz.CGEventTapEnable(tap, True)
            return event

        if event_type != Quartz.kCGEventKeyDown:
            return event

        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )
        flags = Quartz.CGEventGetFlags(event) & all_modifier_mask

        for target_keycode, required_flags, cb in bindings:
            if keycode == target_keycode and flags == required_flags:
                cb()
                return None  # 이벤트 소비

        return event

    event_mask = Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)

    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,
        event_mask,
        callback,
        None,
    )

    if tap is None:
        raise RuntimeError(
            "이벤트 탭 생성 실패. 시스템 설정 > 개인 정보 보호 및 보안 > 접근성에서 "
            "ttstt를 허용해주세요."
        )

    source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(),
        source,
        Quartz.kCFRunLoopDefaultMode,
    )
    Quartz.CGEventTapEnable(tap, True)

    run_loop = Quartz.CFRunLoopGetCurrent()
    _setup_stop_watcher(stop_event, tap, run_loop)

    labels = [f"{modifier}+{key} 로 녹음 토글"]
    for mod, k, _ in extra_bindings or []:
        labels.append(f"{mod}+{k} 로 재붙여넣기")
    print(f"ttstt 대기 중... ({', '.join(labels)})")
    Quartz.CFRunLoopRun()


def listen_tap_hold(
    key: str,
    on_start: Callable[[], None],
    on_stop: Callable[[], None],
    hold_threshold: float = 0.3,
    on_repaste: Callable[[], None] | None = None,
    repaste_key: str = "\\",
    repaste_threshold: float = 0.13,
    stop_event: threading.Event | None = None,
    modifier: str = "",
) -> None:
    """탭 & 홀드 방식으로 글로벌 핫키를 감지한다.

    짧게 누르면 원래 키 입력이 그대로 전달되고,
    hold_threshold 이상 누르고 있으면 녹음을 시작하고 떼면 중지한다.
    repaste_key를 빠르게 두 번 누르면 on_repaste 콜백을 호출한다.

    Args:
        key: 키 이름 (예: 'space').
        on_start: 홀드 시작 시 호출할 콜백.
        on_stop: 키를 뗐을 때 호출할 콜백.
        hold_threshold: 홀드 판정 시간 (초).
        on_repaste: repaste_key 더블탭 시 호출할 콜백 (None이면 비활성).
        repaste_key: 더블탭 감지 대상 키 (기본 '\\').
        repaste_threshold: 더블탭 판정 시간 (초).
    """
    target_keycode = _KEY_CODES.get(key)
    if target_keycode is None:
        raise ValueError(f"지원하지 않는 키: {key}")

    required_flags = _parse_modifier(modifier) if modifier else 0

    all_modifier_mask = (
        Quartz.kCGEventFlagMaskCommand
        | Quartz.kCGEventFlagMaskShift
        | Quartz.kCGEventFlagMaskAlternate
        | Quartz.kCGEventFlagMaskControl
    )

    repaste_keycode = _KEY_CODES.get(repaste_key) if on_repaste else None

    lock = threading.Lock()
    state = {
        "pressed": False,
        "holding": False,
        "timer": None,
        "inject_count": 0,
        "press_flags": 0,
        "repaste_pending": False,  # 첫 번째 \\ 대기 중
        "repaste_timer": None,  # 더블탭 대기 타이머
        "repaste_consumed": False,  # 더블탭 감지로 두 번째 키를 소비 중
    }

    def _inject_repaste_key():
        """더블탭 대기 타임아웃: 단일 \\ 입력으로 확정 → 키 주입."""
        state["repaste_pending"] = False
        state["inject_count"] += 2
        down = Quartz.CGEventCreateKeyboardEvent(None, repaste_keycode, True)
        up = Quartz.CGEventCreateKeyboardEvent(None, repaste_keycode, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def _start_if_held():
        """타이머 콜백: threshold 경과 후에도 키가 눌려있으면 녹음 시작."""
        with lock:
            print(f"[hotkey] timer fired: pressed={state['pressed']}, holding={state['holding']}", flush=True)
            if state["pressed"] and not state["holding"]:
                state["holding"] = True
            else:
                return
        # lock 밖에서 부수효과 실행 (lock 점유 최소화)
        bs_down = Quartz.CGEventCreateKeyboardEvent(None, 0x33, True)
        bs_up = Quartz.CGEventCreateKeyboardEvent(None, 0x33, False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, bs_down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, bs_up)
        print("[hotkey] on_start()", flush=True)
        on_start()

    def callback(proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            Quartz.CGEventTapEnable(tap, True)
            return event

        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )

        # repaste 키 (\\) 더블탭 감지 — 지연 방식
        if repaste_keycode is not None and keycode == repaste_keycode:
            # 재주입된 이벤트는 그대로 통과
            if state["inject_count"] > 0:
                state["inject_count"] -= 1
                return event
            if event_type == Quartz.kCGEventKeyDown:
                if state["repaste_consumed"]:
                    return None  # 더블탭 두 번째 keyDown 소비
                if state["repaste_pending"]:
                    # 두 번째 \\ → 더블탭 확정
                    state["repaste_consumed"] = True
                    state["repaste_pending"] = False
                    if state["repaste_timer"]:
                        state["repaste_timer"].cancel()
                        state["repaste_timer"] = None
                    on_repaste()
                    return None
                # 첫 번째 \\ → 대기 (즉시 통과시키지 않음)
                state["repaste_pending"] = True
                timer = threading.Timer(repaste_threshold, _inject_repaste_key)
                timer.daemon = True
                timer.start()
                state["repaste_timer"] = timer
                return None
            elif event_type == Quartz.kCGEventKeyUp:
                if state["repaste_consumed"]:
                    state["repaste_consumed"] = False
                    return None  # 더블탭 두 번째 keyUp 소비
                if state["repaste_pending"]:
                    return None  # 첫 번째 keyUp도 대기 중이므로 소비
                return event
            return event

        if keycode != target_keycode:
            return event

        # 재주입된 이벤트는 그대로 통과
        if state["inject_count"] > 0:
            state["inject_count"] -= 1
            return event

        flags = Quartz.CGEventGetFlags(event) & all_modifier_mask

        if event_type == Quartz.kCGEventKeyDown:
            # 요구된 modifier 조합과 다르면 통과
            if flags != required_flags:
                return event

            is_repeat = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventAutorepeat
            )
            if is_repeat:
                return None  # 리피트 소비

            if state["holding"]:
                return None

            # 키 누름 시작 — 즉시 키 다운 주입하고 타이머 시작
            state["pressed"] = True
            state["press_flags"] = flags
            state["inject_count"] = 1
            down = Quartz.CGEventCreateKeyboardEvent(
                None, target_keycode, True
            )
            if required_flags:
                Quartz.CGEventSetFlags(down, required_flags)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
            if state["timer"]:
                state["timer"].cancel()
            timer = threading.Timer(hold_threshold, _start_if_held)
            timer.daemon = True
            timer.start()
            state["timer"] = timer
            return None

        elif event_type == Quartz.kCGEventKeyUp:
            with lock:
                print(f"[hotkey] keyUp: pressed={state['pressed']}, holding={state['holding']}", flush=True)
                # modifier 상태의 keyUp이고 우리가 추적 중이 아니면 통과
                if not state["pressed"] and not state["holding"]:
                    print("[hotkey] keyUp: not tracked, passing through", flush=True)
                    return event

                state["pressed"] = False
                if state["timer"]:
                    state["timer"].cancel()
                    state["timer"] = None

                was_holding = state["holding"]
                if was_holding:
                    state["holding"] = False

            if was_holding:
                # 홀드 해제 → 녹음 중지
                print("[hotkey] on_stop()", flush=True)
                on_stop()
                return None
            else:
                # 짧은 탭 → 키 다운은 이미 주입됨, 키 업만 주입
                state["inject_count"] = 1
                up = Quartz.CGEventCreateKeyboardEvent(
                    None, target_keycode, False
                )
                if required_flags:
                    Quartz.CGEventSetFlags(up, required_flags)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
                return None

        return event

    event_mask = (
        Quartz.CGEventMaskBit(Quartz.kCGEventKeyDown)
        | Quartz.CGEventMaskBit(Quartz.kCGEventKeyUp)
    )

    tap = Quartz.CGEventTapCreate(
        Quartz.kCGSessionEventTap,
        Quartz.kCGHeadInsertEventTap,
        Quartz.kCGEventTapOptionDefault,
        event_mask,
        callback,
        None,
    )

    if tap is None:
        raise RuntimeError(
            "이벤트 탭 생성 실패. 시스템 설정 > 개인 정보 보호 및 보안 > 접근성에서 "
            "ttstt를 허용해주세요."
        )

    source = Quartz.CFMachPortCreateRunLoopSource(None, tap, 0)
    Quartz.CFRunLoopAddSource(
        Quartz.CFRunLoopGetCurrent(),
        source,
        Quartz.kCFRunLoopDefaultMode,
    )
    Quartz.CGEventTapEnable(tap, True)

    run_loop = Quartz.CFRunLoopGetCurrent()
    _setup_stop_watcher(stop_event, tap, run_loop)

    mod_label = f"{modifier}+" if modifier else ""
    print(f"ttstt 대기 중... ({mod_label}{key} 탭+홀드로 녹음)")
    Quartz.CFRunLoopRun()
