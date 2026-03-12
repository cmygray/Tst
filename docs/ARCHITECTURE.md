# 아키텍처

ttstt의 설계 결정과 모듈 구조를 설명한다.

## 설계 원칙

1. **완전한 로컬 실행** — 네트워크 없이 Apple Silicon의 MLX 프레임워크 위에서 동작
2. **최소 지연** — 핫키 → 텍스트 입력까지의 체감 지연을 최소화
3. **비침습적** — Dock 아이콘 없이 백그라운드에서 동작, 클립보드를 오염시키지 않음
4. **설정 가능** — 모델, 단축키, 마이크, 후처리 등 모두 커스터마이즈 가능

## 전체 흐름

```
사용자
  │
  ├─ Cmd+Shift+L (hotkey.py: CGEventTap)
  │
  ├─ 녹음 시작 ──→ sounds.py: 시스템 사운드 재생
  │                audio.py: sounddevice InputStream 시작
  │
  ├─ Cmd+Shift+L
  │
  ├─ 녹음 종료 ──→ sounds.py: 시스템 사운드 재생
  │                audio.py: InputStream 종료 + ffmpeg 정규화
  │
  ├─ ASR ────────→ asr.py: mlx-audio Qwen3-ASR 추론
  │
  ├─ 후처리 ─────→ postprocess.py: mlx-lm 경량 LLM 교정 (선택)
  │
  └─ 출력 ───────→ clipboard.py: clipboard swap + Cmd+V 시뮬레이션
```

## 모듈 구조

```
src/ttstt/
├── __init__.py      # 패키지 메타데이터
├── __main__.py      # python -m ttstt 엔트리포인트
├── app.py           # 메인 오케스트레이터 (App 클래스)
├── config.py        # 설정 로드 (~/.config/ttstt/config.toml)
├── hotkey.py        # 글로벌 단축키 (CGEventTap)
├── audio.py         # 마이크 녹음 (sounddevice + ffmpeg)
├── asr.py           # 음성인식 (mlx-audio + Qwen3-ASR)
├── postprocess.py   # 텍스트 교정 (mlx-lm + 경량 LLM)
├── clipboard.py     # 클립보드 swap & 붙여넣기
└── sounds.py        # 시스템 사운드 피드백
```

### app.py — 메인 오케스트레이터

`App` 클래스가 모든 모듈을 조율한다.

- `on_toggle()`: 핫키 콜백. 녹음 중이면 종료하고 파이프라인 실행, 아니면 녹음 시작.
- `_process_pipeline()`: ASR → 후처리 → 클립보드 붙여넣기. **별도 스레드**에서 실행하여 CFRunLoop(이벤트 루프)를 블로킹하지 않는다.
- `_processing` 플래그로 파이프라인 실행 중 중복 호출을 방지한다.

### hotkey.py — 글로벌 단축키

`Quartz.CGEventTapCreate`로 세션 레벨 이벤트 탭을 생성한다.

- **kCGEventKeyDown** 이벤트만 감시
- 콜백에서 modifier + keycode 조합이 일치하면 `on_toggle()` 호출 후 `None` 반환 (이벤트 소비)
- 불일치하면 이벤트를 그대로 통과 (`return event`)
- 탭이 타임아웃으로 비활성화되면 자동으로 재활성화
- `CFRunLoopRun()`으로 메인 스레드의 이벤트 루프 실행

**macOS 접근성 권한**: `CGPreflightListenEventAccess()` → `CGRequestListenEventAccess()`로 권한 확인 및 요청.

### audio.py — 마이크 녹음

`sounddevice.InputStream`의 콜백 기반 녹음을 사용한다.

- 콜백에서 프레임을 리스트에 누적 (논블로킹)
- `stop()` 시 `numpy.concatenate` 후 `normalize_audio()` 호출
- `normalize_audio()`: 파이프를 통해 ffmpeg에 raw PCM을 보내고 정규화된 PCM을 받는다. 임시 파일 없이 처리.
- ffmpeg 파라미터: `-ac 1 -ar 16000 -c:a pcm_s16le`

### asr.py — 음성인식

`mlx_audio.stt.load()`로 모델을 lazy load한다.

- 모델은 전역 변수에 캐시. 같은 모델 ID면 재로드하지 않음.
- `model.generate(audio, max_tokens=..., language=...)` 호출
- `language`가 빈 문자열이면 `None` 전달 (자동 감지). 한국어+영어 혼합 환경에서는 자동 감지를 권장.
- 반환값: `STTOutput.text`

### postprocess.py — 텍스트 교정

`mlx_lm.load()`로 경량 LLM을 lazy load한다.

- `config.postprocess.enabled`가 `False`면 원본 텍스트를 그대로 반환
- chat template을 적용해 system prompt + user message 형태로 프롬프트 구성
- system prompt는 설정 파일에서 커스터마이즈 가능

### clipboard.py — 클립보드 swap

NSPasteboard API로 clipboard swap 패턴을 구현한다.

1. `_backup()`: 현재 클립보드의 모든 아이템 × 모든 타입을 `NSData`로 백업
2. `_set_string()`: ASR 결과 텍스트를 클립보드에 설정
3. `_simulate_cmd_v()`: `CGEventCreateKeyboardEvent` + `CGEventPost`로 Cmd+V 시뮬레이션
4. 0.15초 대기 (대상 앱의 붙여넣기 처리 시간)
5. `_restore()`: 백업한 내용을 클립보드에 복원

### sounds.py — 시스템 사운드

`AppKit.NSSound.soundNamed_()`로 macOS 시스템 사운드를 재생한다.

- `/System/Library/Sounds/` 디렉토리의 사운드 이름을 사용
- 설정 파일에서 사운드 이름을 변경할 수 있음

## 한국어+영어 혼합 최적화

Qwen3-ASR은 한국어를 네이티브로 지원한다. 혼합 환경에서의 전략:

1. **언어 자동 감지 사용** (`language = ""`) — 모델이 세그먼트별로 언어를 자동 감지하여, 한국어 중간에 영어 단어가 나와도 적절히 처리
2. **후처리 LLM** — ASR이 영어를 한국어로 잘못 음차하거나, 한국어를 영어로 잘못 인식한 경우를 교정
3. **ffmpeg 정규화** — 입력 오디오를 일관된 포맷으로 변환하여 인식률 안정화

## 스레딩 모델

```
메인 스레드: CFRunLoopRun() — 이벤트 탭 콜백 처리
    │
    └─ on_toggle()
         │
         ├─ 녹음 시작: sounddevice 콜백 스레드에서 프레임 누적
         │
         └─ 녹음 종료: 워커 스레드 생성 → ASR + 후처리 + 붙여넣기
```

- 메인 스레드: CFRunLoop. 핫키 이벤트를 처리한다. 블로킹하면 안 됨.
- sounddevice 콜백 스레드: 자동 생성. 오디오 프레임을 버퍼에 누적.
- 워커 스레드: `_process_pipeline()`을 실행. ASR과 후처리는 무거운 연산이므로 별도 스레드 필수.

## 배포

PyInstaller로 `.app` 번들을 생성한다.

- `LSUIElement = True`: Dock에 아이콘 없이 백그라운드 실행
- `NSMicrophoneUsageDescription`: 마이크 권한 설명
- `target_arch = arm64`: Apple Silicon 전용
- GitHub Release에 `.app` 번들을 업로드
