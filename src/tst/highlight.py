"""포커스 윈도우 하이라이트 오버레이.

녹음 중 STT 입력이 어디로 갈지 시각적으로 표시한다.
show_highlight() / hide_highlight()는 아무 스레드에서 호출 가능.
"""

from __future__ import annotations

import math
import time

import objc
import Quartz
from AppKit import (
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSScreen,
    NSView,
    NSWindow,
    NSWorkspace,
)
from Foundation import NSObject, NSPoint, NSRect, NSSize, NSThread, NSTimer

GLOW_DEPTH = 12
BORDER_RADIUS = 10.0
BASE_COLOR = (0.25, 0.55, 1.0)
TRACK_INTERVAL = 0.3


def _get_focused_window_bounds() -> tuple[float, float, float, float] | None:
    """포커스된 윈도우의 (x, y, w, h)를 반환한다. Quartz 좌표계."""
    active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if active_app is None:
        return None
    pid = active_app.processIdentifier()

    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    if window_list is None:
        return None

    for win in window_list:
        if win.get(Quartz.kCGWindowOwnerPID) != pid:
            continue
        if win.get(Quartz.kCGWindowLayer, -1) != 0:
            continue
        bounds = win.get(Quartz.kCGWindowBounds)
        if bounds is None:
            continue
        x, y, w, h = bounds["X"], bounds["Y"], bounds["Width"], bounds["Height"]
        if w < 50 or h < 50:
            continue
        return (x, y, w, h)
    return None


def _quartz_to_cocoa_rect(x: float, y: float, w: float, h: float) -> NSRect:
    screen_h = NSScreen.mainScreen().frame().size.height
    return NSRect(NSPoint(x, screen_h - y - h), NSSize(w, h))


class _HighlightView(NSView):
    _alpha = 1.0

    def drawRect_(self, rect):
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(rect)

        bounds = self.bounds()
        r, g, b = BASE_COLOR
        a = self._alpha

        layers = 8
        for i in range(layers):
            t = i / layers
            inset_d = GLOW_DEPTH * t
            inset_rect = NSRect(
                NSPoint(bounds.origin.x + inset_d, bounds.origin.y + inset_d),
                NSSize(bounds.size.width - inset_d * 2, bounds.size.height - inset_d * 2),
            )
            alpha = a * 0.35 * (1 - t)
            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                inset_rect, BORDER_RADIUS, BORDER_RADIUS
            )
            path.setLineWidth_(GLOW_DEPTH / layers * 2)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, alpha).set()
            path.stroke()


class _HighlightOverlay(NSObject):

    def init(self):
        self = objc.super(_HighlightOverlay, self).init()
        if self is None:
            return None
        rect = NSRect(NSPoint(0, 0), NSSize(100, 100))
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, 0, NSBackingStoreBuffered, False,
        )
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setLevel_(Quartz.kCGFloatingWindowLevel)
        self.window.setIgnoresMouseEvents_(True)
        self.window.setHasShadow_(False)
        self.window.setCollectionBehavior_(
            (1 << 0) | (1 << 4) | (1 << 9)
        )
        self.view = _HighlightView.alloc().initWithFrame_(rect)
        self.window.setContentView_(self.view)
        self._anim_timer = None
        self._track_timer = None
        self._start_time = 0.0
        return self

    def show(self):
        """오버레이 표시. 메인 스레드에서 호출해야 한다."""
        bounds = _get_focused_window_bounds()
        if bounds is None:
            return
        cocoa_rect = _quartz_to_cocoa_rect(*bounds)
        self.window.setFrame_display_(cocoa_rect, True)
        self._start_time = time.monotonic()
        self.window.orderFront_(None)
        _schedule = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_
        if self._anim_timer is None:
            self._anim_timer = _schedule(
                1.0 / 30, self,
                objc.selector(self._animate_, signature=b"v@:@"),
                None, True,
            )
        if self._track_timer is None:
            self._track_timer = _schedule(
                TRACK_INTERVAL, self,
                objc.selector(self._track_, signature=b"v@:@"),
                None, True,
            )

    def hide(self):
        """오버레이 숨김. 메인 스레드에서 호출해야 한다."""
        self.window.orderOut_(None)
        if self._anim_timer:
            self._anim_timer.invalidate()
            self._anim_timer = None
        if self._track_timer:
            self._track_timer.invalidate()
            self._track_timer = None

    def _animate_(self, timer):
        if not self.window.isVisible():
            return
        elapsed = time.monotonic() - self._start_time
        t = (math.sin(elapsed * 2 * math.pi / 1.8) + 1) / 2
        self.view._alpha = 0.4 + t * 0.6
        self.view.setNeedsDisplay_(True)

    def _track_(self, timer):
        if not self.window.isVisible():
            return
        bounds = _get_focused_window_bounds()
        if bounds is None:
            return
        cocoa_rect = _quartz_to_cocoa_rect(*bounds)
        self.window.setFrame_display_(cocoa_rect, True)


# --- 메인 스레드 디스패치 ---

class _Dispatcher(NSObject):
    _instance = None

    @classmethod
    def shared(cls):
        if cls._instance is None:
            cls._instance = cls.alloc().init()
        return cls._instance

    def doShow_(self, obj):
        _ensure_overlay().show()

    def doHide_(self, obj):
        overlay = _overlay_ref
        if overlay is not None:
            overlay.hide()


_overlay_ref: _HighlightOverlay | None = None


def _ensure_overlay() -> _HighlightOverlay:
    global _overlay_ref
    if _overlay_ref is None:
        _overlay_ref = _HighlightOverlay.alloc().init()
    return _overlay_ref


def show_highlight() -> None:
    """하이라이트 표시. 아무 스레드에서 호출 가능."""
    d = _Dispatcher.shared()
    if NSThread.isMainThread():
        d.doShow_(None)
    else:
        d.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(d.doShow_, signature=b"v@:@"), None, False,
        )


def hide_highlight() -> None:
    """하이라이트 숨김. 아무 스레드에서 호출 가능."""
    d = _Dispatcher.shared()
    if NSThread.isMainThread():
        d.doHide_(None)
    else:
        d.performSelectorOnMainThread_withObject_waitUntilDone_(
            objc.selector(d.doHide_, signature=b"v@:@"), None, False,
        )
