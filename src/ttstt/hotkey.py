"""글로벌 단축키 모듈.

pyobjc-framework-Quartz의 CGEventTap을 사용해 글로벌 핫키를 감지한다.
macOS 접근성(Accessibility) 권한이 필요하다.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

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
}

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

    권한이 없으면 시스템 설정 다이얼로그를 트리거한다.
    """
    trusted = Quartz.CGPreflightListenEventAccess()
    if not trusted:
        Quartz.CGRequestListenEventAccess()
        return False
    return True


def listen(modifier: str, key: str, on_toggle: Callable[[], None]) -> None:
    """글로벌 핫키를 등록하고 이벤트 루프를 실행한다. (토글 모드)

    Args:
        modifier: 'cmd+shift' 형태의 modifier 문자열.
        key: 알파벳 소문자 한 글자.
        on_toggle: 핫키가 눌렸을 때 호출할 콜백.
    """
    target_keycode = _KEY_CODES.get(key.lower())
    if target_keycode is None:
        raise ValueError(f"지원하지 않는 키: {key}")

    required_flags = _parse_modifier(modifier)
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

        if keycode == target_keycode and flags == required_flags:
            on_toggle()
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

    print(f"ttstt 대기 중... ({modifier}+{key} 로 녹음 토글)")
    Quartz.CFRunLoopRun()


def listen_tap_hold(
    key: str,
    on_start: Callable[[], None],
    on_stop: Callable[[], None],
    hold_threshold: float = 0.3,
) -> None:
    """탭 & 홀드 방식으로 글로벌 핫키를 감지한다.

    짧게 누르면 원래 키 입력이 그대로 전달되고,
    hold_threshold 이상 누르고 있으면 녹음을 시작하고 떼면 중지한다.

    Args:
        key: 키 이름 (예: 'space').
        on_start: 홀드 시작 시 호출할 콜백.
        on_stop: 키를 뗐을 때 호출할 콜백.
        hold_threshold: 홀드 판정 시간 (초).
    """
    target_keycode = _KEY_CODES.get(key)
    if target_keycode is None:
        raise ValueError(f"지원하지 않는 키: {key}")

    all_modifier_mask = (
        Quartz.kCGEventFlagMaskCommand
        | Quartz.kCGEventFlagMaskShift
        | Quartz.kCGEventFlagMaskAlternate
        | Quartz.kCGEventFlagMaskControl
    )

    state = {
        "pressed": False,
        "holding": False,
        "timer": None,
        "inject_count": 0,
        "press_flags": 0,
    }

    def _start_if_held():
        """타이머 콜백: threshold 경과 후에도 키가 눌려있으면 녹음 시작."""
        if state["pressed"] and not state["holding"]:
            state["holding"] = True
            on_start()

    def _inject_key(flags):
        """원래 키 이벤트를 재주입한다 (짧은 탭 시)."""
        state["inject_count"] = 2
        down = Quartz.CGEventCreateKeyboardEvent(None, target_keycode, True)
        up = Quartz.CGEventCreateKeyboardEvent(None, target_keycode, False)
        if flags:
            Quartz.CGEventSetFlags(down, flags)
            Quartz.CGEventSetFlags(up, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)

    def callback(proxy, event_type, event, refcon):
        if event_type == Quartz.kCGEventTapDisabledByTimeout:
            Quartz.CGEventTapEnable(tap, True)
            return event

        keycode = Quartz.CGEventGetIntegerValueField(
            event, Quartz.kCGKeyboardEventKeycode
        )
        if keycode != target_keycode:
            return event

        # 재주입된 이벤트는 그대로 통과
        if state["inject_count"] > 0:
            state["inject_count"] -= 1
            return event

        flags = Quartz.CGEventGetFlags(event) & all_modifier_mask

        if event_type == Quartz.kCGEventKeyDown:
            # modifier가 눌린 상태면 통과 (Cmd+Space, Shift+Space 등)
            if flags:
                return event

            is_repeat = Quartz.CGEventGetIntegerValueField(
                event, Quartz.kCGKeyboardEventAutorepeat
            )
            if is_repeat:
                return None  # 리피트 소비

            if state["holding"]:
                return None

            # 키 누름 시작 — 이벤트 소비하고 타이머 시작
            state["pressed"] = True
            state["press_flags"] = flags
            if state["timer"]:
                state["timer"].cancel()
            timer = threading.Timer(hold_threshold, _start_if_held)
            timer.daemon = True
            timer.start()
            state["timer"] = timer
            return None

        elif event_type == Quartz.kCGEventKeyUp:
            # modifier 상태의 keyUp이고 우리가 추적 중이 아니면 통과
            if not state["pressed"] and not state["holding"]:
                return event

            state["pressed"] = False
            if state["timer"]:
                state["timer"].cancel()
                state["timer"] = None

            if state["holding"]:
                # 홀드 해제 → 녹음 중지
                state["holding"] = False
                on_stop()
                return None
            else:
                # 짧은 탭 → 원래 키 이벤트 재주입
                _inject_key(state["press_flags"])
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

    print(f"ttstt 대기 중... ({key} 탭+홀드로 녹음)")
    Quartz.CFRunLoopRun()
