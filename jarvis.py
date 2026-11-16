"""
JARVIS - Orquestador 100% GitHub Actions (gratis)
1) Gemini escribe el guion  2) render.py monta el Short  3) se sube a YouTube
Secrets: GEMINI_API_KEY, PEXELS_API_KEY, YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN
"""
import calendar, json, os, pathlib, re, time, requests
import xml.etree.ElementTree as ET
import render

TEMAS = pathlib.Path("temas.json")
MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
PRIVACY = os.getenv("YT_PRIVACY", "public")


def _json(txt):
    t = re.sub(r"```(json)?", "", txt).strip()
    return json.loads(t[t.find("{"):t.rfind("}") + 1])


_DISPONIBLES = None


def modelos_disponibles():
    """Pregunta a Google qué modelos hay HOY (los nombres cambian)."""
    global _DISPONIBLES
    if _DISPONIBLES is None:
        try:
            r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                             headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]}, timeout=30)
            _DISPONIBLES = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                            if "generateContent" in m.get("supportedGenerationMethods", [])]
        except Exception as e:
            print("  no se pudo listar modelos:", e); _DISPONIBLES = []
    return _DISPONIBLES


def _plan_b():
    """Otros modelos gratis de Google con su propia capacidad (flash, flash-lite, gemma...)."""
    disp = modelos_disponibles()
    malos = ("embedding", "image", "tts", "audio", "live", "vision", "native", "robotics", "computer", "aqa")
    cand = [m for m in disp if not any(x in m for x in malos)]
    pref = lambda m: (0 if "flash" in m and "gemini" in m else 1 if "gemma" in m else 2, -len(m))
    return [m for m in sorted(cand, key=pref) if "pro" not in m][:6]


def llm(prompt, modelos=None):
    """Gemini -> otros modelos de Google -> Pollinations. Devuelve dict JSON."""
    key, err = os.environ["GEMINI_API_KEY"], None
    base = "https://generativelanguage.googleapis.com/v1beta/models"
    modelos = modelos or [MODEL, "gemini-flash-latest"]
    extra = [m for m in _plan_b() if m not in modelos]
    intentos = [(m, True) for m in modelos * 2] + [(m, "gemma" not in m) for m in extra]
    for i, (model, json_mode) in enumerate(intentos):
        try:
            cfg = {"temperature": 1}
            if json_mode:
                cfg["responseMimeType"] = "application/json"
            r = requests.post(f"{base}/{model}:generateContent", headers={"x-goog-api-key": key},
                              json={"contents": [{"parts": [{"text": prompt + "\nResponde SOLO con el JSON."}]}],
                                    "generationConfig": cfg}, timeout=(15, 75))
            r.raise_for_status()
            d = _json(r.json()["candidates"][0]["content"]["parts"][-1]["text"])
            print("  IA:", model); return d
        except Exception as e:
            err = e; print("  fallo", model, "->", str(e)[:150]); time.sleep(min(10 + 5 * i, 30))
    for _ in range(3):  # plan C sin clave
        try:
            r = requests.post("https://text.pollinations.ai/", timeout=(15, 120), json={
                "messages": [{"role": "user", "content": prompt + "\nResponde SOLO con JSON válido."}]})
            r.raise_for_status()
            d = _json(r.text)
            print("  IA: pollinations"); return d
        except Exception as e:
            err = e; print("  fallo pollinations ->", str(e)[:150]); time.sleep(20)
    raise RuntimeError(f"Ninguna IA respondió: {err}")


CLAVES = ("titulo", "guion", "keywords", "descripcion", "hashtags", "texto_miniatura")


CANAL = os.getenv("YT_CHANNEL_ID", "UCsopoWr4pom9WjQlnqGP-RA")
STATS = pathlib.Path("stats.json")


def estudio_canal():
    """Lee las estadísticas públicas del canal (RSS) y ordena los Shorts por rendimiento."""
    try:
        x = requests.get(f"https://www.youtube.com/feeds/videos.xml?channel_id={CANAL}", timeout=30).text
        ns = {"a": "http://www.w3.org/2005/Atom", "m": "http://search.yahoo.com/mrss/"}
        now, vids = time.time(), []
        for e in ET.fromstring(x).findall("a:entry", ns):
            titulo = e.find("a:title", ns).text.replace("#shorts", "").strip()
            pub = calendar.timegm(time.strptime(e.find("a:published", ns).text[:19], "%Y-%m-%dT%H:%M:%S"))
            com = e.find("m:group/m:community", ns)
            vistas = int(com.find("m:statistics", ns).get("views", 0))
            likes = int(com.find("m:starRating", ns).get("count", 0))
            horas = (now - pub) / 3600
            if horas < 6:
                continue  # demasiado reciente para juzgarlo
            vids.append({"titulo": titulo, "vistas": vistas, "likes": likes, "horas": round(horas),
                         "vph": round(vistas / min(horas, 72), 1),  # vistas/hora en sus primeras 72 h
                         "like_ratio": round(likes / vistas * 100, 1) if vistas else 0})
        vids.sort(key=lambda v: v["vph"], reverse=True)
        STATS.write_text(json.dumps(vids, ensure_ascii=False, indent=1), "utf-8")
        print("ESTUDIO CANAL:", [(v["titulo"][:35], v["vistas"], v["vph"]) for v in vids])
        return vids
    except Exception as e:
        print("Estudio del canal falló:", str(e)[:200])
        return []


