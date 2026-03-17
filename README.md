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

## 회의 모드 + mdgate 연동 / Meeting Mode + mdgate

회의 모드(`ttstt-meeting`)는 연속 녹음 → 청크 단위 전사 → 마크다운 파일 출력을 수행한다. [mdgate](https://github.com/cmygray/mdgate)와 함께 쓰면 전사 파일과 라이브 노트를 모바일에서 실시간으로 볼 수 있다.

Meeting mode (`ttstt-meeting`) continuously records audio, transcribes in chunks, and writes to a markdown file. Pair it with [mdgate](https://github.com/cmygray/mdgate) to view transcripts and live notes on your phone in real time.

### 1. mdgate 설치 / Install mdgate

```bash
git clone https://github.com/cmygray/mdgate.git
cd mdgate && npm install && npm link
```

### 2. Claude Code 슬래시 커맨드 / Claude Code Slash Command

ttstt 프로젝트에는 회의 모드를 자동 실행하는 `/meeting-start` 커맨드가 포함되어 있다 (`.claude/commands/meeting-start.md`). mdgate가 설치되어 있으면 `--share` 옵션으로 zrok 공개 URL을 자동 생성한다.

This project includes a `/meeting-start` command (`.claude/commands/meeting-start.md`) that orchestrates the entire meeting flow. If mdgate is installed, it automatically creates a public zrok URL via `--share`.

```
/meeting-start
```

커맨드가 하는 일 / What it does:
1. 회의 주제·컨텍스트 확인 / Confirm meeting topic and context
2. `ttstt-meeting` 백그라운드 실행 / Run `ttstt-meeting` in background
3. mdgate로 전사 파일 + 라이브 노트 서빙 (`--share`) / Serve transcript + live notes via mdgate (`--share`)
4. 30초 간격 모니터링 → 라이브 노트 갱신 / Monitor every 30s, update live notes
5. 회의 종료 시 요약 작성 + mdgate 정리 / Write summary on end, clean up mdgate

> mdgate 없이도 회의 모드는 정상 동작한다. 전사 파일은 `~/ttstt-meetings/`에 저장된다.
>
> Meeting mode works without mdgate. Transcripts are saved to `~/ttstt-meetings/`.

## 문서

- [아키텍처](docs/ARCHITECTURE.md) — 설계 결정과 모듈 구조
- [설정 가이드](docs/CONFIGURATION.md) — 모든 설정 항목
- [개발 가이드](docs/DEVELOPMENT.md) — 빌드, 배포

## 라이선스

MIT
