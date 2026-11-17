import type { Config, Context } from "@netlify/functions"
import { CK, CS, seal } from "../lib/tt.mts"

export default async (req: Request, context: Context) => {
  const q = new URL(req.url).searchParams
  if (q.get("error")) return Response.redirect(new URL("/?error=" + encodeURIComponent(q.get("error_description") || q.get("error")!), req.url).toString(), 302)
  if (!q.get("state") || q.get("state") !== context.cookies.get("st")) return new Response("Estado no válido", { status: 400 })
  const r = await fetch("https://open.tiktokapis.com/v2/oauth/token/", {
    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ client_key: CK(), client_secret: CS(), code: q.get("code") || "",
      grant_type: "authorization_code", redirect_uri: new URL("/api/callback", req.url).toString() }),
  }).then((x) => x.json())
  if (!r.access_token) return new Response("Error TikTok: " + JSON.stringify(r), { status: 400 })
  context.cookies.set({ name: "tt", value: seal({ access_token: r.access_token, exp: Date.now() + r.expires_in * 1000 }),
    httpOnly: true, secure: true, sameSite: "Lax", path: "/", maxAge: r.expires_in })
  context.cookies.delete("st")
  return Response.redirect(new URL("/", req.url).toString(), 302)
}
export const config: Config = { path: "/api/callback" }
