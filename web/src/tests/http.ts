import { vi } from "vitest";

export interface MockCall {
  url: URL;
  method: string;
  headers: Headers;
  body: unknown;
  signal: AbortSignal | null;
}

export interface MockRequest {
  url: URL;
  method: string;
  headers: Headers;
  body: unknown;
  signal: AbortSignal | null;
}

export interface MockRoute {
  method: string;
  path: string | RegExp;
  respond: (request: MockRequest) => Response | Promise<Response>;
}

export function jsonResponse(
  body: unknown,
  status = 200,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

export function errorResponse(
  status: number,
  code: string,
  message: string,
  extra: Record<string, unknown> = {},
): Response {
  return jsonResponse(
    {
      error: {
        code,
        message,
        request_id: "test-request",
        ...extra,
      },
    },
    status,
  );
}

function pathMatches(routePath: string | RegExp, pathname: string): boolean {
  if (typeof routePath === "string") return routePath === pathname;
  return routePath.test(pathname);
}

export function installFetchMock(routes: MockRoute[]) {
  const calls: MockCall[] = [];
  const originalFetch = globalThis.fetch;

  const mock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const rawUrl =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const url = new URL(rawUrl, "http://localhost");
    const method = (init?.method ?? "GET").toUpperCase();
    const headers = new Headers(init?.headers);
    let body: unknown;
    if (typeof init?.body === "string" && init.body) {
      try {
        body = JSON.parse(init.body);
      } catch {
        body = init.body;
      }
    }
    const call: MockCall = {
      url,
      method,
      headers,
      body,
      signal: init?.signal ?? null,
    };
    calls.push(call);

    if (init?.signal?.aborted) {
      throw new DOMException("Aborted", "AbortError");
    }

    const route = routes.find(
      (candidate) =>
        candidate.method.toUpperCase() === method &&
        pathMatches(candidate.path, url.pathname),
    );
    if (!route) {
      throw new Error(`Solicitud no simulada: ${method} ${url.pathname}`);
    }
    return route.respond(call);
  });

  globalThis.fetch = mock as unknown as typeof fetch;

  return {
    calls,
    restore: () => {
      globalThis.fetch = originalFetch;
    },
    callsFor: (path: string) =>
      calls.filter((call) => call.url.pathname === path),
  };
}
