// frontend/src/api/client.ts

type TokenProvider = () => Promise<string>;

/**
 * Typed fetch wrapper that attaches Bearer tokens to every request.
 * In local mode, the token provider returns a static dev token.
 */
export class ApiClient {
  private baseUrl: string;
  private getToken: TokenProvider;

  constructor(baseUrl: string, getToken: TokenProvider) {
    this.baseUrl = baseUrl;
    this.getToken = getToken;
  }

  private async headers(): Promise<HeadersInit> {
    const token = await this.getToken();
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  }

  async get<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "GET",
      headers: await this.headers(),
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<T>;
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: await this.headers(),
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<T>;
  }

  async patch<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "PATCH",
      headers: await this.headers(),
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<T>;
  }

  async delete<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: await this.headers(),
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<T>;
  }
}

export class ApiError extends Error {
  status: number;
  body: string;

  constructor(status: number, body: string) {
    super(`API error ${status}: ${body}`);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/**
 * Create the singleton ApiClient instance.
 * In local mode, the token provider returns a static string.
 * In production, the caller passes the MSAL token acquisition function.
 */
let clientInstance: ApiClient | null = null;

export function getApiClient(getToken?: TokenProvider): ApiClient {
  if (clientInstance) return clientInstance;

  const baseUrl = import.meta.env.VITE_API_BASE_URL || "";
  const isLocalMode = import.meta.env.VITE_LOCAL_MODE === "true";
  const tokenProvider =
    isLocalMode || !getToken
      ? () => Promise.resolve("local-dev-token")
      : getToken;

  clientInstance = new ApiClient(baseUrl, tokenProvider);
  return clientInstance;
}
