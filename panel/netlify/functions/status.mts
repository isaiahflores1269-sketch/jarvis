import type { Config, Context } from "@netlify/functions"
import { json, token } from "../lib/tt.mts"
export default async (req: Request, context: Context) => {
  const t = await token(req, context)
  if (!t) return json({ error: "sin sesión" }, 401)
  const id = new URL(req.url).searchParams.get("id")
  const r = await fetch("https://open.tiktokapis.com/v2/post/publish/status/fetch/", { method: "POST",
    headers: { Authorization: `Bearer ${t}`, "Content-Type": "application/json; charset=UTF-8" }, body: JSON.stringify({ publish_id: id }) }).then((x) => x.json())
  return json(r)
}
export const config: Config = { path: "/api/status" }
