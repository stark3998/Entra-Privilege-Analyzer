// frontend/src/api/client.ts

type TokenProvider = () => Promise<string>;

declare global {
  interface Window {
    __scanStreamDebug?: {
      path: string;
      startedAt: string;
      responseStatus: number | null;
      responseContentType: string | null;
      chunkCount: number;
      rawEventCount: number;
      parsedEventCount: number;
      lastEventId: string | null;
      lastEventType: string | null;
      lastMessage: string | null;
      lastChunkPreview: string | null;
      lastRawEventPreview: string | null;
      lastError: string | null;
      completed: boolean;
    };
  }
}

function createScanStreamDebugState(path: string) {
  return {
    path,
    startedAt: new Date().toISOString(),
    responseStatus: null as number | null,
    responseContentType: null as string | null,
    chunkCount: 0,
    rawEventCount: 0,
    parsedEventCount: 0,
    lastEventId: null as string | null,
    lastEventType: null as string | null,
    lastMessage: null as string | null,
    lastChunkPreview: null as string | null,
    lastRawEventPreview: null as string | null,
    lastError: null as string | null,
    completed: false,
  };
}

export interface ServerSentEventMessage<T = unknown> {
  event: string;
  data: T;
  id?: string;
}

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

  setTokenProvider(getToken: TokenProvider): void {
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

  async put<T>(path: string, body: unknown): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "PUT",
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

  async getBlob(path: string): Promise<Blob> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "GET",
      headers: await this.headers(),
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.blob();
  }

  async delete<T>(path: string): Promise<T> {
    const res = await fetch(`${this.baseUrl}${path}`, {
      method: "DELETE",
      headers: await this.headers(),
    });
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<T>;
  }

  async stream<T>(
    path: string,
    onMessage: (message: ServerSentEventMessage<T>) => void,
    signal?: AbortSignal,
  ): Promise<void> {
    const debugState = createScanStreamDebugState(path);
    window.__scanStreamDebug = debugState;
    const requestUrl = `${this.baseUrl}${path}`;

    const headers = await this.headers();
    const res = await fetch(requestUrl, {
      method: "GET",
      headers: {
        ...headers,
        Accept: "text/event-stream",
      },
      signal,
    });
    debugState.responseStatus = res.status;
    debugState.responseContentType = res.headers.get("content-type");
    if (!res.ok || !res.body) {
      debugState.lastError = `HTTP ${res.status}`;
      debugState.completed = true;
      throw new ApiError(res.status, await res.text());
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    const findEventBoundary = (value: string): number => {
      const crlfBoundary = value.indexOf("\r\n\r\n");
      const lfBoundary = value.indexOf("\n\n");

      if (crlfBoundary === -1) {
        return lfBoundary;
      }
      if (lfBoundary === -1) {
        return crlfBoundary;
      }
      return Math.min(crlfBoundary, lfBoundary);
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        debugState.completed = true;
        break;
      }

      const chunkText = decoder.decode(value, { stream: true });
      debugState.chunkCount += 1;
      debugState.lastChunkPreview = chunkText.slice(0, 400);
      buffer += chunkText;

      let boundary = findEventBoundary(buffer);
      while (boundary >= 0) {
        const rawEvent = buffer.slice(0, boundary);
        const separatorLength = buffer.startsWith("\r\n\r\n", boundary) ? 4 : 2;
        buffer = buffer.slice(boundary + separatorLength);
        boundary = findEventBoundary(buffer);
        debugState.rawEventCount += 1;
        debugState.lastRawEventPreview = rawEvent.slice(0, 400);

        const lines = rawEvent.split(/\r?\n/);
        let event = "message";
        let id: string | undefined;
        const dataLines: string[] = [];

        for (const line of lines) {
          if (!line || line.startsWith(":")) {
            continue;
          }
          if (line.startsWith("event:")) {
            event = line.slice(6).trim();
            continue;
          }
          if (line.startsWith("id:")) {
            id = line.slice(3).trim();
            continue;
          }
          if (line.startsWith("data:")) {
            dataLines.push(line.slice(5).trim());
          }
        }

        if (dataLines.length === 0) {
          continue;
        }

        const jsonStr = dataLines.join("\n");
        const parsed = JSON.parse(jsonStr) as T & { message?: string };
        debugState.parsedEventCount += 1;
        debugState.lastEventId = id ?? null;
        debugState.lastEventType = event;
        debugState.lastMessage = parsed.message ?? null;

        onMessage({
          event,
          id,
          data: parsed,
        });
      }
    }
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
  const baseUrl = import.meta.env.VITE_API_BASE_URL || "";
  const isLocalMode = import.meta.env.VITE_LOCAL_MODE === "true";
  const tokenProvider =
    isLocalMode || !getToken
      ? () => Promise.resolve("local-dev-token")
      : getToken;

  if (clientInstance) {
    if (!isLocalMode && getToken) {
      clientInstance.setTokenProvider(getToken);
    }
    return clientInstance;
  }

  clientInstance = new ApiClient(baseUrl, tokenProvider);
  return clientInstance;
}
