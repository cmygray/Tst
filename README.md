# Tst

Local speech-to-text for macOS. Press a key, speak, release — text appears at your cursor. Runs entirely on-device using [MLX](https://github.com/ml-explore/mlx) on Apple Silicon. No network required.

## Requirements

- macOS (Apple Silicon)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/)

## Install

**From release (recommended):**

Download the latest `.dmg` from [Releases](https://github.com/cmygray/Tst/releases), open it, and drag `tst.app` to Applications.

**From source:**

```bash
git clone https://github.com/cmygray/Tst.git
cd Tst
uv tool install -e .
tst
```

The first run downloads the ASR model (~300MB for the default 0.6B model). After that it works offline.

### Accessibility Permission

macOS will prompt for accessibility access on first launch. Grant it in:

> System Settings > Privacy & Security > Accessibility

## Usage

The default hotkey mode is **tap+hold**: hold `Option+Space` to record, release to transcribe and paste.

| Action | Description |
|--------|-------------|
| Hold `Option+Space` | Start recording |
| Release | Stop recording, transcribe, paste at cursor |
| `Cmd+Shift+\` | Re-paste last transcription |

Click the menu bar icon to change input device or open settings.

## Configuration

Works out of the box with defaults. To customize:

```bash
mkdir -p ~/.config/tst
cp config.example.toml ~/.config/tst/config.toml
```

You can also change hotkey, model, and appearance from the **Settings** menu in the menu bar.

### Hotkey

| Option | Default | Description |
|--------|---------|-------------|
| `mode` | `tap_hold` | `tap_hold` (hold to record) or `toggle` (press to start/stop) |
| `key` | `space` | Trigger key |
| `modifier` | `option` | Modifier key(s), e.g. `cmd+shift` |
| `hold_threshold` | `0.20` | Seconds to distinguish tap from hold (`tap_hold` mode) |
| `repaste_modifier` | `cmd+shift` | Modifier for re-paste |
| `repaste_key` | `\` | Key for re-paste |

### ASR Model

| Option | Default | Description |
|--------|---------|-------------|
| `model` | `Qwen3-ASR-0.6B-8bit` | HuggingFace model ID. Switch to `Qwen3-ASR-1.7B-8bit` for higher accuracy |
| `language` | `""` (auto) | Force language: `"Korean"`, `"English"`, or `""` for auto-detect |
| `system_prompt` | `""` | Hotwords or hints to improve recognition |

### Post-processing LLM

Optionally pass ASR output through an LLM for correction:

```toml
[postprocess]
enabled = true
model = "mlx-community/Qwen3.5-4B-4bit"
```

See [`config.example.toml`](config.example.toml) for all options.

## Meeting Mode

Meeting mode continuously records audio, transcribes in chunks, and writes to a markdown file. Toggle it from the menu bar or via `SIGUSR1` signal:

```bash
kill -USR1 $(cat /tmp/tst.lock)
```

Transcripts are saved to `~/Library/Application Support/tst/meetings/`.

### Claude Code Integration

Tst includes a `/meeting-start` slash command for [Claude Code](https://claude.ai/claude-code) that automates the full meeting workflow: start recording, monitor transcripts, write live notes, and summarize on end.

**Install the skill:**

```bash
mkdir -p ~/.claude/commands && \
curl -fsSL https://raw.githubusercontent.com/cmygray/Tst/main/.claude/commands/meeting-start.md \
  -o ~/.claude/commands/meeting-start.md
```

Re-run the same command to update to the latest version.

Then in any Claude Code session:

```
/meeting-start
```

Optionally install [mdgate](https://github.com/cmygray/mdgate) to view live transcripts and notes on your phone via a public URL.

## Docs

- [Architecture](docs/ARCHITECTURE.md)
- [Configuration](docs/CONFIGURATION.md)
- [Development](docs/DEVELOPMENT.md)

## License

MIT
