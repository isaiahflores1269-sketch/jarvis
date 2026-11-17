"""
JARVIS - Motor de render de Shorts (gratis)
Entrada: payload.json  {titulo, guion, keywords[], descripcion, hashtags[], callback}
Salida : out.mp4 (1080x1920) con voz (Edge-TTS), clips de Pexels y subtitulos quemados.
"""
import asyncio, json, os, random, re, subprocess, sys, pathlib, requests
import edge_tts

W, H = 1080, 1920
VOICE = os.getenv("JARVIS_VOICE", "es-ES-AlvaroNeural")
RATE = os.getenv("JARVIS_RATE", "+10%")
PEXELS_KEY = os.getenv("PEXELS_API_KEY", "")
TMP = pathlib.Path("tmp"); TMP.mkdir(exist_ok=True)
CLIPS_USADOS = pathlib.Path("clips_usados.json")


def _usados():
    try:
        return set(json.loads(CLIPS_USADOS.read_text("utf-8")))
    except Exception:
        return set()


def _guardar_usados(nuevos):
    todos = list(_usados() | set(nuevos))
    CLIPS_USADOS.write_text(json.dumps(todos[-600:]), "utf-8")


def sh(cmd):
    print(">", " ".join(cmd[:6]), "...")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def dur(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout
    return float(out.strip())


# ---------- 1. VOZ + tiempos de cada palabra ----------
async def tts(text, mp3, voice=None):
    voice = voice or VOICE
    try:
        com = edge_tts.Communicate(text, voice, rate=RATE, boundary="WordBoundary")
    except TypeError:  # versiones antiguas
        com = edge_tts.Communicate(text, voice, rate=RATE)
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


FONT = os.getenv("JARVIS_FONT", "Montserrat Black")


def _limpia(t):
    return t.replace("{", "").replace("}", "").replace("\\", "")


def _hook_lineas(hook, maxc=14):
    """Parte el texto de portada en 1-2 líneas equilibradas."""
    w = _limpia(hook).upper().split()
    if len(" ".join(w)) <= maxc or len(w) < 2:
        return " ".join(w)
    mejor = min(range(1, len(w)), key=lambda i: abs(len(" ".join(w[:i])) - len(" ".join(w[i:]))))
    return " ".join(w[:mejor]) + "\\N" + " ".join(w[mejor:])


def make_ass(words, path, total, hook=""):
    """Subtítulos estilo Shorts: 2-3 palabras, la que suena en amarillo y un poco más grande, con 'pop'."""
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Main,{FONT},104,&H00FFFFFF,&H000000FF,&H00000000,&H78000000,0,0,0,0,100,100,1,0,1,8,4,2,70,70,560,1
Style: Hook,{FONT},138,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,1,0,1,9,5,8,60,60,300,1
Style: HookBox,{FONT},138,&H00000000,&H000000FF,&H0000E5FF,&H0000E5FF,0,0,0,0,100,100,1,0,3,22,0,8,60,60,300,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    AMA, BLA = "&H0000E5FF&", "&H00FFFFFF&"
    # agrupar: máx 3 palabras o 16 letras, y cortar en signos de puntuación
    grupos, g = [], []
    for w in words:
        g.append(w)
        if len(g) == 3 or len(" ".join(x[2] for x in g)) > 16 or re.search(r"[.,;:?!]$", w[2]):
            grupos.append(g); g = []
    if g:
        grupos.append(g)
    lines = []
    for gi, g in enumerate(grupos):
        fin_grupo = grupos[gi + 1][0][0] if gi + 1 < len(grupos) else min(g[-1][1] + 0.5, total)
        for wi, w in enumerate(g):
            ini = w[0]
            fin = g[wi + 1][0] if wi + 1 < len(g) else fin_grupo
            if fin <= ini:
                continue
            partes = []
            for j, x in enumerate(g):
                t = _limpia(x[2]).upper()
                if j == wi:
                    partes.append(f"{{\\c{AMA}\\fscx112\\fscy112}}{t}{{\\c{BLA}\\fscx100\\fscy100}}")
                else:
                    partes.append(t)
            pop = "{\\fscx80\\fscy80\\t(0,90,\\fscx100\\fscy100)}" if wi == 0 else ""
            lines.append(f"Dialogue: 0,{ts(ini)},{ts(fin)},Main,,0,0,0,,{pop}{' '.join(partes)}")
    if hook:  # portada: caja amarilla con texto negro arriba durante los primeros 2,2 s (sale en la miniatura)
        h = _hook_lineas(hook)
        lines.insert(0, f"Dialogue: 2,{ts(0)},{ts(2.2)},HookBox,,0,0,0,,{{\\fad(0,200)}}{h}")
    pathlib.Path(path).write_text(head + "\n".join(lines), encoding="utf-8")


# ---------- 3. CLIPS de stock (Pixabay o Pexels) ----------
def pixabay_clips(keywords, need):
    key = os.getenv("PIXABAY_API_KEY", "")
    if not key:
        return []
    got, seen, usados = [], set(), _usados()
    for kw in keywords + ["nature", "space", "science"]:
        hits = []
        for page in (1, 2):
            try:
                r = requests.get("https://pixabay.com/api/videos/", timeout=30, params={
                    "key": key, "q": kw, "per_page": 20, "page": page, "safesearch": "true"})
                hits += r.json().get("hits", [])
            except Exception as e:
                print("pixabay error", e); break
        frescos = [h for h in hits if f"px{h['id']}" not in usados and h["id"] not in seen]
        random.shuffle(frescos)
        # preferir verticales, pero manteniendo el azar
        frescos.sort(key=lambda h: h["videos"]["medium"].get("width", 1) > h["videos"]["medium"].get("height", 1))
        for h in frescos[:2]:
            v = h["videos"].get("large") or {}
            if not v.get("url"):
                v = h["videos"]["medium"]
            try:
                p = TMP / f"clip{len(got)}.mp4"
                p.write_bytes(requests.get(v["url"], timeout=120).content)
            except Exception as e:
                print("descarga error", e); continue
            seen.add(h["id"]); got.append(p)
            if len(got) >= need:
                break
        if len(got) >= need:
            break
    _guardar_usados(f"px{i}" for i in seen)
    print("clips nuevos:", sorted(seen))
    return got


def pexels_clips(keywords, need):
    if not PEXELS_KEY:
        return pixabay_clips(keywords, need)
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
    build_background.cortes = [0.0]
    if not clips:  # sin Pexels: fondo degradado animado
        sh(["ffmpeg", "-y", "-f", "lavfi", "-i",
            f"gradients=s={W}x{H}:c0=0x0f2027:c1=0x2c5364:speed=0.02:d={total}", "-t", str(total),
            "-r", "30", "-pix_fmt", "yuv420p", str(out)])
        return
    seg = total / len(clips)
    build_background.cortes = [round(seg * i, 2) for i in range(len(clips))]
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


# ---------- 4. MÚSICA de fondo + efectos (generados, sin derechos de autor) ----------
MUSICA_DIR = pathlib.Path("musica")
ACORDES = [  # progresiones suaves (Hz): Am-F-C-G, Dm-Bb-F-C, Em-C-G-D
    [(220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66)],
    [(146.83, 174.61, 220.0), (116.54, 146.83, 174.61), (174.61, 220.0, 261.63), (130.81, 164.81, 196.0)],
    [(164.81, 196.0, 246.94), (130.81, 164.81, 196.0), (196.0, 246.94, 293.66), (146.83, 185.0, 220.0)],
]


def make_music(total, out):
    """Si hay mp3/m4a en la carpeta musica/ usa uno al azar; si no, genera un 'pad' ambiental con pulso suave."""
    propios = [p for p in MUSICA_DIR.glob("*") if p.suffix.lower() in (".mp3", ".m4a", ".wav", ".ogg")] if MUSICA_DIR.exists() else []
    if propios:
        src = random.choice(propios)
        sh(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(src), "-t", f"{total:.2f}",
            "-af", f"afade=t=in:d=0.5,afade=t=out:st={max(total-1.2,0):.2f}:d=1.2,loudnorm=I=-20:TP=-3", "-ar", "44100", "-ac", "2", str(out)])
        return
    prog = random.choice(ACORDES)
    paso = 2.4  # segundos por acorde
    terms = []
    for k, acorde in enumerate(prog):
        cond = f"between(mod(t,{paso*len(prog)}),{k*paso},{(k+1)*paso})"
        notas = "+".join(f"sin(2*PI*{f}*t)+0.35*sin(2*PI*{f*2}*t)" for f in acorde)
        terms.append(f"{cond}*({notas})")
    pad = "0.05*(" + "+".join(terms) + ")"
    bajo = "+".join(f"between(mod(t,{paso*len(prog)}),{k*paso},{(k+1)*paso})*sin(2*PI*{a[0]/2}*t)" for k, a in enumerate(prog))
    pulso = f"0.06*({bajo})*(0.5+0.5*cos(2*PI*t*2))"  # pulso a 120 bpm
    sh(["ffmpeg", "-y", "-f", "lavfi", "-i", f"aevalsrc='{pad}+{pulso}':s=44100:d={total:.2f}",
        "-af", "lowpass=f=1800,aecho=0.8:0.6:120|240:0.25|0.15,"
               f"afade=t=in:d=0.8,afade=t=out:st={max(total-1.5,0):.2f}:d=1.5,loudnorm=I=-20:TP=-3",
        "-ar", "44100",
        "-ac", "2", str(out)])


