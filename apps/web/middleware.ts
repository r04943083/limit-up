import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Web-layer access gate for the EXPOSED surface (the cloudflared tunnel serves :3000, not the
// localhost-only API :8000). When LU_WEB_PASSWORD is set, every route requires HTTP Basic auth
// (native browser prompt — no login page needed); credentials travel encrypted over the tunnel's
// HTTPS. Unset (default) = fully open, preserving the local single-user experience.
//
// This is the correct layer to lock down the deployment: the browser talks only to :3000, and
// the Next server proxies /api → :8000 server-side, so gating here protects the whole app without
// the API token having to round-trip through the (server-side, tokenless) proxy.
export function middleware(req: NextRequest) {
  const password = process.env.LU_WEB_PASSWORD;
  if (!password) return NextResponse.next(); // open by default

  const auth = req.headers.get("authorization") || "";
  if (auth.startsWith("Basic ")) {
    try {
      const decoded = atob(auth.slice(6)); // "user:pass"
      const pass = decoded.slice(decoded.indexOf(":") + 1);
      if (pass === password) return NextResponse.next();
    } catch {
      /* malformed header → fall through to challenge */
    }
  }
  return new NextResponse("需要登录", {
    status: 401,
    headers: { "WWW-Authenticate": 'Basic realm="limit-up (LU)", charset="UTF-8"' },
  });
}

// Gate everything except Next's own static assets (which don't leak app data).
export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
