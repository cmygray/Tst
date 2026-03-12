# 설정 가이드

ttstt의 모든 설정 항목을 설명한다.

## 설정 파일 위치

```
~/.config/ttstt/config.toml
```

파일이 없으면 모든 항목에 기본값이 사용된다.

## 초기 설정

```bash
mkdir -p ~/.config/ttstt
cp config.example.toml ~/.config/ttstt/config.toml
```

## 설정 항목

### [asr] — 음성인식

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `model` | string | `"mlx-community/Qwen3-ASR-1.7B-8bit"` | HuggingFace 모델 ID. 성능이 부족하면 `Qwen3-ASR-0.6B-8bit`이나 4bit 모델 사용. |
| `max_tokens` | int | `8192` | 최대 생성 토큰 수. 긴 녹음(2시간+)에는 `128000` 권장. |
| `language` | string | `""` (빈 문자열) | 인식 언어. `"Korean"`, `"English"` 등 지정 가능. 빈 문자열이면 자동 감지. 한국어+영어 혼합은 빈 문자열 권장. |

**사용 가능한 ASR 모델:**

| 모델 | 크기 | 용도 |
|------|------|------|
| `mlx-community/Qwen3-ASR-1.7B-8bit` | ~1.7B 8bit | 기본. 정확도 우선. |
| `mlx-community/Qwen3-ASR-1.7B-4bit` | ~1.7B 4bit | 메모리 절약. |
| `mlx-community/Qwen3-ASR-0.6B-8bit` | ~0.6B 8bit | 속도 우선. |

### [postprocess] — 후처리 LLM

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `enabled` | bool | `false` | 후처리 활성화 여부. |
| `model` | string | `"mlx-community/Qwen3.5-4B-4bit"` | 후처리 LLM 모델 ID. |
| `max_tokens` | int | `4096` | 후처리 최대 토큰 수. |
| `system_prompt` | string | (내장 프롬프트) | 후처리에 사용할 시스템 프롬프트. 커스터마이즈 가능. |

**후처리 LLM 모델 예시:**

| 모델 | 크기 | 용도 |
|------|------|------|
| `mlx-community/Qwen3.5-4B-4bit` | ~4B 4bit | 기본. 균형. |
| `mlx-community/Qwen3.5-1.7B-4bit` | ~1.7B 4bit | 경량. 속도 우선. |

**기본 시스템 프롬프트:**

```
음성인식 결과를 교정해주세요.
- 오탈자와 잘못 인식된 단어를 수정
- 문장 부호 정리
- 원문의 의미와 어투를 최대한 유지
- 한국어와 영어가 혼합된 텍스트에 주의
- 교정된 텍스트만 출력 (설명 없이)
```

### [hotkey] — 글로벌 단축키

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `modifier` | string | `"cmd+shift"` | modifier 조합. `+`로 구분. |
| `key` | string | `"l"` | 알파벳 소문자 한 글자. |

**사용 가능한 modifier:**

- `cmd` — Command (⌘)
- `shift` — Shift (⇧)
- `option` 또는 `alt` — Option (⌥)
- `ctrl` — Control (⌃)

**예시:**

```toml
[hotkey]
modifier = "cmd+option"
key = "r"
```

### [audio] — 오디오 입력

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `device` | string | `""` (빈 문자열) | 마이크 디바이스 이름. 빈 문자열이면 시스템 기본 인풋. |
| `sample_rate` | int | `16000` | 샘플링 레이트 (Hz). 변경 비권장. |
| `channels` | int | `1` | 채널 수. 변경 비권장. |

**마이크 디바이스 확인:**

```python
import sounddevice as sd
print(sd.query_devices())
```

디바이스 이름 또는 인덱스를 `device` 항목에 지정할 수 있다.

### [sound] — 사운드 피드백

| 항목 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `start` | string | `"Tink"` | 녹음 시작 시 재생할 시스템 사운드 이름. |
| `stop` | string | `"Pop"` | 녹음 종료 시 재생할 시스템 사운드 이름. |

**사용 가능한 시스템 사운드:**

Basso, Blow, Bottle, Frog, Funk, Glass, Hero, Morse, Ping, Pop, Purr, Sosumi, Submarine, Tink

사운드 파일 위치: `/System/Library/Sounds/`

## 설정 예시: 경량 모드

메모리가 제한적인 환경:

```toml
[asr]
model = "mlx-community/Qwen3-ASR-0.6B-8bit"
max_tokens = 4096

[postprocess]
enabled = false
```

## 설정 예시: 최대 정확도 모드

메모리가 넉넉하고 정확도가 최우선:

```toml
[asr]
model = "mlx-community/Qwen3-ASR-1.7B-8bit"
max_tokens = 128000

[postprocess]
enabled = true
model = "mlx-community/Qwen3.5-4B-4bit"
```
