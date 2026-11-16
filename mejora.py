"""
JARVIS - Mejora continua (se ejecuta 1 vez por semana)
1) Analiza qué variantes (categoría, tipo de gancho, voz) consiguen más vistas/hora
2) Ajusta los pesos para que Jarvis haga más de lo que funciona (sin dejar de experimentar)
3) La IA saca lecciones de los mejores/peores títulos y de los comentarios del público
4) Publica un informe en GitHub (Issues) que te llega como notificación
"""
import json, os, statistics, time, requests
import jarvis
from jarvis import _leer, ESTRATEGIA, HISTORIAL, COMENTARIOS, VARIANTES, REVISOR

MIN_HORAS = 48     # un vídeo necesita al menos 48 h para juzgarlo
MIN_MUESTRAS = 2   # mínimo de vídeos por opción para fiarse


def analizar():
    jarvis.estudio_canal()  # refresca vistas del historial
    hist = [h for h in _leer(HISTORIAL, []) if h.get("vph") is not None and h.get("horas", 0) >= MIN_HORAS]
    if len(hist) < 6:
        print(f"Aún pocos datos ({len(hist)} vídeos maduros). Se mantiene la estrategia.")
        return hist, {}, {}
    media = statistics.mean(h["vph"] for h in hist) or 1
    pesos, tabla = {}, {}
    for dim, opciones in VARIANTES.items():
        pesos[dim], tabla[dim] = {}, {}
        for o in opciones:
            vals = [h["vph"] for h in hist if h.get("variante", {}).get(dim) == o]
            if len(vals) >= MIN_MUESTRAS:
                m = statistics.mean(vals)
                pesos[dim][o] = round(min(max(m / media, 0.3), 3.0), 2)  # 0,3x … 3x
                tabla[dim][o] = (round(m, 1), len(vals))
            else:
                pesos[dim][o] = 1.0  # sin datos: peso neutro para que se pruebe
                tabla[dim][o] = (None, len(vals))
    return hist, pesos, tabla


def lecciones(hist):
    if len(hist) < 6:
        return [], []
    orden = sorted(hist, key=lambda h: h["vph"], reverse=True)
    fmt = lambda h: f'{h["titulo"]} | {h["vph"]} vistas/h | {h.get("variante", {})}'
    com = [c["texto"] for c in _leer(COMENTARIOS, [])][-120:]
    prompt = f"""Eres el estratega de crecimiento de un canal de YouTube Shorts de curiosidades en español.
MEJORES vídeos (vistas/hora en sus primeras 72 h):
{chr(10).join(fmt(h) for h in orden[:10])}
PEORES vídeos:
{chr(10).join(fmt(h) for h in orden[-10:])}
COMENTARIOS RECIENTES DEL PÚBLICO:
{json.dumps(com, ensure_ascii=False)}

Devuelve SOLO JSON con:
- lecciones: 5-8 reglas concretas y accionables para los próximos guiones (sobre temas, ganchos, títulos, texto de portada), basadas en estos datos.
- ideas: 10 ideas de temas nuevos con potencial (incluye las que pida el público en los comentarios), sin repetir los ya publicados.
- resumen: 3 frases explicando qué está funcionando y qué no."""
    r = jarvis.llm(prompt, REVISOR)
    return r.get("lecciones", []), r.get("ideas", []), r.get("resumen", "")


def fallos_semana():
    repo, tok = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if not (repo and tok):
        return None
    desde = time.strftime("%Y-%m-%d", time.gmtime(time.time() - 7 * 86400))
    r = requests.get(f"https://api.github.com/repos/{repo}/actions/workflows/jarvis.yml/runs",
                     headers={"Authorization": f"Bearer {tok}"}, params={"created": f">={desde}", "per_page": 100},
                     timeout=30).json().get("workflow_runs", [])
    return sum(x["conclusion"] == "success" for x in r), sum(x["conclusion"] == "failure" for x in r)


def informe(hist, tabla, lec, ideas, resumen, runs):
    md = ["# 📊 Informe semanal de Jarvis", ""]
    if runs:
        md.append(f"**Publicaciones esta semana:** ✅ {runs[0]} correctas · ❌ {runs[1]} fallidas\n")
    if hist:
        top = sorted(hist, key=lambda h: h["vph"], reverse=True)
        md.append("## 🏆 Top 5")
        md += [f"{i+1}. {h['titulo']} — {h.get('vistas', 0)} vistas ({h['vph']}/h)" for i, h in enumerate(top[:5])]
        md.append("\n## 🐢 Los 3 que peor funcionaron")
        md += [f"- {h['titulo']} — {h.get('vistas', 0)} vistas ({h['vph']}/h)" for h in top[-3:]]
    if resumen:
        md += ["\n## 🧠 Qué está pasando", str(resumen)]
    for dim, ops in tabla.items():
        md.append(f"\n## 🔬 Experimento: {dim}")
        for o, (m, n) in sorted(ops.items(), key=lambda x: -(x[1][0] or 0)):
            md.append(f"- {o}: {'%s vistas/h' % m if m is not None else 'sin datos aún'} ({n} vídeos)")
    if lec:
        md += ["\n## 📌 Lecciones que Jarvis aplicará esta semana"] + [f"- {l}" for l in lec]
    if ideas:
        md += ["\n## 💡 Ideas en cola"] + [f"- {i}" for i in ideas]
    return "\n".join(md)


def publicar_informe(texto):
    repo, tok = os.getenv("GITHUB_REPOSITORY"), os.getenv("GITHUB_TOKEN")
    if not (repo and tok):
        print(texto); return
    r = requests.post(f"https://api.github.com/repos/{repo}/issues", timeout=30,
                      headers={"Authorization": f"Bearer {tok}", "Accept": "application/vnd.github+json"},
                      json={"title": time.strftime("Informe semanal Jarvis %d/%m/%Y"), "body": texto})
    print("INFORME ->", r.json().get("html_url", r.text[:200]))


if __name__ == "__main__":
    hist, pesos, tabla = analizar()
    lec, ideas, resumen = [], [], ""
    try:
        lec, ideas, resumen = lecciones(hist)
    except Exception as e:
        print("Lecciones IA fallaron:", e)
    est = _leer(ESTRATEGIA, {})
    if pesos:
        est["pesos"] = pesos
    if lec:
        est["lecciones"] = lec
    if ideas:
        est["ideas"] = ideas
    est["actualizado"] = time.strftime("%Y-%m-%d")
    ESTRATEGIA.write_text(json.dumps(est, ensure_ascii=False, indent=1), "utf-8")
    try:
        runs = fallos_semana()
    except Exception:
        runs = None
    publicar_informe(informe(hist, tabla, lec, ideas, resumen, runs))
