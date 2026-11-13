"""
JARVIS - Control de calidad técnico del vídeo antes de publicar.
Devuelve lista de problemas (vacía = OK).
"""
import json, re, subprocess


def _run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def revisar_video(path, info=None):
    problemas = []
    info = info or {}
    p = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,width,height",
              "-of", "json", path])
    try:
        meta = json.loads(p.stdout)
    except Exception:
        return ["El vídeo no se puede leer (archivo dañado)"]
    dur = float(meta.get("format", {}).get("duration", 0))
    size = int(meta.get("format", {}).get("size", 0))
    tipos = [s.get("codec_type") for s in meta.get("streams", [])]
    v = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), {})

    if not 15 <= dur <= 59:
        problemas.append(f"Duración fuera de rango para Short: {dur:.1f}s (15-59s)")
    if "audio" not in tipos:
        problemas.append("No tiene audio")
    if (v.get("width"), v.get("height")) != (1080, 1920):
        problemas.append(f"Resolución incorrecta: {v.get('width')}x{v.get('height')}")
    if size < 1_000_000:
        problemas.append(f"Archivo sospechosamente pequeño ({size/1e6:.1f} MB)")
    if info.get("clips", 1) == 0:
        problemas.append("Sin clips de vídeo (solo fondo liso)")
    if info and info.get("palabras", 99) < 60:
        problemas.append(f"Locución demasiado corta ({info.get('palabras')} palabras)")

    # volumen medio de la voz
    vd = _run(["ffmpeg", "-i", path, "-af", "volumedetect", "-vn", "-f", "null", "-"]).stderr
    m = re.search(r"mean_volume: (-?[\d.]+) dB", vd)
    if m and float(m.group(1)) < -35:
        problemas.append(f"Audio casi mudo ({m.group(1)} dB)")

    # pantallas negras
    bd = _run(["ffmpeg", "-i", path, "-vf", "blackdetect=d=0.5:pix_th=0.10", "-an", "-f", "null", "-"]).stderr
    negro = sum(float(x) for x in re.findall(r"black_duration:([\d.]+)", bd))
    if dur and negro / dur > 0.15:
        problemas.append(f"Demasiado tiempo en negro ({negro:.1f}s)")

    # vídeo congelado (pocos cambios de escena en todo el vídeo)
    fr = _run(["ffmpeg", "-i", path, "-vf", "freezedetect=n=0.003:d=4", "-an", "-f", "null", "-"]).stderr
    congelado = sum(float(x) for x in re.findall(r"freeze_duration: ([\d.]+)", fr))
    if dur and congelado / dur > 0.4:
        problemas.append(f"Imagen congelada demasiado tiempo ({congelado:.1f}s)")
    return problemas
