# Unemaa 🌙

A bedtime app for small kids (built for a 4-year-old), fully in Estonian.
One self-contained `index.html` — no build step, no framework, no server-side code.

## Features

- **Öised helid** — calming sounds synthesized live with the Web Audio API
  (no audio files): rain, ocean, wind, and a music-box Brahms lullaby.
  Volume slider and a sleep timer (15/30/45 min) that fades out over the last minute.
- **Unejutud** — seven bedtime stories (12–13 pages each) with big calm text that
  dims page by page. Three originals plus softened retellings of Punamütsike,
  Kolm põrsakest, Lumivalgeke, and Tuhkatriinu. Optional narration (🔊 Loe ette)
  plays pre-generated neural TTS audio at 0.8× speed with pitch preserved, with
  a narrator picker (👩 Külli / 👨 Peeter) remembered per device.
- **Unesammud** — an 8-step bedtime routine checklist with flying-star rewards
  and a moon meter; state is per-day in localStorage, full moon celebration at
  100%, reset button to start the steps over.

## Running it

Any static file server works:

```bash
python3 -m http.server 8742
# then open http://<machine-ip>:8742 on the phone/tablet (same Wi-Fi)
```

On the device, add it to the home screen for a fullscreen app feel:
- **Android Chrome**: menu → *Add to Home screen*
- **iPad/iPhone Safari**: share button → *Add to Home Screen*

Notes:
- Sounds and narration start only after a tap (browser autoplay policy) — by design,
  tap a sound card once.
- Fonts (Fredoka, Quicksand) load from Google Fonts; everything else is offline.

## Story narration (audio/)

Each story page has a pre-generated MP3 per narrator:
`audio/<voice>/s<story>p<page>.mp3`, where `<voice>` is `kylli` or `peeter`
(story and page are 0-based indexes into the `STORIES` array in `index.html`;
the voice list lives in `VOICES` in `batch_synth.py` and the `.vchip` buttons
in `index.html` — keep them in sync).
The reader plays the file at 0.8× with `preservesPitch`; if a file is missing it
falls back to the device's Estonian system voice via the Web Speech API
(on iPad that voice may need downloading: Settings → Accessibility → Spoken
Content → Voices → Eesti).

After adding or editing stories in `index.html`, regenerate the missing clips
with one of the two generators below.

### Option A (best quality): local TartuNLP neural TTS — `batch_synth.py`

Runs [TartuNLP's](https://koodivaramu.eesti.ee/tartunlp/text-to-speech-worker)
Estonian TTS (the same models as [neurokone.ee](https://www.neurokone.ee))
locally on CPU. ~3 GB disk, no GPU needed, no external API.

One-time setup, in a sibling folder:

```bash
cd ..
git clone https://github.com/TartuNLP/text-to-speech-worker.git tartunlp-worker
cd tartunlp-worker
git submodule update --init --depth 1          # pulls TransformerTTS

# Python 3.11 venv (TF 2.15 / torch 2.1 do not support 3.12) — uv fetches the toolchain
uv venv --python 3.11 .venv
. .venv/bin/activate
uv pip install torch==2.1.2 torchaudio==2.1.2 --index-url https://download.pytorch.org/whl/cpu
uv pip install "librosa==0.11.0" "tensorflow==2.15.1" "ruamel.yaml==0.17.40" \
  "nltk==3.9.2" pydantic pydantic-settings python-dotenv "speechbrain==1.0.2" \
  "huggingface-hub==0.29.2" lameenc \
  "git+https://github.com/TartuNLP/tts_preprocess_et.git@v1.1.0"

# the multispeaker model (210 MB, 10 Estonian voices)
curl -sL -o /tmp/multispeaker.zip \
  https://github.com/TartuNLP/text-to-speech-worker/releases/download/v3.1.0/multispeaker.zip
unzip /tmp/multispeaker.zip -d models/

python -c 'import nltk; nltk.download("punkt"); nltk.download("punkt_tab")'
```

Version pins that matter (learned the hard way):

| Pin | Why |
| --- | --- |
| Python 3.11 | tensorflow 2.15 / torch 2.1.2 have no 3.12 wheels |
| `tensorflow==2.15.1` | the repo's pinned 2.13 caps `typing-extensions<4.6`, which conflicts with pydantic v2 |
| `ruamel.yaml==0.17.40` | 0.18+ removed loader internals that speechbrain's hyperpyyaml still uses (`'Loader' object has no attribute 'max_depth'`) |
| torch from the `/whl/cpu` index | default wheel drags in ~2 GB of CUDA |

Then generate (first run also downloads the HiFiGAN vocoder from HuggingFace):

```bash
cd ../tartunlp-worker && . .venv/bin/activate
python ../laps-magama/batch_synth.py                   # missing clips, both app voices
python ../laps-magama/batch_synth.py --force           # redo everything
python ../laps-magama/batch_synth.py --speaker kylli   # one voice only; the model also
                                                       # has albert, indrek, kalev, liivika,
                                                       # mari, meelis, tambet, vesta
```

`batch_synth.py` parses the `STORIES` array straight out of `index.html` (so texts
can't drift), drives the worker's `Synthesizer` class directly (no RabbitMQ),
and encodes 64 kbps mono MP3s. It also works around a worker bug where the WAV
buffer is read without rewinding, which would return empty audio.
`audio/.local-*` marker files track which clips are locally-generated neural TTS;
that's what `--force` overrides.

### Option B (no setup): `generate-audio.py`

```bash
python3 generate-audio.py         # TartuNLP public API first, Google TTS fallback
python3 generate-audio.py --gtts  # skip straight to Google TTS
```

Uses only the Python standard library. Tries the free public TartuNLP API
(`api.tartunlp.ai`) and falls back to Google Translate TTS. Lower quality than
option A and the TartuNLP API is sometimes down (returns 408 on every request),
but it needs zero installation. Skips files that already exist — delete `audio/`
(or individual files) to regenerate.

## Editing stories / steps / sounds

Everything lives in `index.html`:

- `STORIES` — array of `{ title, sub, cover, pages: [[emoji, text], …] }`.
  Add a story or page, then regenerate audio (see above).
- `TASKS` — the routine checklist `[emoji, label]` pairs.
- `Snd` — the sound engine; each sound is a small Web Audio graph
  (`startRain`, `startOcean`, `startWind`, `startLullaby`).

## Deployment

Static hosting of the repo root is all that's needed — GitHub Pages serves
`index.html` and `audio/` as-is.
