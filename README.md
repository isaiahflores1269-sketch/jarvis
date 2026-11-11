# JARVIS — Shorts de curiosidades 100% automáticos (0 €, solo GitHub)

Cada día GitHub Actions: Gemini escribe el guion → voz Edge-TTS + clips Pexels + subtítulos (FFmpeg) → sube a YouTube. Recuerda los temas usados en `temas.json`.

## 1. Repo
1. github.com → New repository → **`jarvis`** (público = minutos ilimitados).
2. *Add file → Upload files* → arrastra TODO el contenido del zip (incluida la carpeta `.github`).

## 2. Claves → Settings → Secrets and variables → Actions → New secret
| Secret | Dónde sacarlo |
|---|---|
| `GEMINI_API_KEY` | aistudio.google.com → Get API key |
| `PEXELS_API_KEY` | pexels.com/api |
| `YT_CLIENT_ID` / `YT_CLIENT_SECRET` | Paso 3 |
| `YT_REFRESH_TOKEN` | Paso 3 |

## 3. YouTube (una sola vez)
1. console.cloud.google.com → proyecto nuevo "jarvis" → activa **YouTube Data API v3**.
2. Pantalla de consentimiento OAuth → Externo → añádete como usuario de prueba → **Publicar app** (si no, el token caduca a los 7 días).
3. Credenciales → ID de cliente OAuth → **Aplicación web** → URI de redirección: `https://developers.google.com/oauthplayground` → copia ID y secreto.
4. developers.google.com/oauthplayground → ⚙️ *Use your own OAuth credentials* (pega ID y secreto) → scope `https://www.googleapis.com/auth/youtube.upload` → Authorize con la cuenta del canal → *Exchange* → copia el **refresh token**.

## 4. Probar
Actions → **Jarvis** → *Run workflow*. En ~4 min el Short está en el canal (y descargable en *Artifacts*).

## Ajustes
- Horario: `cron` en `.github/workflows/render.yml` (hora UTC).
- Voz: añade `JARVIS_VOICE: es-ES-ElviraNeural` en el `env` del workflow.
- Subir en privado para revisar: `YT_PRIVACY: private`.

## Avisos
- YouTube puede dejar en **privado** lo subido por apps no verificadas → solicita la auditoría gratuita de YouTube Data API.
- Evita contenido "repetitivo": varía temas/voz para poder monetizar.
