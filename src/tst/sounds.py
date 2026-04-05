"""시스템 사운드 재생 모듈.

macOS NSSound를 사용해 시스템 사운드를 재생한다.
/System/Library/Sounds/ 디렉토리에 있는 사운드 이름을 사용.
"""

from __future__ import annotations

import time

from AppKit import NSSound


def play(name: str, wait: bool = False) -> bool:
    """이름으로 시스템 사운드를 재생한다.

    Args:
        name: 시스템 사운드 이름.
        wait: True면 사운드 길이만큼 대기한다.
    """
    sound = NSSound.soundNamed_(name)
    if sound is None:
        return False
    sound.play()
    if wait:
        time.sleep(sound.duration())
    return True
