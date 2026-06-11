#!/usr/bin/env python3
"""Batch-generate Estonian narration for Unemaa using the local TartuNLP model.

Run from the TTS worker directory (see README) with its venv active:
    cd ../tartunlp-worker && . .venv/bin/activate && python ../laps-magama/batch_synth.py [--speaker mari] [--force]
Parses story texts out of the app's index.html and writes audio/s<story>p<page>.mp3.
"""
import io
import os
import pathlib
import re
import sys
import types

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")

# the script lives in the app repo but imports tts_worker/TransformerTTS from
# the worker checkout it is run from — python adds the script dir, not the cwd
sys.path.insert(0, os.getcwd())

APP = pathlib.Path(__file__).resolve().parent
OUT = APP / "audio"
OUT.mkdir(exist_ok=True)
SPEAKER = sys.argv[sys.argv.index("--speaker") + 1] if "--speaker" in sys.argv else "mari"
FORCE = "--force" in sys.argv

html = (APP / "index.html").read_text(encoding="utf-8")
m = re.search(r"const STORIES = \[(.*?)\n\];", html, re.S)
if not m:
    sys.exit("STORIES array not found in index.html")
stories = []
for block in re.split(r"\{ title:", m.group(1))[1:]:
    texts = re.findall(r"\['[^']*',\s*'((?:[^'\\]|\\.)*)'\],", block)
    stories.append([t.replace("\\'", "'") for t in texts])
print(f"{len(stories)} stories, {sum(map(len, stories))} pages, speaker={SPEAKER}")

import numpy as np
import lameenc
from scipy.io import wavfile

from tts_worker.config import read_model_config
from tts_worker.schemas import Request
import tts_worker.synthesizer as syn


# synthesizer.py builds the response with BytesIO.read() right after writing,
# which returns b'' unless the buffer is rewound first — patch module-locally
class _RewindingBytesIO(io.BytesIO):
    def read(self, *args):
        self.seek(0)
        return super().read(*args)


syn.io = types.SimpleNamespace(BytesIO=_RewindingBytesIO)

cfg = read_model_config("config/config.yaml", "multispeaker")
if SPEAKER not in cfg.speakers:
    sys.exit(f"unknown speaker {SPEAKER}; options: {list(cfg.speakers)}")
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


for si, story in enumerate(stories):
    for pi, text in enumerate(story):
        out = OUT / f"s{si}p{pi}.mp3"
        marker = OUT / f".local-{out.name}"  # tracks which files are neural TTS
        if marker.exists() and out.exists() and not FORCE:
            print(f"{out.name}: exists, skip")
            continue
        resp = synth.process_request(Request(text=text, speaker=SPEAKER, speed=1.0))
        if resp.status_code != 200 or not resp.content or not resp.content.audio:
            sys.exit(f"{out.name}: synthesis failed (status {resp.status_code})")
        to_mp3(resp.content.audio, out)
        marker.touch()
        print(f"{out.name} {out.stat().st_size // 1024}KB :: {text[:48]}")

print("done")
