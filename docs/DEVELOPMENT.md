# 개발 가이드

ttstt 개발 환경 설정, 빌드, 배포 방법을 설명한다.

## 요구사항

- macOS (Apple Silicon)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- ffmpeg (`brew install ffmpeg`)
- Xcode Command Line Tools

## 개발 환경 설정

```bash
git clone https://github.com/cmygray/ttstt.git
cd ttstt
uv sync --extra dev
```

## 실행

```bash
# 직접 실행
uv run ttstt

# python -m 실행
uv run python -m ttstt
```

첫 실행 시 ASR 모델이 HuggingFace에서 다운로드된다. 약 1.7GB (8bit 모델).

## 프로젝트 구조

```
ttstt/
├── README.md               # 프로젝트 소개
├── pyproject.toml           # 패키지 설정 및 의존성
├── config.example.toml      # 설정 파일 예시
├── ttstt.spec               # PyInstaller 빌드 스펙
├── src/
│   └── ttstt/
│       ├── __init__.py      # 패키지 메타데이터
│       ├── __main__.py      # python -m 엔트리포인트
│       ├── app.py           # 메인 오케스트레이터
│       ├── config.py        # 설정 관리
│       ├── hotkey.py        # 글로벌 단축키
│       ├── audio.py         # 마이크 녹음
│       ├── asr.py           # 음성인식 엔진
│       ├── postprocess.py   # 텍스트 후처리
│       ├── clipboard.py     # 클립보드 swap
│       └── sounds.py        # 사운드 피드백
└── docs/
    ├── ARCHITECTURE.md      # 아키텍처 문서
    ├── CONFIGURATION.md     # 설정 가이드
    └── DEVELOPMENT.md       # 개발 가이드 (이 문서)
```

## 코드 스타일

- ruff로 린트 (`uv run ruff check src/`)
- 줄 길이 100자
- import 정렬: isort 규칙

## .app 번들 빌드

```bash
uv run pyinstaller ttstt.spec
```

결과물: `dist/ttstt.app`

### 빌드 시 주의사항

- `target_arch = arm64`: Apple Silicon 전용으로 빌드됨
- MLX 관련 패키지(`mlx`, `mlx-audio`, `mlx-lm`)는 Apple Silicon에서만 동작
- `LSUIElement = True`: Dock에 아이콘을 표시하지 않는 백그라운드 앱
- `NSMicrophoneUsageDescription`: macOS 마이크 권한 설명이 Info.plist에 포함됨

## GitHub Release 배포

1. 버전 태그 생성:

```bash
git tag v0.1.0
git push origin v0.1.0
```

2. .app 번들 빌드:

```bash
uv run pyinstaller ttstt.spec
```

3. .app을 zip으로 압축:

```bash
cd dist
zip -r ttstt-v0.1.0-macos-arm64.zip ttstt.app
```

4. GitHub Release 생성:

```bash
gh release create v0.1.0 \
  dist/ttstt-v0.1.0-macos-arm64.zip \
  --title "v0.1.0" \
  --notes "최초 릴리스"
```

## 의존성

| 패키지 | 용도 |
|--------|------|
| `mlx-audio` | Qwen3-ASR 모델 로드 및 추론 |
| `mlx-lm` | 후처리 LLM 모델 로드 및 생성 |
| `sounddevice` | 마이크 녹음 (콜백 기반) |
| `numpy` | 오디오 데이터 처리 |
| `pyobjc-framework-Quartz` | 글로벌 핫키 (CGEventTap), 키 시뮬레이션 |
| `pyobjc-framework-Cocoa` | 클립보드 (NSPasteboard), 사운드 (NSSound) |

## 접근성 권한

개발 중에는 터미널 앱에 접근성 권한을 부여해야 한다:

> 시스템 설정 > 개인 정보 보호 및 보안 > 접근성 > 터미널.app 허용

.app 번들로 배포할 경우, ttstt.app 자체에 권한을 부여해야 한다.

## 트러블슈팅

### "이벤트 탭 생성 실패"

접근성 권한이 없음. 시스템 설정에서 허용 후 재실행.

### "ffmpeg not found"

```bash
brew install ffmpeg
```

### 첫 실행이 느림

ASR 모델 다운로드 중. HuggingFace에서 ~1.7GB를 받는다. 이후에는 캐시됨.

### 마이크가 안 잡힘

```python
import sounddevice as sd
print(sd.query_devices())
```

출력에서 디바이스 이름을 확인하고 `config.toml`의 `[audio] device`에 지정.
