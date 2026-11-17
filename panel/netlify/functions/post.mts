import type { Config, Context } from "@netlify/functions"
import { REPO, json, token } from "../lib/tt.mts"

export default async (req: Request, context: Context) => {
  const t = await token(req, context)
  if (!t) return json({ error: "Inicia sesión con TikTok" }, 401)
  const b = await req.json()
  if (!b.privacy_level) return json({ error: "Elige quién puede ver el vídeo" }, 400)
  if (!/^[\w.-]+$/.test(b.tag || "")) return json({ error: "vídeo no válido" }, 400)
  const rel = await fetch(`https://api.github.com/repos/${REPO}/releases/tags/${b.tag}`, { headers: { "User-Agent": "sabias-que-jarvis" } }).then((x) => x.json())
  const mp4 = rel.assets?.find((a: any) => a.name.endsWith(".mp4"))
  if (!mp4) return json({ error: "vídeo no encontrado" }, 404)
  const buf = new Uint8Array(await fetch(mp4.browser_download_url).then((x) => x.arrayBuffer()))
  const h = { Authorization: `Bearer ${t}`, "Content-Type": "application/json; charset=UTF-8" }
  const brand = b.brand_content_toggle === true, organic = b.brand_organic_toggle === true
  const init = await fetch("https://open.tiktokapis.com/v2/post/publish/video/init/", { method: "POST", headers: h, body: JSON.stringify({
    post_info: { title: String(b.title || "").slice(0, 2200), privacy_level: b.privacy_level,
      disable_comment: !b.allow_comment, disable_duet: !b.allow_duet, disable_stitch: !b.allow_stitch,
      brand_content_toggle: brand, brand_organic_toggle: organic, video_cover_timestamp_ms: 800 },
    source_info: { source: "FILE_UPLOAD", video_size: buf.length, chunk_size: buf.length, total_chunk_count: 1 } }) }).then((x) => x.json())
  if (init.error?.code && init.error.code !== "ok") return json({ error: init.error.message || init.error.code, code: init.error.code }, 400)
  const up = await fetch(init.data.upload_url, { method: "PUT", body: buf, headers: {
    "Content-Type": "video/mp4", "Content-Range": `bytes 0-${buf.length - 1}/${buf.length}` } })
  if (!up.ok) return json({ error: "Fallo subiendo el vídeo: " + up.status }, 500)
  return json({ publish_id: init.data.publish_id })
}
export const config: Config = { path: "/api/post", method: "POST" }
