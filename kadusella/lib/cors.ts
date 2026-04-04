import { NextRequest, NextResponse } from "next/server";
import { webAppUrl } from "@/lib/env";

function allowedOrigins(): string[] {
  const extra = (process.env.CORS_ALLOW_ORIGINS || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

  return Array.from(
    new Set([
      webAppUrl(),
      "http://localhost:5173",
      "http://127.0.0.1:5173",
      ...extra,
    ]),
  );
}

function resolveOrigin(request: NextRequest): string {
  const origin = request.headers.get("origin") || "";
  return allowedOrigins().includes(origin) ? origin : webAppUrl();
}

export function withCors(request: NextRequest, response: NextResponse): NextResponse {
  response.headers.set("Access-Control-Allow-Origin", resolveOrigin(request));
  response.headers.set("Access-Control-Allow-Methods", "GET,POST,OPTIONS");
  response.headers.set("Access-Control-Allow-Headers", "Authorization,Content-Type");
  response.headers.set("Vary", "Origin");
  return response;
}

export function preflight(request: NextRequest): NextResponse {
  return withCors(request, new NextResponse(null, { status: 204 }));
}
