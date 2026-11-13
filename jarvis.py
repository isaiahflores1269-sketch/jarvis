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


def _json(txt):
    t = re.sub(r"```(json)?", "", txt).strip()
    return json.loads(t[t.find("{"):t.rfind("}") + 1])


def llm(prompt, modelos=None):
    """Gemini -> Gemma -> Pollinations. Devuelve dict JSON."""
    key, err = os.environ["GEMINI_API_KEY"], None
    base = "https://generativelanguage.googleapis.com/v1beta/models"
    modelos = modelos or [MODEL, "gemini-flash-latest"]
    intentos = [(m, True) for m in modelos * 2] + \
               [(m, False) for m in ["gemma-3-27b-it", "gemma-3-12b-it", "gemma-3-27b-it"]]
    for i, (model, json_mode) in enumerate(intentos):
        try:
            cfg = {"temperature": 1}
            if json_mode:
                cfg["responseMimeType"] = "application/json"
            r = requests.post(f"{base}/{model}:generateContent", headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": prompt + "\nResponde SOLO con el JSON."}]}],
                                    "generationConfig": cfg}, timeout=(15, 120))
            r.raise_for_status()
            d = _json(r.json()["candidates"][0]["content"]["parts"][-1]["text"])
            print("  IA:", model); return d
        except Exception as e:
            err = e; print("  fallo", model, "->", str(e)[:150]); time.sleep(min(15 + 10 * i, 45))
    for _ in range(3):  # plan C sin clave
        try:
            r = requests.post("https://text.pollinations.ai/openai", timeout=(15, 120), json={
                "model": "openai", "messages": [{"role": "user", "content": prompt + "\nResponde SOLO con JSON."}],
                "response_format": {"type": "json_object"}})
            r.raise_for_status()
            d = _json(r.json()["choices"][0]["message"]["content"])
            print("  IA: pollinations"); return d
        except Exception as e:
            err = e; print("  fallo pollinations ->", str(e)[:150]); time.sleep(20)
    raise RuntimeError(f"Ninguna IA respondió: {err}")


CLAVES = ("titulo", "guion", "keywords", "descripcion", "hashtags", "texto_miniatura")


ESCRITOR = ["gemini-flash-latest", "gemini-flash-lite-latest"]
REVISOR = ["gemini-flash-lite-latest", "gemini-flash-latest"]


def guion(evitar_extra=()):
    usados = json.loads(TEMAS.read_text("utf-8")) if TEMAS.exists() else []
    prompt = f"""Eres JARVIS, guionista experto en YouTube Shorts virales en español de España sobre curiosidades y datos sorprendentes (ciencia, animales, historia, cuerpo humano, espacio, tecnología).
Crea UN Short nuevo pensado para retener y ganar suscriptores. Devuelve SOLO un JSON con estas claves:
- titulo: máx 60 caracteres, despierta curiosidad SIN exagerar ni engañar, sin hashtags. Debe coincidir exactamente con lo que dice el guion.
- texto_miniatura: 2-4 palabras MUY potentes para la portada (ej: "NO DEBERÍA EXISTIR"), distinto del título.
- guion: 110-140 palabras para leer en voz alta. La 1ª frase (máx 12 palabras) es el GANCHO: una afirmación concreta y sorprendente (no una pregunta genérica tipo "¿sabías que...?"). Frases cortas. Un giro o dato extra a mitad. Termina con "Suscríbete para más curiosidades."
REGLA DE ORO: usa SOLO datos muy conocidos que aparezcan en cualquier enciclopedia. Nada de cifras discutibles, mitos populares ni exageraciones. Si no estás 100% seguro de un dato, no lo pongas.
- keywords: array de 4 palabras EN INGLÉS para buscar vídeos de stock (concretas, visuales, relacionadas con el tema).
- descripcion: 2 frases.
- hashtags: array de 5, incluye "#shorts" y "#curiosidades".
Temas ya usados (NO repetir): {' | '.join(list(usados[-60:]) + list(evitar_extra)) or 'ninguno'}"""
    d = llm(prompt, ESCRITOR)
    falta = [k for k in CLAVES if k not in d]
    if falta:
        raise RuntimeError(f"JSON incompleto, faltan {falta}")
    return d


def revisar_guion(d):
    """Editor IA: solo puntúa y señala problemas."""
    prompt = f"""Eres el editor jefe de un canal de YouTube Shorts de curiosidades.
Revisa este Short antes de publicarlo:
TÍTULO: {d['titulo']}
TEXTO MINIATURA: {d['texto_miniatura']}
GUION: {d['guion']}

Puntúa del 1 al 10: gancho (¿la 1ª frase engancha en 1 segundo?), retencion (ritmo y giro), titulo_miniatura (¿dan ganas de pulsar?), veracidad (10 = todo es un hecho conocido y correcto).
Lista en datos_dudosos SOLO afirmaciones que sean falsas o claramente exageradas (no marques simplificaciones normales de divulgación).
Devuelve SOLO JSON: gancho, retencion, titulo_miniatura, veracidad, problemas (lista corta), datos_dudosos (lista)."""
    return llm(prompt, REVISOR)


