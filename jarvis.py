"""
JARVIS - Orquestador 100% GitHub Actions (gratis)
1) Gemini escribe el guion  2) render.py monta el Short  3) se sube a YouTube
Secrets: GEMINI_API_KEY, PEXELS_API_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""
import json, os, pathlib, re, time, requests
import render

TEMAS = pathlib.Path("temas.json")
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
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
    txt, err = None, None
    for intento, model in enumerate([MODEL, "gemini-flash-latest"] * 2):
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                json={"contents": [{"parts": [{"text": prompt}]}],
                      "generationConfig": {"responseMimeType": "application/json", "temperature": 1}},
                timeout=(15, 100))
            r.raise_for_status()
            txt = r.json()["candidates"][0]["content"]["parts"][-1]["text"]
            print("Modelo:", model); break
        except Exception as e:
            err = e; print("Gemini fallo con", model, "->", str(e)[:200]); time.sleep(15 + 15 * intento)
    # Plan B: Gemma (gratis, misma clave, otra capacidad)
    for model in ["gemma-3-27b-it", "gemma-3-12b-it", "gemma-3-27b-it"]:
        if txt is not None:
            break
        try:
            r = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                json={"contents": [{"parts": [{"text": prompt + "\nResponde SOLO con el JSON, sin texto extra."}]}],
                      "generationConfig": {"temperature": 1}},
                timeout=(15, 120))
            r.raise_for_status()
            t = r.json()["candidates"][0]["content"]["parts"][-1]["text"]
            t = t[t.find("{"):t.rfind("}") + 1]
            json.loads(t)
            txt = t; print("Modelo:", model, "(plan B)")
        except Exception as e:
            err = e; print("Plan B fallo con", model, "->", str(e)[:200]); time.sleep(20)
    # Plan C gratis y sin clave: Pollinations (compatible OpenAI)
    for intento in range(4):
        if txt is not None:
            break
        try:
            r = requests.post("https://text.pollinations.ai/openai", timeout=(15, 120), json={
                "model": "openai", "temperature": 1,
                "messages": [{"role": "system", "content": "Responde solo con JSON válido."},
                             {"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}})
            r.raise_for_status()
            txt = r.json()["choices"][0]["message"]["content"]
            json.loads(re.sub(r"```(json)?", "", txt).strip())  # validar
            print("Modelo: pollinations (plan B)")
        except Exception as e:
            txt = None; err = e; print("Plan B fallo ->", str(e)[:200]); time.sleep(20)
    if txt is None:
        raise RuntimeError(f"Ninguna IA respondió: {err}")
    d = json.loads(re.sub(r"```(json)?", "", txt).strip())
    if not all(k in d for k in ("titulo", "guion", "keywords", "descripcion", "hashtags")):
        raise RuntimeError(f"JSON incompleto: {list(d)}")
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


def caption(d):
    return f"{d['titulo']}\n\n{d['descripcion']}\n\n{' '.join(d['hashtags'])}"


def publicar_release(path, d):
    """Deja el vídeo + texto en GitHub Releases (para TikTok a mano y URL pública para Instagram)."""
    repo, tok = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if not (repo and tok):
        return None
    h = {"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"}
    tag = time.strftime("short-%Y%m%d-%H%M")
    r = requests.post(f"https://api.github.com/repos/{repo}/releases", headers=h, timeout=30,
                      json={"tag_name": tag, "name": d["titulo"],
                            "body": "📱 Texto para TikTok / Instagram:\n\n" + caption(d)})
    r.raise_for_status()
    up_url = r.json()["upload_url"].split("{")[0]
    a = requests.post(f"{up_url}?name=short.mp4", headers={**h, "Content-Type": "video/mp4"},
                      data=open(path, "rb"), timeout=300)
    a.raise_for_status()
    url = a.json()["browser_download_url"]
    print("RELEASE ->", r.json()["html_url"])
    # limpiar releases antiguas (dejar las 30 últimas)
    try:
        rels = requests.get(f"https://api.github.com/repos/{repo}/releases?per_page=100", headers=h, timeout=30).json()
        for old in rels[30:]:
            requests.delete(f"https://api.github.com/repos/{repo}/releases/{old['id']}", headers=h, timeout=30)
            requests.delete(f"https://api.github.com/repos/{repo}/git/refs/tags/{old['tag_name']}", headers=h, timeout=30)
    except Exception as e:
        print("limpieza releases:", e)
    return url


def subir_instagram(video_url, d):
    tok, uid = os.getenv("IG_TOKEN"), os.getenv("IG_USER_ID")
    if not (tok and uid and video_url):
        print("Instagram: sin configurar"); return
    g = os.getenv("IG_GRAPH", "https://graph.facebook.com/v27.0")
    c = requests.post(f"{g}/{uid}/media", timeout=60, data={
        "media_type": "REELS", "video_url": video_url, "caption": caption(d),
        "share_to_feed": "true", "access_token": tok})
    c.raise_for_status()
    cid = c.json()["id"]
    for _ in range(40):  # hasta ~10 min
        time.sleep(15)
        st = requests.get(f"{g}/{cid}", params={"fields": "status_code", "access_token": tok}, timeout=30).json()
        if st.get("status_code") == "FINISHED":
            break
        if st.get("status_code") == "ERROR":
            raise RuntimeError(f"Instagram procesado con error: {st}")
    p = requests.post(f"{g}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}, timeout=60)
    p.raise_for_status()
    print("INSTAGRAM -> publicado", p.json().get("id"))


if __name__ == "__main__":
    d = guion()
    print("TEMA:", d["titulo"])
    pathlib.Path("payload.json").write_text(json.dumps(d, ensure_ascii=False), "utf-8")
    render.main("payload.json", "out.mp4")
    if os.getenv("YT_REFRESH_TOKEN"):
        subir_youtube("out.mp4", d)
    else:
        print("Sin credenciales de YouTube: vídeo solo en Artifacts")
    url = None
    try:
        url = publicar_release("out.mp4", d)
    except Exception as e:
        print("Release falló:", str(e)[:300])
    try:
        subir_instagram(url, d)
    except Exception as e:
        print("Instagram falló:", str(e)[:300])
