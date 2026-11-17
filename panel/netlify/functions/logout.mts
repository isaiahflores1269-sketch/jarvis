import type { Config, Context } from "@netlify/functions"
export default async (req: Request, context: Context) => {
  context.cookies.delete("tt")
  return Response.redirect(new URL("/", req.url).toString(), 302)
}
export const config: Config = { path: "/api/logout" }
