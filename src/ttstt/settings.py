"""설정 창 모듈.

pyobjc AppKit으로 네이티브 NSWindow를 생성한다.
모든 ObjC 객체 참조를 모듈 레벨에서 유지하여 Python GC에 의한 조기 해제를 방지한다.
"""

from __future__ import annotations

from collections.abc import Callable

import objc
from AppKit import (
    NSBezelStyleRounded,
    NSButton,
    NSFont,
    NSMakeRect,
    NSObject,
    NSPopUpButton,
    NSTextField,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskTitled,
)

from ttstt.config import HotkeyConfig
from ttstt.hotkey import KEY_OPTIONS, MODIFIER_OPTIONS

# 모듈 레벨에서 ObjC 객체 참조를 유지하여 GC 방지
_refs: dict = {}


def _make_label(text: str, x: float, y: float, width: float = 80) -> NSTextField:
    label = NSTextField.alloc().initWithFrame_(NSMakeRect(x, y, width, 20))
    label.setStringValue_(text)
    label.setBezeled_(False)
    label.setDrawsBackground_(False)
    label.setEditable_(False)
    label.setSelectable_(False)
    label.setFont_(NSFont.systemFontOfSize_(13))
    return label


class _Delegate(NSObject):
    """NSButton/NSPopUpButton 타겟. ObjC 런타임에서 참조되므로 GC 방지 필수."""

    @objc.python_method
    def setup(self, on_mode, on_save):
        self._on_mode = on_mode
        self._on_save = on_save
        return self

    @objc.IBAction
    def onModeChanged_(self, sender):
        if self._on_mode:
            self._on_mode(sender)

    @objc.IBAction
    def onSave_(self, sender):
        if self._on_save:
            self._on_save(sender)


def show_settings(
    hotkey_config: HotkeyConfig,
    on_save: Callable[[HotkeyConfig], None],
) -> None:
    """설정 NSWindow를 표시한다."""
    # 이전 창이 열려있으면 앞으로 가져오기
    if "window" in _refs:
        win = _refs["window"]
        if win.isVisible():
            win.orderFrontRegardless()
            return

    width, height = 320, 200
    style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, width, height), style, 2, False
    )
    window.setTitle_("ttstt 설정")
    window.center()

    content = window.contentView()
    control_x, control_w, row_h = 110, 180, 40

    # 모드
    y = height - 50
    content.addSubview_(_make_label("모드", 20, y))
    mode_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    mode_popup.addItemsWithTitles_(["tap_hold", "toggle"])
    mode_popup.selectItemWithTitle_(hotkey_config.mode)
    content.addSubview_(mode_popup)

    # 키
    y -= row_h
    content.addSubview_(_make_label("키", 20, y))
    key_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    key_popup.addItemsWithTitles_(KEY_OPTIONS)
    key_popup.selectItemWithTitle_(hotkey_config.key)
    content.addSubview_(key_popup)

    # Modifier
    y -= row_h
    content.addSubview_(_make_label("Modifier", 20, y))
    modifier_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    modifier_popup.addItemsWithTitles_(MODIFIER_OPTIONS)
    if hotkey_config.modifier in MODIFIER_OPTIONS:
        modifier_popup.selectItemWithTitle_(hotkey_config.modifier)
    modifier_popup.setEnabled_(hotkey_config.mode == "toggle")
    content.addSubview_(modifier_popup)

    # 콜백
    def on_mode_changed(sender):
        is_toggle = mode_popup.titleOfSelectedItem() == "toggle"
        modifier_popup.setEnabled_(is_toggle)

    def on_save_clicked(sender):
        new_config = HotkeyConfig(
            mode=mode_popup.titleOfSelectedItem(),
            key=key_popup.titleOfSelectedItem(),
            modifier=modifier_popup.titleOfSelectedItem(),
        )
        on_save(new_config)
        window.close()

    delegate = _Delegate.alloc().init()
    delegate.setup(on_mode_changed, on_save_clicked)

    mode_popup.setTarget_(delegate)
    mode_popup.setAction_(b"onModeChanged:")

    # 저장 버튼
    y -= row_h + 5
    save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(width - 100, y, 80, 32))
    save_btn.setTitle_("저장")
    save_btn.setBezelStyle_(NSBezelStyleRounded)
    save_btn.setTarget_(delegate)
    save_btn.setAction_(b"onSave:")
    content.addSubview_(save_btn)

    # 모듈 레벨에서 강한 참조 유지 (GC 방지)
    _refs["window"] = window
    _refs["delegate"] = delegate
    _refs["popups"] = (mode_popup, key_popup, modifier_popup)

    window.orderFrontRegardless()
