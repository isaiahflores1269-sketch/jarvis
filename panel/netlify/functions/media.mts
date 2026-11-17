import type { Config } from "@netlify/functions"
import { REPO } from "../lib/tt.mts"
// Proxy para ver la vista previa (GitHub no permite incrustar directamente)
export default async (req: Request) => {
  const q = new URL(req.url).searchParams
  const tag = q.get("tag") || "", f = q.get("f") || ""
  if (!/^[\w.-]+$/.test(tag) || !/^[\w.-]+$/.test(f)) return new Response("no", { status: 400 })
  const r = await fetch(`https://github.com/${REPO}/releases/download/${tag}/${f}`)
  return new Response(r.body, { status: r.status, headers: {
    "Content-Type": f.endsWith(".mp4") ? "video/mp4" : "image/jpeg", "Cache-Control": "public, max-age=3600" } })
}
export const config: Config = { path: "/api/media" }
