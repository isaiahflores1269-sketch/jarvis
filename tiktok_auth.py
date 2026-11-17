"""Conecta la cuenta de TikTok: cambia el código de autorización por un refresh token y lo guarda cifrado."""
import os, sys, urllib.parse, requests
import jarvis

code = urllib.parse.unquote(sys.argv[1].strip())
r = requests.post("https://open.tiktokapis.com/v2/oauth/token/", timeout=30,
                  headers={"Content-Type": "application/x-www-form-urlencoded"}, data={
    "client_key": os.environ["TT_CLIENT_KEY"], "client_secret": os.environ["TT_CLIENT_SECRET"],
    "code": code, "grant_type": "authorization_code",
    "redirect_uri": "https://isaiahflores1269-sketch.github.io/jarvis/tiktok.html"}).json()
if "refresh_token" not in r:
    sys.exit(f"Error TikTok: {r}")
jarvis.tt_guardar_token(r["refresh_token"])
print("TikTok conectado. Permisos:", r.get("scope"), "| caduca en", r.get("refresh_expires_in"), "s")
