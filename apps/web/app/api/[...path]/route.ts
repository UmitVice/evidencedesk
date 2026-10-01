import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";
export const maxDuration = 60;
const cookieName = "evidencedesk_session";
const uuid = "[0-9a-f-]{36}";
const routes = new Map<string, RegExp[]>([
  [
    "GET",
    [
      /^tickets$/,
      new RegExp(`^tickets/${uuid}$`),
      new RegExp(`^runs/${uuid}$`),
      new RegExp(`^runs/${uuid}/sources/${uuid}$`),
      new RegExp(`^sources/${uuid}$`),
    ],
  ],
  [
    "POST",
    [
      /^sessions$/,
      new RegExp(`^tickets/${uuid}/analyze$`),
      new RegExp(`^proposals/${uuid}/decision$`),
      /^voice\/ticket$/,
      new RegExp(`^tickets/${uuid}/transcribe$`),
    ],
  ],
]);
function failure(code: string, message: string, status: number) {
  return NextResponse.json(
    { error: { code, message, request_id: crypto.randomUUID() } },
    { status, headers: { "Cache-Control": "no-store" } },
  );
}
async function forward(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> },
) {
  const { path } = await context.params;
  const route = path.join("/");
  if (!routes.get(request.method)?.some((pattern) => pattern.test(route)))
    return failure("not_found", "Route unavailable.", 404);
  const origin =
    process.env.APP_ORIGIN ||
    (process.env.VERCEL_URL
      ? `https://${process.env.VERCEL_URL}`
      : "http://localhost:3000");
  if (request.method === "POST" && request.headers.get("origin") !== origin)
    return failure(
      "origin_rejected",
      "Reload this page before trying again.",
      403,
    );
  const audioRoute = new RegExp(`^tickets/${uuid}/transcribe$`).test(route);
  const contentType = audioRoute ? "audio/wav" : "application/json";
  let body: ArrayBuffer | undefined;
  if (request.method === "POST") {
    if (
      audioRoute
        ? request.headers.get("content-type") !== contentType
        : !request.headers.get("content-type")?.startsWith(contentType)
    )
      return failure(
        "invalid_request",
        "A supported request format is required.",
        415,
      );
    const reader = request.body?.getReader();
    const parts: Uint8Array[] = [];
    let size = 0;
    if (reader) {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        size += value.length;
        if (size > (audioRoute ? 960044 : 4096)) {
          await reader.cancel();
          return failure("body_too_large", "Request too large.", 413);
        }
        parts.push(value);
      }
    }
    body = Uint8Array.from(Buffer.concat(parts)).buffer;
  }
  const api = process.env.API_ORIGIN;
  const key = process.env.SERVICE_KEY;
  if (!api || !key)
    return failure(
      "sandbox_unavailable",
      "The interactive sandbox is not configured. You can still explore the walkthrough below.",
      503,
    );
  let apiUrl: URL;
  try {
    apiUrl = new URL(api);
    if (
      apiUrl.pathname !== "/" ||
      apiUrl.search ||
      apiUrl.hash ||
      apiUrl.username ||
      apiUrl.password
    )
      throw new Error("origin");
    if (
      apiUrl.protocol !== "https:" &&
      !(
        process.env.NODE_ENV !== "production" &&
        ["localhost", "127.0.0.1"].includes(apiUrl.hostname)
      )
    )
      throw new Error("protocol");
  } catch {
    return failure(
      "sandbox_unavailable",
      "The sandbox origin is not configured correctly.",
      503,
    );
  }
  const jar = await cookies();
  const token = jar.get(cookieName)?.value;
  if (route !== "sessions" && !token)
    return failure("session_expired", "Start a new sandbox session.", 401);
  try {
    const headers: Record<string, string> = {
      "Content-Type": contentType,
      "X-Service-Key": key,
    };
    if (token) headers["X-Session-Token"] = token;
    if (process.env.API_PROTECTION_BYPASS_SECRET)
      headers["x-vercel-protection-bypass"] =
        process.env.API_PROTECTION_BYPASS_SECRET;
    const upstream = await fetch(new URL(route, apiUrl), {
      method: request.method,
      body,
      headers,
      cache: "no-store",
      redirect: "error",
      signal: AbortSignal.timeout(45000),
    });
    const data = await upstream.json();
    if (route === "sessions" && upstream.ok) {
      if (
        typeof data.token !== "string" ||
        !/^[A-Za-z0-9_-]{43}$/.test(data.token)
      )
        throw new Error("session");
      jar.set(cookieName, data.token, {
        httpOnly: true,
        secure: process.env.NODE_ENV === "production",
        sameSite: "lax",
        path: "/",
        expires: new Date(data.expires_at),
      });
      delete data.token;
    }
    return NextResponse.json(data, {
      status: upstream.status,
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    return failure(
      "sandbox_unavailable",
      "The sandbox could not complete this request. Try again later.",
      503,
    );
  }
}
export const GET = forward;
export const POST = forward;