def make_sfx(cortes, total, out):
    """'Whoosh' al empezar y en cada cambio de clip."""
    if not cortes:
        cortes = [0.0]
    partes, mezcla = [], []
    for i, t in enumerate(cortes):
        d = int(max(t - 0.15, 0) * 1000)
        partes.append(f"[0:a]atrim=0:0.45,asetpts=PTS-STARTPTS,highpass=f=400,lowpass=f=5000,"
                      f"afade=t=in:d=0.15,afade=t=out:st=0.15:d=0.3,volume=0.35,adelay={d}|{d}[w{i}]")
        mezcla.append(f"[w{i}]")
    filt = ";".join(partes) + ";" + "".join(mezcla) + f"amix=inputs={len(mezcla)}:normalize=0,apad=whole_dur={total:.2f}[s]"
    sh(["ffmpeg", "-y", "-f", "lavfi", "-i", "anoisesrc=c=pink:d=1:a=0.6", "-filter_complex", filt,
        "-map", "[s]", "-t", f"{total:.2f}", "-ac", "2", "-ar", "44100", str(out)])


# ---------- MAIN ----------
def main(payload_path="payload.json", out="out.mp4"):
    d = json.loads(pathlib.Path(payload_path).read_text(encoding="utf-8"))
    text = d["guion"].strip()
    mp3, ass, bg = TMP / "voz.mp3", TMP / "subs.ass", TMP / "bg.mp4"

    words = asyncio.run(asyncio.wait_for(tts(text, mp3, d.get("voz")), 120))
    total = dur(mp3) + 0.6
    make_ass(words, ass, total, d.get("texto_miniatura", ""))

    n = max(3, min(8, int(total // 6)))
    clips = pexels_clips(d.get("keywords", []), n)
    build_background(clips, total, bg)

    music, sfx = TMP / "musica.wav", TMP / "sfx.wav"
    make_music(total, music)
    make_sfx(build_background.cortes, total, sfx)
    vol_m = os.getenv("JARVIS_MUSIC_VOL", "0.16")
    # la música baja sola cuando habla la voz (ducking)
    mix = (f"[1:a]aresample=44100,aformat=channel_layouts=stereo,volume=1.15,asplit=2[voz][key];"
           f"[2:a]volume={vol_m}[mus];[mus][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=350[musd];"
           f"[3:a]volume=1[fx];[voz][musd][fx]amix=inputs=3:normalize=0,alimiter=limit=0.95[a]")
    sh(["ffmpeg", "-y", "-i", str(bg), "-i", str(mp3), "-i", str(music), "-i", str(sfx),
        "-filter_complex", f"[0:v]eq=brightness=-0.06:saturation=1.12,ass={ass}[v];{mix}",
        "-map", "[v]", "-map", "[a]", "-t", f"{total:.2f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out])
    # miniatura: fotograma a 0,8 s (lleva el texto gancho)
    sh(["ffmpeg", "-y", "-ss", "0.5", "-i", out, "-frames:v", "1", "-vf", "scale=720:1280", "-q:v", "3", "thumb.jpg"])
    print(f"OK -> {out}  ({total:.1f}s, {os.path.getsize(out)/1e6:.1f} MB, {len(clips)} clips)")
    return {"duracion": total, "clips": len(clips), "palabras": len(words)}


if __name__ == "__main__":
    main(*sys.argv[1:])
