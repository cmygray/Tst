"""클립보드 swap 모듈.

기존 클립보드를 백업하고, ASR 결과를 클립보드에 넣고,
Cmd+V를 시뮬레이션해서 붙여넣은 뒤, 원래 클립보드를 복원한다.
"""

from __future__ import annotations

import time

import Quartz
from AppKit import NSData, NSPasteboard, NSPasteboardItem

# 'V' 키의 가상 키코드 (ANSI)
_VK_V = 0x09


def _backup() -> list[dict[str, NSData]]:
    """현재 클립보드의 모든 아이템과 타입을 백업한다."""
    pb = NSPasteboard.generalPasteboard()
    items = pb.pasteboardItems()
    if items is None:
        return []

    backup = []
    for item in items:
        item_data = {}
        for ptype in item.types():
            data = item.dataForType_(ptype)
            if data is not None:
                item_data[ptype] = NSData.dataWithData_(data)
        backup.append(item_data)
    return backup


def _restore(backup: list[dict[str, NSData]]) -> None:
    """백업된 내용을 클립보드에 복원한다."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()

    if not backup:
        return

    new_items = []
    for item_data in backup:
        new_item = NSPasteboardItem.alloc().init()
        for ptype, data in item_data.items():
            new_item.setData_forType_(data, ptype)
        new_items.append(new_item)

    pb.writeObjects_(new_items)


def _set_string(text: str) -> None:
    """클립보드에 텍스트를 설정한다."""
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    pb.setString_forType_(text, "public.utf8-plain-text")


def _simulate_cmd_v() -> None:
    """Cmd+V 키 이벤트를 시뮬레이션한다."""
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)

    down = Quartz.CGEventCreateKeyboardEvent(source, _VK_V, True)
    Quartz.CGEventSetFlags(down, Quartz.kCGEventFlagMaskCommand)

    up = Quartz.CGEventCreateKeyboardEvent(source, _VK_V, False)
    Quartz.CGEventSetFlags(up, Quartz.kCGEventFlagMaskCommand)

    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, down)
    Quartz.CGEventPost(Quartz.kCGAnnotatedSessionEventTap, up)


def paste_text(text: str) -> None:
    """Clipboard swap 패턴으로 텍스트를 현재 포커스 위치에 붙여넣는다.

    1. 기존 클립보드 백업
    2. ASR 결과를 클립보드에 설정
    3. Cmd+V 시뮬레이션
    4. 잠시 대기 (붙여넣기 처리 시간)
    5. 원래 클립보드 복원
    """
    backup = _backup()
    _set_string(text)
    _simulate_cmd_v()
    time.sleep(0.15)
    _restore(backup)
