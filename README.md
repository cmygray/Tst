# ttstt

macOS 글로벌 단축키 기반 음성인식 → 텍스트 입력 도구.

어디서든 `Cmd+Shift+L`을 누르면 마이크가 켜지고, 다시 누르면 음성을 인식해서 현재 포커스 위치에 텍스트를 입력한다. Apple Silicon의 [MLX](https://github.com/ml-explore/mlx) 위에서 동작하며, 네트워크 없이 완전히 로컬에서 실행된다.

## 요구사항

- macOS (Apple Silicon)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## 설치

```bash
git clone https://github.com/cmygray/ttstt.git
cd ttstt
uv tool install -e .
```

> 첫 실행 시 ASR 모델(~1.7GB)이 HuggingFace에서 다운로드된다. 이후에는 캐시되어 오프라인 실행 가능.

## 실행

```bash
ttstt
```

어디서든 실행 가능. 메뉴바에 🎤 아이콘이 나타나면 준비 완료.

> 개발 중이라면 `-e` 플래그 덕분에 소스 수정이 즉시 반영된다. 재설치 불필요.

### 접근성 권한

첫 실행 시 macOS가 접근성 권한을 요청한다.

> 시스템 설정 > 개인 정보 보호 및 보안 > 접근성

터미널 앱을 허용 목록에 추가해야 글로벌 단축키가 작동한다.

## 사용법

| 동작 | 설명 |
|------|------|
| `Cmd+Shift+L` | 녹음 시작 (사운드 피드백) |
| `Cmd+Shift+L` | 녹음 종료 → ASR → 현재 포커스에 붙여넣기 |

메뉴바 아이콘을 클릭하면 입력 디바이스를 변경할 수 있다.

## 설정 (선택)

설정 파일 없이도 기본값으로 동작한다. 커스터마이즈가 필요하면:

```bash
mkdir -p ~/.config/ttstt
cp config.example.toml ~/.config/ttstt/config.toml
```

주요 설정 항목:

| 항목 | 기본값 | 설명 |
|------|--------|------|
| ASR 모델 | `Qwen3-ASR-1.7B-8bit` | 경량 모델로 전환 가능 |
| 후처리 LLM | 비활성 | 켜면 ASR 결과를 LLM으로 교정 |
| 단축키 | `Cmd+Shift+L` | modifier + key 조합 변경 가능 |
| 시작/종료 사운드 | Blow / Submarine | macOS 시스템 사운드 이름 |

자세한 설정은 [docs/CONFIGURATION.md](docs/CONFIGURATION.md) 참고.

## 문서

- [아키텍처](docs/ARCHITECTURE.md) — 설계 결정과 모듈 구조
- [설정 가이드](docs/CONFIGURATION.md) — 모든 설정 항목
- [개발 가이드](docs/DEVELOPMENT.md) — 빌드, 배포

## 라이선스

MIT
