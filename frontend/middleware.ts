import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

const PUBLIC_PATHS = [
  '/auth/login',
  '/auth/signup',
  '/auth/forgot-password',
  '/auth/reset-password',
  '/auth/verify-email',
];

const PROTECTED_PATHS = [
  '/dashboard',
  '/assets',
  '/scans',
  '/findings',
  '/attack-paths',
  '/agents',
  '/remediation',
  '/reports',
  '/chat',
  '/team',
  '/settings',
];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublicPath = PUBLIC_PATHS.some(path => pathname.startsWith(path));
  const isProtectedPath = PROTECTED_PATHS.some(path => pathname.startsWith(path));

  if (isPublicPath) {
    return NextResponse.next();
  }

  if (isProtectedPath) {
    const hasAuthCookie = request.cookies.has('__session') || 
                          request.cookies.has('firebase-auth-token') ||
                          request.headers.get('authorization')?.startsWith('Bearer ');

    if (!hasAuthCookie) {
      const loginUrl = new URL('/auth/login', request.url);
      loginUrl.searchParams.set('callbackUrl', pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    '/((?!api|_next/static|_next/image|favicon.ico|.*\\.png$).*)',
  ],
};