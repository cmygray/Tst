"""GitHub Releases 기반 업데이트 체크."""

from __future__ import annotations

import json
import urllib.request

from ttstt import __version__

_API_URL = "https://api.github.com/repos/cmygray/ttstt/releases/latest"


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def check_update() -> tuple[str, str] | None:
    """최신 릴리스를 조회하여 업데이트가 있으면 (version, url)을 반환한다.

    네트워크 실패 또는 최신 버전이면 None.
    """
    try:
        req = urllib.request.Request(_API_URL, headers={"Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None

    tag = data.get("tag_name", "")
    url = data.get("html_url", "")
    if not tag or not url:
        return None

    try:
        if _parse_version(tag) > _parse_version(__version__):
            return (tag.lstrip("v"), url)
    except (ValueError, TypeError):
        return None

    return None
