import type {
  AuditEvent,
  CreateRunInput,
  Health,
  Run,
  RunState,
} from "./types";
import { isTerminal } from "./types";
import { actorForEvent, profileFromEvent } from "./workflow";

const ENV = import.meta.env || {};
const BASE = (ENV.VITE_API_BASE_URL || "").replace(/\/$/, "");
export const DEMO_MODE = ENV.VITE_API_MODE !== "live";
export const assetUrl = (url?: string | null) =>
  url?.startsWith("/api/") ? `${BASE}${url}` : url || "/products/fallback.svg";
export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status = 0,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export const friendlyErrors: Record<string, string> = {
  RUN_NOT_FOUND:
    "This room session has expired. Start a new room to try again.",
  INVALID_STATE:
    "This room has already changed. We will refresh its current status.",
  BAD_INPUT: "Please check the photo and room preferences.",
  PAYMENT_FAILED:
    "Payment could not be completed. Review the payment status before trying again.",
  INTERNAL: "Hivly hit a snag. Please try again in a moment.",
  NETWORK_ERROR:
    "We could not reach Hivly. Check your connection and try again.",
  LLM_TIMEOUT:
    "The styling team took longer than expected. You can try your room again.",
};
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      signal: init?.signal ?? AbortSignal.timeout(120000),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new ApiError("NETWORK_ERROR", friendlyErrors.NETWORK_ERROR);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      data?.error?.code || "INTERNAL",
      data?.error?.message || friendlyErrors.INTERNAL,
      response.status,
    );
  if (!data)
    throw new ApiError(
      "INTERNAL",
      "The server returned an unreadable response.",
    );
  return data as T;
}
export const api = {
  health: () => request<Health>("/api/health"),
  async createRun(input: CreateRunInput) {
    const body = new FormData();
    body.append("photo", input.photo);
    body.append("user_id", input.user_id);
    body.append("budget_usd", String(input.budget_usd));
    body.append("stores", input.stores.join(","));
    if (input.note) body.append("note", input.note);
    return request<{ run_id: string; state: RunState }>("/api/runs", {
      method: "POST",
      body,
    });
  },
  getRun: (id: string, signal?: AbortSignal) =>
    request<Run>(`/api/runs/${encodeURIComponent(id)}`, { signal }),
  approve: (id: string, ids: string[]) =>
    request<Run>(`/api/runs/${encodeURIComponent(id)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selected_item_ids: ids }),
    }),
  reject: (id: string, reason: string) =>
    request<Run>(`/api/runs/${encodeURIComponent(id)}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }),
  audit: (id: string, signal?: AbortSignal) =>
    request<{ events: AuditEvent[]; chain_valid: boolean }>(
      `/api/runs/${encodeURIComponent(id)}/audit`,
      { signal },
    ),
};

export interface RunSubscriptionHandlers {
  onStep: (event: AuditEvent) => void;
  onRun: (run: Run) => void;
  onProfile?: (profile: NonNullable<Run["room"]>) => void;
  onError: (error: Error) => void;
  onFallback: () => void;
}
/** Transport injection permits genuine SSE-disconnect/polling tests without a browser. */
export function watchRun(
  id: string,
  handlers: RunSubscriptionHandlers,
  transport: {
    stream: (url: string) => Pick<EventSource, "addEventListener" | "close">;
    run: (id: string, signal: AbortSignal) => Promise<Run>;
    audit: (
      id: string,
      signal: AbortSignal,
    ) => Promise<{ events: AuditEvent[]; chain_valid: boolean }>;
    interval?: number;
  },
) {
  const controller = new AbortController();
  let stopped = false;
  let polling = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  const source = transport.stream(
    `${BASE}/api/runs/${encodeURIComponent(id)}/events`,
  );
  const close = () => {
    stopped = true;
    source.close();
    controller.abort();
    clearTimeout(timer);
  };
  const stopIfReady = (run: Run) => {
    if (isTerminal(run.state) || run.state === "awaiting_approval") close();
  };
  const acceptStep = (event: AuditEvent) => {
    handlers.onStep(event);
    const profile = profileFromEvent(event);
    if (profile) handlers.onProfile?.(profile);
  };
  const refreshRun = async () => {
    try {
      const run = await transport.run(id, controller.signal);
      if (!stopped) {
        handlers.onRun(run);
        stopIfReady(run);
      }
    } catch (error) {
      if (!stopped)
        handlers.onError(
          error instanceof Error ? error : new Error("Connection interrupted"),
        );
    }
  };
  let auditInFlight = false;
  const poll = async () => {
    // Keep run status independent of a failed or slow audit request, with at most one audit in flight.
    if (!auditInFlight) {
      auditInFlight = true;
      void transport
        .audit(id, controller.signal)
        .then((audit) => {
          if (!stopped) audit.events.forEach(acceptStep);
        })
        .catch(() => {})
        .finally(() => {
          auditInFlight = false;
        });
    }
    try {
      const run = await transport.run(id, controller.signal);
      if (!stopped) {
        handlers.onRun(run);
        stopIfReady(run);
      }
    } catch (error) {
      if (!stopped)
        handlers.onError(
          error instanceof Error ? error : new Error("Connection interrupted"),
        );
    }
    if (!stopped) timer = setTimeout(poll, transport.interval ?? 1000);
  };
  function startPolling() {
    if (stopped || polling) return;
    polling = true;
    source.close();
    handlers.onFallback();
    void poll();
  }
  source.addEventListener("step", (event) => {
    if (stopped) return;
    try {
      const step = JSON.parse((event as MessageEvent).data) as AuditEvent;
      acceptStep(step);
      if (actorForEvent(step) === "vision" && !profileFromEvent(step))
        void refreshRun();
    } catch {
      startPolling();
    }
  });
  source.addEventListener("run", (event) => {
    if (stopped) return;
    try {
      const run = JSON.parse((event as MessageEvent).data) as Run;
      handlers.onRun(run);
      stopIfReady(run);
    } catch {
      startPolling();
    }
  });
  source.addEventListener("state", (event) => {
    try {
      const { state } = JSON.parse((event as MessageEvent).data);
      if (
        isTerminal(state) ||
        state === "awaiting_approval" ||
        state === "executing"
      )
        void refreshRun();
    } catch {
      startPolling();
    }
  });
  source.addEventListener("error", (event) => {
    if ("data" in event && (event as MessageEvent).data)
      try {
        const data = JSON.parse((event as MessageEvent).data);
        handlers.onError(new ApiError(data.code, data.message));
      } catch {
        /* poll reconciles */
      }
    startPolling();
  });
  return close;
}
export const subscribeToRun = (id: string, handlers: RunSubscriptionHandlers) =>
  watchRun(id, handlers, {
    stream: (url) => new EventSource(url),
    run: api.getRun,
    audit: api.audit,
  });
