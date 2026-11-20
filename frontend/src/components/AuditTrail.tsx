import { useEffect, useState } from "react";
import {
  Activity,
  AlertCircle,
  Check,
  ChevronDown,
  Copy,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import type { AuditEvent, Run } from "../lib/types";
import { api } from "../lib/api";
import {
  actorName,
  actorForEvent,
  eventFacts,
  isFallback,
} from "../lib/workflow";

export function EventDetails({ event }: { event: AuditEvent }) {
  const [copied, setCopied] = useState(false);
  const facts = eventFacts(event);
  return (
    <div className="event-details">
      <span className="eyebrow">{actorName(actorForEvent(event))}</span>
      <h3>{event.summary}</h3>
      {isFallback(event) && (
        <span className="fallback-label">
          A fallback was used for this step
        </span>
      )}
      {facts.length > 0 && (
        <dl className="event-facts">
          {facts.map((f, i) => (
            <div key={i}>
              <dt>{f.label}</dt>
              <dd>{f.value}</dd>
            </div>
          ))}
        </dl>
      )}
      <details className="technical-details">
        <summary>
          Event data <ChevronDown size={14} />
        </summary>
        <pre>
          {JSON.stringify(
            {
              action: event.action,
              data: event.data,
              hash: event.hash,
              prev_hash: event.prev_hash,
            },
            null,
            2,
          )}
        </pre>
        <button
          className="text-button"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(
                JSON.stringify(event, null, 2),
              );
              setCopied(true);
            } catch {
              setCopied(false);
            }
          }}
        >
          <Copy size={14} />
          {copied ? "Copied" : "Copy event"}
        </button>
      </details>
    </div>
  );
}
export function AuditTrail({
  run,
  events,
  demo,
}: {
  run: Run | null;
  events: AuditEvent[];
  demo: boolean;
}) {
  const [audit, setAudit] = useState<{
    events: AuditEvent[];
    chain_valid: boolean;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!run) return;
    const controller = new AbortController();
    setAudit(null);
    setError("");
    api
      .audit(run.id, controller.signal)
      .then(setAudit)
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [run?.id, events.length]);
  if (!run)
    return (
      <div className="empty-state">
        <Activity size={33} />
        <h3>A story waiting to unfold.</h3>
        <p>
          Start a room to follow its decisions, recommendations, and store
          actions.
        </p>
      </div>
    );
  return (
    <>
      <div className="audit-summary">
        <div>
          <span className="eyebrow">ROOM SESSION</span>
          <code>{run.id}</code>
        </div>
        {audit ? (
          <span
            className={`verified-badge ${audit.chain_valid ? "" : "invalid"}`}
          >
            {audit.chain_valid ? (
              <ShieldCheck size={15} />
            ) : (
              <AlertCircle size={15} />
            )}
            {audit.chain_valid ? "Chain verified" : "Verification failed"}
          </span>
        ) : (
          <LoaderCircle className="spin" size={18} />
        )}
      </div>
      <p className="audit-explainer">
        {demo
          ? "Demo events with a locally verified hash chain."
          : "Every agent decision and store action, with verification from the backend."}
      </p>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      <div className="audit-timeline">
        {(audit?.events || events).map((event) => (
          <article className="audit-event" key={event.seq}>
            <span className="audit-dot">
              <Check size={12} />
            </span>
            <div className="audit-event-heading">
              <strong>{actorName(actorForEvent(event))}</strong>
              <time dateTime={event.ts}>
                {new Date(event.ts).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                  second: "2-digit",
                })}
              </time>
            </div>
            <p>{event.summary}</p>
            {isFallback(event) && (
              <span className="fallback-label">Fallback used</span>
            )}
            <details>
              <summary>
                View result <ChevronDown size={13} />
              </summary>
              <EventDetails event={event} />
            </details>
          </article>
        ))}
      </div>
    </>
  );
}
