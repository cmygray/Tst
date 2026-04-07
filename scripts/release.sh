#!/bin/bash
# scripts/release.sh — 빌드 + 사이닝 + 공증 + DMG + GitHub Release
set -euo pipefail

VERSION="${1:?Usage: ./scripts/release.sh v0.7.0}"
APP="dist/tst.app"
ARTIFACT="dist/tst-${VERSION}-macos-arm64.dmg"
IDENTITY="Developer ID Application"
ENTITLEMENTS="tst.entitlements"
NOTARIZE_PROFILE="tst-notarize"

echo "=== 클린 빌드 ==="
rm -rf build dist
uv run python -m PyInstaller --noconfirm tst.spec

echo "=== 코드 사이닝 (deep sign) ==="
find "$APP" -type f \( -name "*.so" -o -name "*.dylib" \) \
  -exec codesign --force --options runtime \
    --entitlements "$ENTITLEMENTS" \
    --sign "$IDENTITY" --timestamp {} \;

codesign --force --options runtime \
  --entitlements "$ENTITLEMENTS" \
  --sign "$IDENTITY" --timestamp \
  "$APP/Contents/MacOS/tst"

codesign --force --options runtime \
  --entitlements "$ENTITLEMENTS" \
  --sign "$IDENTITY" --timestamp \
  "$APP"

echo "=== 서명 검증 ==="
codesign --verify --deep --strict "$APP"
spctl --assess --type execute --verbose=2 "$APP"

echo "=== DMG 생성 ==="
hdiutil create -volname "tst" \
  -srcfolder "$APP" \
  -ov -format UDZO \
  "$ARTIFACT"

codesign --force --sign "$IDENTITY" --timestamp "$ARTIFACT"

echo "=== 공증 (Notarization) ==="
xcrun notarytool submit "$ARTIFACT" \
  --keychain-profile "$NOTARIZE_PROFILE" \
  --wait

echo "=== Staple ==="
xcrun stapler staple "$ARTIFACT"

echo "=== 태그 & 릴리스 ==="
git tag -d "$VERSION" 2>/dev/null || true
git push origin ":refs/tags/${VERSION}" 2>/dev/null || true
git tag "$VERSION"
git push origin main --tags

gh release create "$VERSION" "$ARTIFACT" \
  --title "$VERSION" \
  --generate-notes

echo "=== 완료: ${VERSION} ==="
