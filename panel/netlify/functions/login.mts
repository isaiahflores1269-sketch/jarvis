import type { Config, Context } from "@netlify/functions"
import { randomBytes } from "node:crypto"
import { CK } from "../lib/tt.mts"

export default async (req: Request, context: Context) => {
  const state = randomBytes(16).toString("hex")
  context.cookies.set({ name: "st", value: state, httpOnly: true, secure: true, sameSite: "Lax", path: "/" })
  const u = new URL("https://www.tiktok.com/v2/auth/authorize/")
  u.searchParams.set("client_key", CK())
  u.searchParams.set("scope", "user.info.basic,video.publish,video.upload")
  u.searchParams.set("response_type", "code")
  u.searchParams.set("redirect_uri", new URL("/api/callback", req.url).toString())
  u.searchParams.set("state", state)
  return Response.redirect(u.toString(), 302)
}
export const config: Config = { path: "/api/login" }
