#!/usr/bin/env python3
"""Pre-generate Estonian narration for story pages.

Tries TartuNLP neural TTS first (best Estonian quality), falls back to
Google Translate TTS. Output: audio/s<story>p<page>.mp3 (or .wav for TartuNLP).
Re-run after editing story texts in index.html.
"""
import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request

HERE = pathlib.Path(__file__).parent
OUT = HERE / "audio"
OUT.mkdir(exist_ok=True)

# story page texts are parsed straight out of index.html so they can't drift
html = (HERE / "index.html").read_text(encoding="utf-8")
m = re.search(r"const STORIES = \[(.*?)\n\];", html, re.S)
if not m:
    sys.exit("STORIES array not found in index.html")
pages = re.findall(r"\['(?:[^']*)',\s*'((?:[^'\\]|\\.)*)'\]", m.group(1))
stories = []
for block in re.split(r"\{ title:", m.group(1))[1:]:
    texts = re.findall(r"\['[^']*',\s*'((?:[^'\\]|\\.)*)'\],", block)
    stories.append([t.replace("\\'", "'") for t in texts])
print(f"found {len(stories)} stories, {sum(len(s) for s in stories)} pages")


def tartunlp(text: str, path: pathlib.Path) -> bool:
    req = urllib.request.Request(
        "https://api.tartunlp.ai/text-to-speech/v2",
        data=json.dumps({"text": text, "speaker": "mari", "speed": 0.9}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            data = r.read()
        if data[:4] == b"RIFF":
            path.with_suffix(".wav").write_bytes(data)
            return True
    except Exception as e:
        print(f"  tartunlp failed: {e}")
    return False


def gtts(text: str, path: pathlib.Path) -> bool:
    url = (
        "https://translate.google.com/translate_tts?ie=UTF-8&tl=et&client=tw-ob&q="
        + urllib.parse.quote(text)
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        if data[:2] in (b"\xff\xf3", b"\xff\xfb", b"ID"):
            path.with_suffix(".mp3").write_bytes(data)
            return True
    except Exception as e:
        print(f"  gtts failed: {e}")
    return False


use_tartu = "--gtts" not in sys.argv
for si, story in enumerate(stories):
    for pi, text in enumerate(story):
        base = OUT / f"s{si}p{pi}"
        if base.with_suffix(".wav").exists() or base.with_suffix(".mp3").exists():
            print(f"s{si}p{pi}: exists, skip")
            continue
        print(f"s{si}p{pi}: {text[:50]}…")
        ok = use_tartu and tartunlp(text, base)
        if not ok:
            ok = gtts(text, base)
        if not ok:
            sys.exit(f"both backends failed at s{si}p{pi}")
        time.sleep(1.2)  # be polite to free services
print("done:", len(list(OUT.iterdir())), "files in", OUT)
