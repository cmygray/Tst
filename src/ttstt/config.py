"""설정 관리 모듈.

~/.config/ttstt/config.toml 파일을 읽어 설정을 로드한다.
파일이 없으면 기본값을 사용한다.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "ttstt"
CONFIG_PATH = CONFIG_DIR / "config.toml"

DEFAULT_POSTPROCESS_PROMPT = """음성인식 결과를 교정해주세요.
- 오탈자와 잘못 인식된 단어를 수정
- 문장 부호 정리
- 원문의 의미와 어투를 최대한 유지
- 한국어와 영어가 혼합된 텍스트에 주의
- 교정된 텍스트만 출력 (설명 없이)"""


@dataclass
class ASRConfig:
    model: str = "mlx-community/Qwen3-ASR-1.7B-8bit"
    max_tokens: int = 8192
    language: str = ""
    system_prompt: str = ""
    repetition_penalty: float = 0.0


@dataclass
class PostprocessConfig:
    enabled: bool = False
    model: str = "mlx-community/Qwen3-1.7B-4bit"
    max_tokens: int = 4096
    system_prompt: str = DEFAULT_POSTPROCESS_PROMPT


@dataclass
class HotkeyConfig:
    mode: str = "tap_hold"
    modifier: str = "cmd+shift"
    key: str = "space"
    hold_threshold: float = 0.20
    repaste_modifier: str = "cmd+shift"
    repaste_key: str = ";"


@dataclass
class AudioConfig:
    device: str = ""
    sample_rate: int = 16000
    channels: int = 1


@dataclass
class SoundConfig:
    start: str = "Blow"
    stop: str = "Submarine"


MEETING_OUTPUT_DIR = Path.home() / ".local" / "share" / "ttstt" / "meetings"


@dataclass
class MeetingASRConfig:
    model: str = "mlx-community/Qwen3-ASR-1.7B-8bit"
    max_tokens: int = 32768
    language: str = ""
    system_prompt: str = ""
    repetition_penalty: float = 0.0


@dataclass
class MeetingConfig:
    chunk_duration: int = 60
    output_dir: str = ""
    asr: MeetingASRConfig = field(default_factory=MeetingASRConfig)

    @property
    def resolved_output_dir(self) -> Path:
        if self.output_dir:
            return Path(self.output_dir).expanduser()
        return MEETING_OUTPUT_DIR


@dataclass
class Config:
    asr: ASRConfig = field(default_factory=ASRConfig)
    postprocess: PostprocessConfig = field(default_factory=PostprocessConfig)
    hotkey: HotkeyConfig = field(default_factory=HotkeyConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    sound: SoundConfig = field(default_factory=SoundConfig)
    meeting: MeetingConfig = field(default_factory=MeetingConfig)


def load_config(path: Path | None = None) -> Config:
    """설정 파일을 로드한다. 파일이 없으면 기본값을 반환한다."""
    path = path or CONFIG_PATH
    config = Config()

    if not path.exists():
        return config

    with open(path, "rb") as f:
        data = tomllib.load(f)

    for section in ("asr", "postprocess", "hotkey", "audio", "sound"):
        if section in data:
            sub = getattr(config, section)
            for k, v in data[section].items():
                if hasattr(sub, k):
                    setattr(sub, k, v)

    if "meeting" in data:
        meeting_data = data["meeting"]
        for k, v in meeting_data.items():
            if k == "asr" and isinstance(v, dict):
                for ak, av in v.items():
                    if hasattr(config.meeting.asr, ak):
                        setattr(config.meeting.asr, ak, av)
            elif hasattr(config.meeting, k):
                setattr(config.meeting, k, v)

    return config


def save_hotkey_config(hotkey: HotkeyConfig, path: Path | None = None) -> None:
    """[hotkey] 섹션만 config.toml에 저장한다. 다른 섹션은 보존."""
    path = path or CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    hotkey_toml = (
        "[hotkey]\n"
        f'mode = "{hotkey.mode}"\n'
        f'key = "{hotkey.key}"\n'
        f'modifier = "{hotkey.modifier}"\n'
        f"hold_threshold = {hotkey.hold_threshold}\n"
        f'repaste_modifier = "{hotkey.repaste_modifier}"\n'
        f'repaste_key = "{hotkey.repaste_key}"\n'
    )

    if not path.exists():
        path.write_text(hotkey_toml)
        return

    text = path.read_text()
    # [hotkey] 섹션을 찾아 교체 (다음 [섹션] 또는 EOF까지)
    pattern = r"\[hotkey\]\n(?:(?!\n\[).)*"
    if re.search(pattern, text, re.DOTALL):
        text = re.sub(pattern, hotkey_toml.rstrip(), text, flags=re.DOTALL)
    else:
        text = text.rstrip() + "\n\n" + hotkey_toml

    path.write_text(text)
