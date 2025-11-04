import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';
import { v4 } from 'uuid';

export function middleware(request: NextRequest) {
  const response = NextResponse.next();

  if (!request.cookies.has('SESSIONID')) {
    response.cookies.set('SESSIONID', v4());
  }

  if (!request.cookies.has('USERID')) {
    response.cookies.set('USERID', v4());
  }

  return response;
}

export const config = {
  matcher: '/:path*',
};
