import type { Config } from "@netlify/functions"
import { REPO, json } from "../lib/tt.mts"

// Vídeos creados por Jarvis (publicados en GitHub Releases del proyecto)
export default async () => {
  const rel = await fetch(`https://api.github.com/repos/${REPO}/releases?per_page=10`, {
    headers: { "User-Agent": "sabias-que-jarvis" } }).then((x) => x.json())
  const vids = (Array.isArray(rel) ? rel : []).map((r: any) => {
    const mp4 = r.assets?.find((a: any) => a.name.endsWith(".mp4"))
    const img = r.assets?.find((a: any) => /\.(jpg|png)$/.test(a.name))
    return mp4 && { id: r.tag_name, titulo: r.name, texto: (r.body || "").slice(0, 2000),
      video: `/api/media?tag=${encodeURIComponent(r.tag_name)}&f=${encodeURIComponent(mp4.name)}`,
      portada: img ? `/api/media?tag=${encodeURIComponent(r.tag_name)}&f=${encodeURIComponent(img.name)}` : null,
      size: mp4.size }
  }).filter(Boolean)
  return json(vids)
}
export const config: Config = { path: "/api/videos" }
