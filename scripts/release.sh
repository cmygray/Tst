#!/bin/bash
# scripts/release.sh — 빌드 + DMG 생성 + GitHub Release
set -euo pipefail

VERSION="${1:?Usage: ./scripts/release.sh v0.2.0}"
ARTIFACT="dist/ttstt-${VERSION}-macos-arm64.dmg"

echo "=== 클린 빌드 ==="
rm -rf build dist
uv run python -m PyInstaller --noconfirm ttstt.spec

echo "=== DMG 생성 ==="
hdiutil create -volname "ttstt" \
  -srcfolder dist/ttstt.app \
  -ov -format UDZO \
  "$ARTIFACT"

echo "=== 태그 & 릴리스 ==="
git tag -d "$VERSION" 2>/dev/null || true
git push origin ":refs/tags/${VERSION}" 2>/dev/null || true
git tag "$VERSION"
git push origin main --tags

gh release create "$VERSION" "$ARTIFACT" \
  --title "$VERSION" \
  --generate-notes

echo "=== 완료: ${VERSION} ==="