def reescribir(d, rv):
    prompt = f"""Reescribe este Short de YouTube corrigiendo los fallos del editor.
TÍTULO: {d['titulo']}
TEXTO MINIATURA: {d['texto_miniatura']}
GUION: {d['guion']}
PROBLEMAS: {rv.get('problemas')}
DATOS DUDOSOS (ELIMÍNALOS por completo, no los reformules; sustitúyelos por hechos conocidos y seguros del mismo tema): {rv.get('datos_dudosos')}
Reglas: mismo tema; 1ª frase = gancho concreto y sorprendente (máx 12 palabras, no una pregunta genérica); título coherente con el guion y sin exagerar; guion de 110-140 palabras que termina con "Suscríbete para más curiosidades."
Devuelve SOLO JSON con: titulo, texto_miniatura, guion."""
    nv = llm(prompt, ESCRITOR)
    for k in ("titulo", "texto_miniatura", "guion"):
        if nv.get(k):
            d[k] = nv[k]
    return d


def _num(x):
    try:
        return float(x)
    except Exception:
        return 0.0


def preparar_guion():
    """Genera, revisa y corrige. Publica solo si los datos son fiables."""
    descartados, mejor = [], None
    for tema in range(3):
        d = guion(descartados)
        print(f"TEMA {tema+1}:", d["titulo"])
        for ronda in range(3):
            rv = revisar_guion(d)
            notas = {k: _num(rv.get(k)) for k in ("gancho", "retencion", "titulo_miniatura", "veracidad")}
            dudosos = rv.get("datos_dudosos") or []
            print(f"  revisión {ronda+1}: {notas} dudosos={dudosos} problemas={rv.get('problemas')}")
            fiable = notas["veracidad"] >= 8 and not dudosos
            if fiable and min(notas.values()) >= 8:
                d["revision"] = notas
                return d
            if fiable:
                score = sum(notas.values())
                if not mejor or score > mejor[0]:
                    mejor = (score, dict(d, revision=notas))
            if ronda < 2:
                d = reescribir(d, rv)
        descartados.append(d["titulo"])
        if mejor and mejor[0] >= 30:  # bueno y fiable: no gastar más
            break
    if mejor:
        print("  publicando el mejor candidato fiable:", mejor[1]["titulo"], mejor[1]["revision"])
        return mejor[1]
    raise RuntimeError("Ningún guion con datos fiables: no se publica")


def registrar_tema(titulo):
    usados = json.loads(TEMAS.read_text("utf-8")) if TEMAS.exists() else []
    TEMAS.write_text(json.dumps((usados + [titulo])[-150:], ensure_ascii=False, indent=1), "utf-8")


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
    if os.path.exists("thumb.jpg"):
        try:
            t = requests.post(f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={vid}",
                              headers={**h, "Content-Type": "image/jpeg"}, data=open("thumb.jpg", "rb"), timeout=60)
            print("MINIATURA ->", "ok" if t.ok else f"no aplicada ({t.status_code}: {t.text[:120]})")
        except Exception as e:
            print("MINIATURA -> error", e)
    return vid


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
                            "body": "📱 Texto para TikTok / Instagram:\n\n" + caption(d)
                                    + f"\n\n🖼️ Texto portada: {d.get('texto_miniatura','')}"
                                    + f"\n✅ Revisión IA: {d.get('revision','')}"})
    r.raise_for_status()
    up_url = r.json()["upload_url"].split("{")[0]
    a = requests.post(f"{up_url}?name=short.mp4", headers={**h, "Content-Type": "video/mp4"},
                      data=open(path, "rb"), timeout=300)
    a.raise_for_status()
    url = a.json()["browser_download_url"]
    if os.path.exists("thumb.jpg"):
        requests.post(f"{up_url}?name=portada.jpg", headers={**h, "Content-Type": "image/jpeg"},
                      data=open("thumb.jpg", "rb"), timeout=60)
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
    import qa
    d = preparar_guion()
    print("GUION APROBADO:", d["titulo"], "| portada:", d["texto_miniatura"])
    pathlib.Path("payload.json").write_text(json.dumps(d, ensure_ascii=False), "utf-8")
    for intento in range(2):
        info = render.main("payload.json", "out.mp4")
        problemas = qa.revisar_video("out.mp4", info)
        print("CONTROL VÍDEO:", "OK" if not problemas else problemas)
        if not problemas:
            break
        if intento == 0:  # reintento con palabras clave genéricas
            d["keywords"] = d["keywords"][:2] + ["nature", "science"]
            pathlib.Path("payload.json").write_text(json.dumps(d, ensure_ascii=False), "utf-8")
    else:
        raise SystemExit(f"NO SE PUBLICA: el vídeo no pasó el control de calidad -> {problemas}")
    registrar_tema(d["titulo"])
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
