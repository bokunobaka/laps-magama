#!/usr/bin/env python3
"""Generate the Unesammud completion praise clip with the local TartuNLP model.

Run from the TTS worker directory (see README) with its venv active:
    cd ../tartunlp-worker && . .venv/bin/activate && python ../laps-magama/synth_congrats.py [--speaker kylli] [--force]
Writes audio/<voice>/congrats.mp3 for each app voice (kylli and peeter);
--speaker limits the run to one voice. Same synthesizer/encoder path as
batch_synth.py, just a single fixed line instead of the story texts.
"""
import io
import os
import pathlib
import sys
import types

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
sys.path.insert(0, os.getcwd())  # import tts_worker/TransformerTTS from the worker checkout

APP = pathlib.Path(__file__).resolve().parent
OUT = APP / "audio"
OUT.mkdir(exist_ok=True)
VOICES = ["kylli", "peeter"]  # must match the .vchip options in index.html
if "--speaker" in sys.argv:
    VOICES = [sys.argv[sys.argv.index("--speaker") + 1]]
FORCE = "--force" in sys.argv

# the line played at 100% on the Unesammud screen (keep in sync with praise() in index.html)
CONGRATS = "Tubli töö! Kõik unesammud on tehtud. Head ööd!"
print(f"congrats clip, voices={VOICES}: {CONGRATS!r}")

import numpy as np
import lameenc
from scipy.io import wavfile

from tts_worker.config import read_model_config
from tts_worker.schemas import Request
import tts_worker.synthesizer as syn


# synthesizer.py reads the BytesIO buffer without rewinding -> b'' unless patched
class _RewindingBytesIO(io.BytesIO):
    def read(self, *args):
        self.seek(0)
        return super().read(*args)


syn.io = types.SimpleNamespace(BytesIO=_RewindingBytesIO)

cfg = read_model_config("config/config.yaml", "multispeaker")
for v in VOICES:
    if v not in cfg.speakers:
        sys.exit(f"unknown speaker {v}; options: {list(cfg.speakers)}")
synth = syn.Synthesizer(cfg, max_input_length=400)


def to_mp3(wav_bytes: bytes, path: pathlib.Path):
    sr, data = wavfile.read(io.BytesIO(wav_bytes))
    pcm = (np.clip(data, -1.0, 1.0) * 32767).astype("<i2")
    enc = lameenc.Encoder()
    enc.set_bit_rate(64)
    enc.set_in_sample_rate(sr)
    enc.set_channels(1)
    enc.set_quality(2)
    path.write_bytes(enc.encode(pcm.tobytes()) + enc.flush())


for voice in VOICES:
    vdir = OUT / voice
    vdir.mkdir(exist_ok=True)
    out = vdir / "congrats.mp3"
    marker = vdir / ".local-congrats.mp3"  # tracks neural-TTS clips, like batch_synth.py
    if marker.exists() and out.exists() and not FORCE:
        print(f"{voice}/congrats.mp3: exists, skip")
        continue
    resp = synth.process_request(Request(text=CONGRATS, speaker=voice, speed=1.0))
    if resp.status_code != 200 or not resp.content or not resp.content.audio:
        sys.exit(f"{voice}/congrats.mp3: synthesis failed (status {resp.status_code})")
    to_mp3(resp.content.audio, out)
    marker.touch()
    print(f"{voice}/congrats.mp3 {out.stat().st_size // 1024}KB :: {CONGRATS}")

print("done")
