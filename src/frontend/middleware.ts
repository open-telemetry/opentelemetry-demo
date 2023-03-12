import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {

  const response = NextResponse.next()

  // set Instana EUM server-timing response header
  const traceId = request.headers.get('x-instana-t') || ''
  response.headers.set('Server-Timing', `intid;desc=${traceId}`)
  
  return response
}
