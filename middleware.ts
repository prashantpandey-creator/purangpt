import { NextResponse, type NextRequest } from "next/server";

// Routes that require authentication — /chat is intentionally open
const PROTECTED_PREFIXES = ["/settings", "/profile"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p));
  if (!isProtected) return NextResponse.next();

  // Check for our session cookies (purangpt_session = Google, logto_session = Logto email)
  const sessionCookie =
    request.cookies.get("logto_session")?.value ||
    request.cookies.get("purangpt_session")?.value;

  if (!sessionCookie) {
    // Redirect to home — the SignInModal will open on the landing page
    const url = request.nextUrl.clone();
    url.pathname = "/";
    url.searchParams.set("signin", "1");
    return NextResponse.redirect(url);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/settings/:path*",
    "/profile/:path*",
    // Exclude static files and API routes from middleware
    "/((?!_next/static|_next/image|favicon.ico|icon-|apple-touch|api/).*)",
  ],
};
