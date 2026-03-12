"""글로벌 단축키 모듈.

pyobjc-framework-Quartz의 CGEventTap을 사용해 글로벌 핫키를 감지한다.
macOS 접근성(Accessibility) 권한이 필요하다.
"""

from __future__ import annotations

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
    """글로벌 핫키를 등록하고 이벤트 루프를 실행한다.

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
