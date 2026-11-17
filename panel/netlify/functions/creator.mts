import type { Config, Context } from "@netlify/functions"
import { json, token } from "../lib/tt.mts"

export default async (req: Request, context: Context) => {
  const t = await token(req, context)
  if (!t) return json({ login: false })
  const r = await fetch("https://open.tiktokapis.com/v2/post/publish/creator_info/query/", {
    method: "POST", headers: { Authorization: `Bearer ${t}`, "Content-Type": "application/json; charset=UTF-8" } }).then((x) => x.json())
  return json({ login: true, ...r })
}
export const config: Config = { path: "/api/creator" }
