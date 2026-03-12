# ttstt

macOS 글로벌 단축키 기반 음성인식 → 텍스트 입력 도구.

어디서든 단축키를 누르면 마이크가 켜지고, 다시 누르면 [Qwen3-ASR](https://huggingface.co/mlx-community/Qwen3-ASR-1.7B-8bit)이 음성을 인식해서 현재 포커스 위치에 텍스트를 입력한다. Apple Silicon의 MLX 프레임워크 위에서 동작하며, 네트워크 없이 로컬에서 실행된다.

## 주요 기능

- **글로벌 단축키** (기본 `Cmd+Shift+L`) — 어떤 앱에서든 녹음 토글
- **로컬 ASR** — mlx-audio + Qwen3-ASR, 네트워크 불필요
- **한국어+영어 혼합** 환경 최적화
- **후처리 LLM** (선택) — 경량 LLM으로 오탈자 교정
- **Clipboard swap** — 기존 클립보드를 보존하면서 결과를 붙여넣기
- **시스템 사운드 피드백** — 녹음 시작/종료 시 사운드
- **설정 가능** — 모델, 단축키, 마이크, 후처리 등 모두 커스터마이즈

## 요구사항

- macOS (Apple Silicon)
- Python 3.12+
- ffmpeg (`brew install ffmpeg`)
- 접근성(Accessibility) 권한

## 설치

### GitHub Release (.app 번들)

[Releases](https://github.com/cmygray/ttstt/releases) 페이지에서 최신 `.app`을 다운로드하여 `/Applications`에 넣으세요.

### 소스에서 설치

```bash
git clone https://github.com/cmygray/ttstt.git
cd ttstt
uv sync
```

## 사용법

### 실행

```bash
# 소스에서
uv run ttstt

# 또는 python -m
uv run python -m ttstt
```

### 기본 동작

1. `Cmd+Shift+L` → "띵" 사운드와 함께 녹음 시작
2. `Cmd+Shift+L` → "뚝" 사운드와 함께 녹음 종료
3. ASR이 음성을 텍스트로 변환
4. (설정 시) 후처리 LLM이 텍스트 교정
5. 현재 포커스된 위치에 텍스트 붙여넣기

### 접근성 권한

첫 실행 시 macOS가 접근성 권한을 요청한다:

> 시스템 설정 > 개인 정보 보호 및 보안 > 접근성

터미널(또는 ttstt.app)을 허용 목록에 추가해야 글로벌 단축키가 작동한다.

## 설정

설정 파일 위치: `~/.config/ttstt/config.toml`

초기 설정:

```bash
mkdir -p ~/.config/ttstt
cp config.example.toml ~/.config/ttstt/config.toml
```

자세한 설정 항목은 [설정 가이드](docs/CONFIGURATION.md)를 참고.

## 빌드 (.app 번들)

```bash
uv sync --extra dev
uv run pyinstaller ttstt.spec
# 결과: dist/ttstt.app
```

## 문서

- [아키텍처](docs/ARCHITECTURE.md) — 설계와 모듈 구조
- [설정 가이드](docs/CONFIGURATION.md) — 모든 설정 항목 설명
- [개발 가이드](docs/DEVELOPMENT.md) — 기여, 빌드, 배포

## 라이선스

MIT
