"""Prueba: sube a TikTok el último Short publicado en Releases (sin crear vídeo nuevo)."""
import os, requests, jarvis
repo, tok = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
h = {"Authorization": f"Bearer {tok}"}
rel = requests.get(f"https://api.github.com/repos/{repo}/releases/latest", headers=h, timeout=30).json()
a = next(x for x in rel["assets"] if x["name"].endswith(".mp4"))
open("out.mp4", "wb").write(requests.get(a["browser_download_url"], timeout=300).content)
d = {"titulo": rel.get("name", "¿Sabías que...?"), "descripcion": "", "hashtags": ["#curiosidades", "#sabiasque"]}
jarvis.subir_tiktok("out.mp4", d)
