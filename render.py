"""
JARVIS - Motor de render de Shorts (gratis)
Entrada: payload.json  {titulo, guion, keywords[], descripcion, hashtags[], callback}
Salida : out.mp4 (1080x1920) con voz (Edge-TTS), clips de Pexels y subtitulos quemados.
"""
import asyncio, json, os, random, subprocess, sys, pathlib, requests
import edge_tts

W, H = 1080, 1920
VOICE = os.getenv("JARVIS_VOICE", "es-ES-AlvaroNeural")
RATE = os.getenv("JARVIS_RATE", "+8%")
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
TMP = pathlib.Path("tmp"); TMP.mkdir(exist_ok=True)


def sh(cmd):
    print(">", " ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return float(out.strip())


# ---------- 1. VOZ + tiempos de cada palabra ----------
async def tts(text, mp3):
    try:
        com = edge_tts.Communicate(text, VOICE, rate=RATE, boundary="WordBoundary")
    except TypeError:  # versiones antiguas
        com = edge_tts.Communicate(text, VOICE, rate=RATE)
    words = []
    with open(mp3, "wb") as f:
        async for ch in com.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                s = ch["offset"] / 1e7
                words.append((s, s + ch["duration"] / 1e7, ch["text"]))
    return words


# ---------- 2. SUBTITULOS estilo Shorts (2-3 palabras, grandes) ----------
def ts(t):
    h, m = int(t // 3600), int(t % 3600 // 60)
    return f"{h}:{m:02d}:{t % 60:05.2f}"


def make_ass(words, path, total):
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,DejaVu Sans,92,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: Hot,DejaVu Sans,92,&H0000E5FF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines, i = [], 0
    while i < len(words):
        chunk = words[i:i + 3]
        start = chunk[0][0]
        end = words[i + 3][0] if i + 3 < len(words) else min(chunk[-1][1] + 0.4, total)
        txt = " ".join(w[2] for w in chunk).upper()
        style = "Hot" if (i // 3) % 2 else "Main"
        lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},{style},,0,0,0,,{{\\fad(60,0)}}{txt}")
        i += 3
    pathlib.Path(path).write_text(head + "\n".join(lines), encoding="utf-8")


# ---------- 3. CLIPS de Pexels (verticales) ----------
def pexels_clips(keywords, need):
    if not PEXELS_KEY:
        return []
    got, seen = [], set()
    for kw in keywords + ["nature", "space", "science"]:
        try:
            r = requests.get("https://api.pexels.com/videos/search",
                             headers={"Authorization": PEXELS_KEY},
                             params={"query": kw, "orientation": "portrait", "per_page": 8}, timeout=30)
            vids = r.json().get("videos", [])
        except Exception as e:
            print("pexels error", e); continue
        random.shuffle(vids)
        for v in vids[:2]:
            files = [f for f in v["video_files"] if f.get("height") and f["height"] >= 1280 and f["height"] <= 2560]
            if not files or v["id"] in seen:
                continue
            f = min(files, key=lambda x: x["height"])
            p = TMP / f"clip{len(got)}.mp4"
            p.write_bytes(requests.get(f["link"], timeout=120).content)
            seen.add(v["id"]); got.append(p)
            if len(got) >= need:
                return got
    return got


def build_background(clips, total, out):
    if not clips:  # sin Pexels: fondo degradado animado
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i",
            f"gradients=s={W}x{H}:c0=0x0f2027:c1=0x2c5364:speed=0.02:d={total}", "-t", str(total),
            "-r", "30", "-pix_fmt", "yuv420p", str(out)])
        return
    seg = total / len(clips)
    parts = []
    for i, c in enumerate(clips):
        p = TMP / f"seg{i}.mp4"
        sh(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(c), "-t", f"{seg:.3f}", "-an",
            "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps=30,setsar=1",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22", "-pix_fmt", "yuv420p", str(p)])
        parts.append(p)
    lst = TMP / "list.txt"
    lst.write_text("".join(f"file '{p.resolve()}'\n" for p in parts))
    sh(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(lst), "-c", "copy", str(out)])


# ---------- MAIN ----------
def main(payload_path="payload.json", out="out.mp4"):
    d = json.loads(pathlib.Path(payload_path).read_text(encoding="utf-8"))
    text = d["guion"].strip()
    mp3, ass, bg = TMP / "voz.mp3", TMP / "subs.ass", TMP / "bg.mp4"

    words = asyncio.run(asyncio.wait_for(tts(text, mp3), 120))
    total = dur(mp3) + 0.6
    make_ass(words, ass, total)

    n = max(3, min(8, int(total // 6)))
    build_background(pexels_clips(d.get("keywords", []), n), total, bg)

    sh(["ffmpeg", "-y", "-i", str(bg), "-i", str(mp3),
        "-vf", f"eq=brightness=-0.06,ass={ass}", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    print(f"OK -> {out}  ({total:.1f}s, {os.path.getsize(out)/1e6:.1f} MB)")


if __name__ == "__main__":
    main(*sys.argv[1:])