def contexto_audiencia(vids):
    if len(vids) < 3:
        return ""
    fmt = lambda v: f'"{v["titulo"]}" ({v["vistas"]} vistas, {v["vph"]} vistas/h, {v["like_ratio"]}% likes)'
    k = min(3, len(vids) // 2)
    top, low = vids[:k], vids[-k:]
    return f"""
DATOS REALES DE NUESTRO CANAL (úsalos para decidir el tema y el estilo):
- Los que MÁS funcionaron: {'; '.join(fmt(v) for v in top)}
- Los que MENOS funcionaron: {'; '.join(fmt(v) for v in low)}
Analiza qué tienen en común los ganadores (categoría de tema, tipo de gancho, emoción: miedo, asombro, asco, misterio...) y crea un Short de ese estilo ganador, SIN repetir ninguno de esos temas. Evita el estilo de los que menos funcionaron."""


ESCRITOR = ["gemini-flash-lite-latest", "gemini-flash-latest"]
REVISOR = ["gemini-flash-lite-latest", "gemini-flash-latest"]


def guion(evitar_extra=(), audiencia=""):
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
- pregunta: una pregunta corta y divertida para el primer comentario que invite a la gente a opinar (ej: "¿Tú lo sabías? 👀").
Temas ya usados (NO repetir): {' | '.join(list(usados[-60:]) + list(evitar_extra)) or 'ninguno'}{audiencia}"""
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


_VACIAS = set("el la los las un una unos unas de del al a en y o que tu tus te se su sus es son por para con sin lo le les mas más muy como cada nunca siempre este esta esto ese esa tiene tienen puede pueden hay ser ver tú qué cómo".split())


def _palabras(t):
    t = re.sub(r"[^a-záéíóúñü ]", " ", t.lower())
    return {w for w in t.split() if len(w) > 3 and w not in _VACIAS}


def es_repetido(titulo, extra=()):
    usados = json.loads(TEMAS.read_text("utf-8")) if TEMAS.exists() else []
    if STATS.exists():
        usados += [v["titulo"] for v in json.loads(STATS.read_text("utf-8"))]
    nuevo = _palabras(titulo)
    for u in list(usados) + list(extra):
        if len(nuevo & _palabras(u)) >= 2:
            return u
    return None


def mismo_tema(titulo):
    """La IA comprueba si es el mismo tema con otras palabras."""
    usados = json.loads(TEMAS.read_text("utf-8")) if TEMAS.exists() else []
    if not usados:
        return None
    try:
        r = llm(f"""¿El Short "{titulo}" trata el MISMO dato o tema que alguno de estos ya publicados?
Cuenta como repetido si el dato central es el mismo aunque cambien las palabras (ej: "la fuerza de las hormigas" y "el insecto que levanta 50 veces su peso").
Publicados: {json.dumps(usados[-80:], ensure_ascii=False)}
Devuelve SOLO JSON: {{"repetido": true/false, "cual": "título publicado o vacío"}}""", REVISOR)
        return r.get("cual") or "repetido" if r.get("repetido") else None
    except Exception as e:
        print("  comprobación de tema falló:", e); return None


def preparar_guion():
    """Genera, revisa y corrige. Publica solo si los datos son fiables."""
    descartados, mejor = [], None
    audiencia = contexto_audiencia(estudio_canal())
    for tema in range(4):
        d = guion(descartados, audiencia)
        print(f"TEMA {tema+1}:", d["titulo"])
        rep = es_repetido(d["titulo"]) or mismo_tema(d["titulo"])
        if rep:
            print("  descartado: tema repetido ->", rep)
            descartados.append(d["titulo"]); continue
        for ronda in range(3):
            rv = revisar_guion(d)
            notas = {k: _num(rv.get(k)) for k in ("gancho", "retencion", "titulo_miniatura", "veracidad")}
            dudosos = rv.get("datos_dudosos") or []
            print(f"  revisión {ronda+1}: {notas} dudosos={dudosos} problemas={rv.get('problemas')}")
            n_pal = len(d["guion"].split())
            if not 95 <= n_pal <= 165:
                dudosos = list(dudosos)
                rv["problemas"] = list(rv.get("problemas") or []) + [
                    f"El guion tiene {n_pal} palabras: DEBE tener entre 110 y 140 palabras exactas"]
                notas["retencion"] = min(notas["retencion"], 5)
            fiable = notas["veracidad"] >= 8 and not dudosos and 95 <= n_pal <= 165
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


def yt_headers():
    tok = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": os.environ["YT_CLIENT_ID"], "client_secret": os.environ["YT_CLIENT_SECRET"],
        "refresh_token": os.environ["YT_REFRESH_TOKEN"], "grant_type": "refresh_token"}, timeout=30)
    tok.raise_for_status()
    return {"Authorization": f"Bearer {tok.json()['access_token']}"}


YT = "https://www.googleapis.com/youtube/v3"
RESPONDIDOS = pathlib.Path("respondidos.json")
MAX_RESPUESTAS = int(os.getenv("MAX_RESPUESTAS", "4"))  # cuota diaria de YouTube limitada


def primer_comentario(vid, d):
    """Publica un comentario del canal con una pregunta para animar a comentar."""
    texto = d.get("pregunta") or "¿Lo sabías? Te leo en los comentarios 👇"
    texto += "\n\nSuscríbete para una curiosidad nueva cada día 🔔"
    r = requests.post(f"{YT}/commentThreads?part=snippet", headers=yt_headers(), timeout=30,
                      json={"snippet": {"videoId": vid, "topLevelComment": {"snippet": {"textOriginal": texto}}}})
    print("PRIMER COMENTARIO ->", "ok" if r.ok else f"no ({r.status_code}: {r.text[:150]})")


def responder_comentarios():
    """Responde con IA a comentarios nuevos de los espectadores (sin spam, máx. MAX_RESPUESTAS)."""
    h = yt_headers()
    r = requests.get(f"{YT}/commentThreads", headers=h, timeout=30, params={
        "part": "snippet", "allThreadsRelatedToChannelId": CANAL, "order": "time",
        "maxResults": 50, "moderationStatus": "published", "textFormat": "plainText"})
    if not r.ok:
        print("COMENTARIOS -> no se pudieron leer", r.status_code, r.text[:150]); return
    hechos = set(json.loads(RESPONDIDOS.read_text("utf-8"))) if RESPONDIDOS.exists() else set()
    pend = []
    for t in r.json().get("items", []):
        sn = t["snippet"]; c = sn["topLevelComment"]["snippet"]
        autor = c.get("authorChannelId", {}).get("value")
        if t["id"] in hechos or autor == CANAL or sn.get("totalReplyCount", 0) > 0:
            continue
        pend.append({"id": t["id"], "texto": c.get("textDisplay", "")[:300]})
    pend = pend[:MAX_RESPUESTAS * 2]
    if not pend:
        print("COMENTARIOS -> nada nuevo"); return
    prompt = f"""Eres el community manager del canal de YouTube "Sabías Que Curiosidades" (curiosidades en español de España).
Para cada comentario escribe una respuesta breve (máx. 20 palabras), cercana, natural y variada, con algún emoji ocasional. Si hacen una pregunta, respóndela con un dato correcto. Anima a seguir viendo el canal sin sonar a robot ni repetir siempre lo mismo.
Si el comentario es spam, insultos, enlaces, contenido sexual o sin sentido, la respuesta debe ser "" (no responder).
Comentarios: {json.dumps(pend, ensure_ascii=False)}
Devuelve SOLO JSON: {{"respuestas": [{{"id": "...", "respuesta": "..."}}]}}"""
    try:
        res = llm(prompt, REVISOR).get("respuestas", [])
    except Exception as e:
        print("COMENTARIOS -> IA no disponible", e); return
    n = 0
    for it in res:
        if n >= MAX_RESPUESTAS:
            break
        txt = (it.get("respuesta") or "").strip()
        hechos.add(it.get("id"))
        if not txt or it.get("id") not in {p["id"] for p in pend}:
            continue
        q = requests.post(f"{YT}/comments?part=snippet", headers=h, timeout=30,
                          json={"snippet": {"parentId": it["id"], "textOriginal": txt}})
        print("  respuesta ->", "ok" if q.ok else f"fallo {q.status_code}", "|", txt)
        n += q.ok
    RESPONDIDOS.write_text(json.dumps(sorted(x for x in hechos if x)[-2000:]), "utf-8")
    print(f"COMENTARIOS -> {n} respuestas publicadas")


def subir_youtube(path, d):
    h = yt_headers()
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
    try:
        d = preparar_guion()
    except RuntimeError as e:
        if "Ninguna IA" not in str(e):
            raise
        print("Las IA están saturadas: espero 4 minutos y reintento...")
        time.sleep(240)
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
        vid = subir_youtube("out.mp4", d)
        for paso in (lambda: primer_comentario(vid, d), responder_comentarios):
            try:
                paso()
            except Exception as e:
                print("Comentarios falló (¿falta permiso youtube.force-ssl?):", str(e)[:200])
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
