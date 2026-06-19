export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function toCamelCase(key: string): string {
  return key.replace(/_([a-z])/g, (_, char: string) => char.toUpperCase());
}

export function normalizeKeys<T>(value: unknown): T {
  if (Array.isArray(value)) {
    return value.map((item) => normalizeKeys(item)) as T;
  }

  if (value !== null && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, nested]) => [
        toCamelCase(key),
        normalizeKeys(nested),
      ]),
    ) as T;
  }

  return value as T;
}

function getBaseUrl(): string {
  const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (!baseUrl) {
    throw new ApiError(
      0,
      "NEXT_PUBLIC_API_BASE_URL is not configured. Copy .env.example to .env.local.",
    );
  }
  return baseUrl.replace(/\/$/, "");
}

export async function apiRequest<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = `${getBaseUrl()}/api/v1${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError(
      0,
      `Unable to reach governance API at ${url}. Ensure the FastAPI backend is running.`,
    );
  }

  if (!response.ok) {
    let message = response.statusText;
    try {
      const body = (await response.json()) as { detail?: string | { msg: string }[] };
      if (typeof body.detail === "string") {
        message = body.detail;
      } else if (Array.isArray(body.detail)) {
        message = body.detail.map((entry) => entry.msg).join("; ");
      }
    } catch {
      const text = await response.text();
      if (text) message = text;
    }
    throw new ApiError(response.status, message);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const json = (await response.json()) as unknown;
  return normalizeKeys<T>(json);
}
