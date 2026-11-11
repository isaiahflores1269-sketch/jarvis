"""
JARVIS - Orquestador 100% GitHub Actions (gratis)
1) Gemini escribe el guion  2) render.py monta el Short  3) se sube a YouTube
Secrets: GEMINI_API_KEY, PEXELS_API_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""
import json, os, pathlib, re, requests
import render

TEMAS = pathlib.Path("temas.json")
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
PRIVACY = os.getenv("YT_PRIVACY", "public")


def guion():
    usados = json.loads(TEMAS.read_text("utf-8")) if TEMAS.exists() else []
    prompt = f"""Eres JARVIS, guionista de un canal de YouTube Shorts en español de España sobre curiosidades y datos sorprendentes (ciencia, animales, historia, cuerpo humano, espacio, tecnología).
Crea UN Short nuevo. Devuelve SOLO un JSON con estas claves:
- titulo: máx 70 caracteres, con gancho, sin hashtags.
- guion: 110-140 palabras para leer en voz alta. Primera frase = gancho brutal. Frases cortas. Solo datos verídicos y comprobables. Termina con "Sígueme para más curiosidades."
- keywords: array de 4 palabras EN INGLÉS para buscar vídeos de stock en Pexels (concretas y visuales).
- descripcion: 2 frases.
- hashtags: array de 5, incluye "#shorts" y "#curiosidades".
Temas ya usados (NO repetir): {' | '.join(usados[-60:]) or 'ninguno'}"""
    r = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent",
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseMimeType": "application/json", "temperature": 1}},
        timeout=90)
    r.raise_for_status()
    txt = r.json()["candidates"][0]["content"]["parts"][0]["text"]
    d = json.loads(re.sub(r"```(json)?", "", txt).strip())
    TEMAS.write_text(json.dumps((usados + [d["titulo"]])[-150:], ensure_ascii=False, indent=1), "utf-8")
    return d


def subir_youtube(path, d):
    tok = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    tok.raise_for_status()
    h = {"Authorization": f"Bearer {tok.json()['access_token']}"}
    meta = {"snippet": {"title": (d["titulo"] + " #shorts")[:100],
                        "description": f"{d['descripcion']}\n\n{' '.join(d['hashtags'])}",
                        "tags": [t.lstrip('#') for t in d["hashtags"]],
                        "categoryId": "27", "defaultLanguage": "es"},
            "status": {"privacyStatus": PRIVACY, "selfDeclaredMadeForKids": False}}
    init = requests.post("https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
                         headers={**h, "Content-Type": "application/json", "X-Upload-Content-Type": "video/mp4"},
                         json=meta, timeout=60)
    init.raise_for_status()
    up = requests.put(init.headers["Location"], headers={**h, "Content-Type": "video/mp4"},
                      data=open(path, "rb"), timeout=600)
    up.raise_for_status()
    vid = up.json()["id"]
    print(f"SUBIDO -> https://youtube.com/shorts/{vid}  ({up.json()['status']['privacyStatus']})")


if __name__ == "__main__":
    d = guion()
    print("TEMA:", d["titulo"])
    pathlib.Path("payload.json").write_text(json.dumps(d, ensure_ascii=False), "utf-8")
    render.main("payload.json", "out.mp4")
    if os.getenv("YT_REFRESH_TOKEN"):
        subir_youtube("out.mp4", d)
    else:
        print("Sin credenciales de YouTube: vídeo solo en Artifacts")
