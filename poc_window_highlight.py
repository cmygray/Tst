"""POC: 포커스된 윈도우를 시각적으로 하이라이트.

STT 입력이 어디로 갈지 사용자에게 알려주기 위한 프로토타입.
독립 실행: python poc_window_highlight.py
"""

from __future__ import annotations

import math
import time

import Quartz
from AppKit import (
    NSApplication,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSColor,
    NSScreen,
    NSView,
    NSWindow,
    NSWorkspace,
)
from Foundation import NSObject, NSRect, NSSize, NSPoint, NSTimer
from PyObjCTools import AppHelper
import objc


# --- 포커스 윈도우 bounds 가져오기 ---

def get_focused_window_bounds() -> tuple[float, float, float, float] | None:
    """포커스된 윈도우의 (x, y, w, h)를 반환한다. Quartz 좌표계 (좌상단 원점)."""
    # 현재 활성 앱의 PID
    active_app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if active_app is None:
        return None
    pid = active_app.processIdentifier()

    # 해당 PID의 윈도우 목록
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly | Quartz.kCGWindowListExcludeDesktopElements,
        Quartz.kCGNullWindowID,
    )
    if window_list is None:
        return None

    for win in window_list:
        if win.get(Quartz.kCGWindowOwnerPID) != pid:
            continue
        # 메인 윈도우 (레이어 0, 일반 윈도우)
        if win.get(Quartz.kCGWindowLayer, -1) != 0:
            continue
        bounds = win.get(Quartz.kCGWindowBounds)
        if bounds is None:
            continue
        x = bounds["X"]
        y = bounds["Y"]
        w = bounds["Width"]
        h = bounds["Height"]
        if w < 50 or h < 50:
            continue
        return (x, y, w, h)

    return None


def quartz_to_cocoa_rect(x: float, y: float, w: float, h: float) -> NSRect:
    """Quartz 좌표 (좌상단 원점) → Cocoa 좌표 (좌하단 원점) 변환."""
    screen_h = NSScreen.mainScreen().frame().size.height
    cocoa_y = screen_h - y - h
    return NSRect(NSPoint(x, cocoa_y), NSSize(w, h))


# --- 하이라이트 오버레이 뷰/윈도우 ---

GLOW_DEPTH = 12  # 안쪽으로 번지는 깊이 (px)
BORDER_RADIUS = 10.0
BASE_COLOR = (0.25, 0.55, 1.0)  # 파란 계열


class HighlightView(NSView):
    """안쪽 글로우 테두리를 그리는 뷰."""

    _alpha = 1.0

    def drawRect_(self, rect):
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(rect)

        bounds = self.bounds()
        r, g, b = BASE_COLOR
        a = self._alpha

        # 안쪽 글로우: 가장자리에서 안쪽으로 점점 투명해지는 레이어
        layers = 8
        for i in range(layers):
            t = i / layers  # 0(가장자리) ~ 1(안쪽 깊은곳)
            inset_d = GLOW_DEPTH * t
            inset_rect = NSRect(
                NSPoint(bounds.origin.x + inset_d, bounds.origin.y + inset_d),
                NSSize(bounds.size.width - inset_d * 2, bounds.size.height - inset_d * 2),
            )
            # 가장자리가 가장 진하고, 안쪽으로 갈수록 투명
            alpha = a * 0.35 * (1 - t)

            path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                inset_rect, BORDER_RADIUS, BORDER_RADIUS
            )
            path.setLineWidth_(GLOW_DEPTH / layers * 2)
            NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, alpha).set()
            path.stroke()


class HighlightOverlay(NSObject):
    """포커스 윈도우 위에 글로우 테두리 오버레이를 표시한다."""

    def init(self):
        self = objc.super(HighlightOverlay, self).init()
        if self is None:
            return None
        rect = NSRect(NSPoint(0, 0), NSSize(100, 100))
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            0,  # NSBorderlessWindowMask
            NSBackingStoreBuffered,
            False,
        )
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(NSColor.clearColor())
        self.window.setLevel_(Quartz.kCGFloatingWindowLevel)
        self.window.setIgnoresMouseEvents_(True)
        self.window.setHasShadow_(False)
        self.window.setCollectionBehavior_(
            (1 << 0)  # canJoinAllSpaces
            | (1 << 4)  # stationary
            | (1 << 9)  # fullScreenAuxiliary
        )

        self.view = HighlightView.alloc().initWithFrame_(rect)
        self.window.setContentView_(self.view)

        # 디밍 애니메이션 (1.5초 주기 sine wave)
        self._start_time = time.monotonic()
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0 / 30,  # ~30fps
            self,
            objc.selector(self._animate_, signature=b"v@:@"),
            None,
            True,
        )
        return self

    def _animate_(self, timer) -> None:
        if not self.window.isVisible():
            return
        elapsed = time.monotonic() - self._start_time
        # sine wave: 0.35 ~ 1.0
        t = (math.sin(elapsed * 2 * math.pi / 1.8) + 1) / 2  # 0~1
        self.view._alpha = 0.4 + t * 0.6  # 0.4 ~ 1.0
        self.view.setNeedsDisplay_(True)

    def moveTo_(self, bounds) -> None:
        if bounds is None:
            self.window.orderOut_(None)
            return

        cocoa_rect = quartz_to_cocoa_rect(*bounds)
        self.window.setFrame_display_(cocoa_rect, True)
        if not self.window.isVisible():
            self.window.orderFront_(None)


# --- 앱 델리게이트: 포커스 변경 감시 ---

class AppDelegate(NSObject):
    overlay = objc.ivar()

    def applicationDidFinishLaunching_(self, notification):
        self.overlay = HighlightOverlay.alloc().init()
        self._update_highlight()

        # 활성 앱 변경 알림 구독
        nc = NSWorkspace.sharedWorkspace().notificationCenter()
        nc.addObserver_selector_name_object_(
            self,
            objc.selector(self.onAppActivated_, signature=b"v@:@"),
            "NSWorkspaceDidActivateApplicationNotification",
            None,
        )
        # 폴링으로 윈도우 이동/리사이즈도 감지 (0.3초)
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.3, self, objc.selector(self.pollUpdate_, signature=b"v@:@"), None, True
        )

    def onAppActivated_(self, notification):
        self._update_highlight()

    def pollUpdate_(self, timer):
        self._update_highlight()

    def _update_highlight(self):
        bounds = get_focused_window_bounds()
        self.overlay.moveTo_(bounds)


# --- 메인 ---

def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(2)  # NSApplicationActivationPolicyAccessory (no dock icon)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    print("[poc] 윈도우 하이라이트 POC 시작. Ctrl+C로 종료.")
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
