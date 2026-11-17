// utilidades compartidas
import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto"

export const CK = () => (Netlify.env.get("TT_CLIENT_KEY") || "").trim()
export const CS = () => (Netlify.env.get("TT_CLIENT_SECRET") || "").trim()
export const REPO = "isaiahflores1269-sketch/jarvis"
const key = () => createHash("sha256").update("panel:" + CS()).digest()

export function seal(obj: unknown): string {
  const iv = randomBytes(12)
  const c = createCipheriv("aes-256-gcm", key(), iv)
  const enc = Buffer.concat([c.update(JSON.stringify(obj)), c.final()])
  return Buffer.concat([iv, c.getAuthTag(), enc]).toString("base64url")
}
export function unseal<T = any>(s?: string): T | null {
  try {
    const b = Buffer.from(s || "", "base64url")
    const d = createDecipheriv("aes-256-gcm", key(), b.subarray(0, 12))
    d.setAuthTag(b.subarray(12, 28))
    return JSON.parse(Buffer.concat([d.update(b.subarray(28)), d.final()]).toString())
  } catch { return null }
}
export async function token(req: Request, context: any): Promise<string | null> {
  const s = unseal<{ access_token: string; exp: number }>(context.cookies.get("tt"))
  return s && s.exp > Date.now() ? s.access_token : null
}
export const json = (d: unknown, status = 200) => Response.json(d, { status })
