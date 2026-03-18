"""설정 창 모듈.

pyobjc AppKit으로 네이티브 NSWindow를 생성한다.
모든 ObjC 객체 참조를 모듈 레벨에서 유지하여 Python GC에 의한 조기 해제를 방지한다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

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

from ttstt.config import AppearanceConfig, HotkeyConfig
from ttstt.hotkey import KEY_OPTIONS, MODIFIER_OPTIONS

ICON_THEMES = ["speech-bubble", "blob"]
ICON_THEME_LABELS = {"speech-bubble": "말풍선", "blob": "블롭"}

MODE_LABELS = {"tap_hold": "탭+홀드", "toggle": "조합키 토글"}
MODE_KEYS = {v: k for k, v in MODE_LABELS.items()}

# 모듈 레벨에서 ObjC 객체 참조를 유지하여 GC 방지
_refs: dict = {}


@dataclass
class SettingsResult:
    hotkey: HotkeyConfig
    appearance: AppearanceConfig


def _make_label(text: str, x: float, y: float, width: float = 100) -> NSTextField:
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
    appearance_config: AppearanceConfig,
    on_save: Callable[[SettingsResult], None],
) -> None:
    """설정 NSWindow를 표시한다."""
    # 이전 창이 있으면 재사용 (GC로 인한 ObjC 크래시 방지)
    if "window" in _refs:
        win = _refs["window"]
        win.orderFrontRegardless()
        return

    width, height = 340, 330
    style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(0, 0, width, height), style, 2, False
    )
    window.setTitle_("ttstt 설정")
    window.center()

    content = window.contentView()
    label_x, control_x, control_w, row_h = 20, 120, 190, 32

    y = height - 40

    # --- 외관 ---
    content.addSubview_(_make_label("아이콘 테마", label_x, y))
    theme_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    theme_labels = [ICON_THEME_LABELS[t] for t in ICON_THEMES]
    theme_popup.addItemsWithTitles_(theme_labels)
    current_label = ICON_THEME_LABELS.get(appearance_config.icon_theme, theme_labels[0])
    theme_popup.selectItemWithTitle_(current_label)
    content.addSubview_(theme_popup)

    y -= row_h + 10

    # --- 핫키 ---
    content.addSubview_(_make_label("녹음 모드", label_x, y))
    mode_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    mode_labels = list(MODE_LABELS.values())
    mode_popup.addItemsWithTitles_(mode_labels)
    mode_popup.selectItemWithTitle_(MODE_LABELS.get(hotkey_config.mode, mode_labels[0]))
    content.addSubview_(mode_popup)

    y -= row_h
    content.addSubview_(_make_label("녹음 키", label_x, y))
    key_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    key_popup.addItemsWithTitles_(KEY_OPTIONS)
    key_popup.selectItemWithTitle_(hotkey_config.key)
    content.addSubview_(key_popup)

    y -= row_h
    modifier_label = _make_label("조합키", label_x, y)
    content.addSubview_(modifier_label)
    modifier_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    modifier_popup.addItemsWithTitles_(MODIFIER_OPTIONS)
    if hotkey_config.modifier in MODIFIER_OPTIONS:
        modifier_popup.selectItemWithTitle_(hotkey_config.modifier)
    modifier_popup.setEnabled_(hotkey_config.mode == "toggle")
    content.addSubview_(modifier_popup)

    y -= row_h + 10

    # --- 재붙여넣기 ---
    content.addSubview_(_make_label("재붙여넣기 키", label_x, y))
    repaste_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    repaste_popup.addItemsWithTitles_(KEY_OPTIONS)
    repaste_popup.selectItemWithTitle_(hotkey_config.repaste_key)
    content.addSubview_(repaste_popup)

    y -= row_h
    repaste_mod_label = _make_label("재붙여넣기 조합", label_x, y)
    content.addSubview_(repaste_mod_label)
    repaste_mod_popup = NSPopUpButton.alloc().initWithFrame_pullsDown_(
        NSMakeRect(control_x, y - 2, control_w, 26), False
    )
    repaste_mod_popup.addItemsWithTitles_(MODIFIER_OPTIONS)
    if hotkey_config.repaste_modifier in MODIFIER_OPTIONS:
        repaste_mod_popup.selectItemWithTitle_(hotkey_config.repaste_modifier)
    # tap_hold 모드에서는 더블탭이므로 modifier 비활성
    repaste_mod_popup.setEnabled_(hotkey_config.mode == "toggle")
    content.addSubview_(repaste_mod_popup)

    # --- 콜백 ---
    def on_mode_changed(sender):
        is_toggle = MODE_KEYS.get(mode_popup.titleOfSelectedItem()) == "toggle"
        modifier_popup.setEnabled_(is_toggle)
        repaste_mod_popup.setEnabled_(is_toggle)

    def on_save_clicked(sender):
        selected_theme_label = theme_popup.titleOfSelectedItem()
        theme_key = next(k for k, v in ICON_THEME_LABELS.items() if v == selected_theme_label)
        mode_key = MODE_KEYS.get(mode_popup.titleOfSelectedItem(), "tap_hold")

        result = SettingsResult(
            hotkey=HotkeyConfig(
                mode=mode_key,
                key=key_popup.titleOfSelectedItem(),
                modifier=modifier_popup.titleOfSelectedItem(),
                repaste_key=repaste_popup.titleOfSelectedItem(),
                repaste_modifier=repaste_mod_popup.titleOfSelectedItem(),
            ),
            appearance=AppearanceConfig(icon_theme=theme_key),
        )
        on_save(result)
        window.orderOut_(None)

    delegate = _Delegate.alloc().init()
    delegate.setup(on_mode_changed, on_save_clicked)

    mode_popup.setTarget_(delegate)
    mode_popup.setAction_(b"onModeChanged:")

    # --- 저장 버튼 ---
    y -= row_h + 8
    save_btn = NSButton.alloc().initWithFrame_(NSMakeRect(width - 100, y, 80, 32))
    save_btn.setTitle_("저장")
    save_btn.setBezelStyle_(NSBezelStyleRounded)
    save_btn.setTarget_(delegate)
    save_btn.setAction_(b"onSave:")
    content.addSubview_(save_btn)

    # 모듈 레벨에서 강한 참조 유지 (GC 방지)
    _refs["window"] = window
    _refs["delegate"] = delegate
    _refs["popups"] = (theme_popup, mode_popup, key_popup, modifier_popup,
                       repaste_popup, repaste_mod_popup)

    window.orderFrontRegardless()
