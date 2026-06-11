import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Redirect legacy /main/* paths to /* (browser cache dari versi lama)
export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  if (pathname.startsWith("/main/")) {
    const newPath = pathname.replace(/^\/main/, "");
    const url = request.nextUrl.clone();
    url.pathname = newPath || "/";
    return NextResponse.redirect(url, { status: 301 });
  }
}

export const config = {
  matcher: ["/main/:path*"],
};
