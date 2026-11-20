import { useEffect, useState } from "react";
import { motion } from "motion/react";
import {
  Activity,
  Brain,
  Check,
  Circle,
  Clock3,
  Eye,
  Leaf,
  Search,
  ShieldCheck,
  Sparkles,
  Wallet,
} from "lucide-react";
import type { AuditEvent, Run } from "../lib/types";
import {
  agentTimeline,
  actorForEvent,
  actorName,
  isFallback,
} from "../lib/workflow";
import { BeeLoader, BeeScene } from "./BeeScene";

const icons = {
  vision: Eye,
  memory: Brain,
  stylist: Sparkles,
  catalog: Search,
  curator: Leaf,
  critic: ShieldCheck,
  policy: ShieldCheck,
  payments: Wallet,
};
export function AgentWorkspace({
  run,
  events,
  fallback,
  reduced,
  onEvent,
  onAudit,
}: {
  run: Run;
  events: AuditEvent[];
  fallback: boolean;
  reduced: boolean;
  onEvent: (e: AuditEvent) => void;
  onAudit: () => void;
}) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  const timeline = agentTimeline(events, run.state);
  const current = timeline.find((a) => a.status === "working");
  const completed = timeline.filter((a) => a.status === "done").length;
  const executing = run.state === "executing";
  const elapsed = Math.max(
    0,
    Math.floor((now - Date.parse(run.created_at)) / 1000),
  );
  const latest = [...events]
    .reverse()
    .find((e) => !["user", "system"].includes(e.actor));
  return (
    <section className="surface agents-panel" aria-label="Agents at work">
      <div className="panel-heading">
        <span className="section-icon">
          <Sparkles size={23} />
        </span>
        <div>
          <h2>
            {executing ? "Bringing it together" : "Your hive, at work"}
          </h2>
          <p>
            {executing
              ? "Preparing orders, carts, and your next steps."
              : "A little expertise, working in harmony."}
          </p>
        </div>
      </div>
      <BeeScene variant="working" reduced={reduced} activity={current?.id || "payments"} />
      <div className="active-agent-summary">
        <span className="working-orb"><BeeLoader still={reduced} /></span>
        <div>
          <small className="active-agent-name">
            {executing ? "Store execution" : current?.name || "Styling team"}
          </small>
          <strong>
            {executing
              ? "Preparing your approved collection"
              : current?.task || "Putting the collection together"}
          </strong>
          <span>
            <Clock3 size={12} />
            {elapsed < 60
              ? `${elapsed}s elapsed`
              : `${Math.floor(elapsed / 60)}m ${elapsed % 60}s elapsed`}
          </span>
        </div>
      </div>
      {!executing && (
        <>
          <div className="progress-caption">
            <span>
              {completed} of {timeline.length} preparation steps complete
            </span>
            <span>{fallback ? "Checking status" : "Live updates"}</span>
          </div>
          <div className="progress-track">
            <motion.span
              initial={{ width: 0 }}
              animate={{ width: `${(completed / timeline.length) * 100}%` }}
              transition={{ type: "tween", duration: reduced ? 0 : 0.35 }}
            />
          </div>
        </>
      )}
      <div className="agent-list" aria-label="Agent progress">
        {timeline.map((agent) => {
          const Icon = icons[agent.id];
          return (
            <motion.button
              layout={!reduced}
              key={agent.id}
              className={`agent-row ${agent.status}`}
              disabled={!agent.event}
              onClick={() => agent.event && onEvent(agent.event)}
              aria-label={`${agent.name}: ${agent.status}${agent.event ? ". View result" : ""}`}
            >
              <span className="agent-icon">
                <Icon size={17} />
              </span>
              <span className="agent-copy">
                <strong>
                  {agent.name}
                  {isFallback(agent.event) && (
                    <small className="fallback-label">Fallback used</small>
                  )}
                </strong>
                <span>
                  {agent.status === "working"
                    ? agent.task
                    : agent.event?.summary ||
                      (agent.status === "waiting"
                        ? "Waiting for its turn"
                        : "")}
                </span>
              </span>
              <span className="agent-status">
                {agent.status === "done" ? (
                  <Check size={16} />
                ) : agent.status === "working" ? (
                  <BeeLoader still={reduced} />
                ) : agent.status === "blocked" ? (
                  <span>!</span>
                ) : (
                  <Circle size={10} />
                )}
              </span>
            </motion.button>
          );
        })}
      </div>
      {latest && (
        <div className="latest-event" aria-live="polite">
          <span className="eyebrow">
            LATEST UPDATE · {actorName(actorForEvent(latest))}
          </span>
          <p>{latest.summary}</p>
        </div>
      )}
      <div className="agents-footer">
        <span>
          <span className="status-dot" />
          {fallback
            ? "SSE interrupted · polling every second"
            : "Following the agent event stream"}
        </span>
        <button className="text-button" onClick={onAudit}>
          <Activity size={14} />
          Full trail
        </button>
      </div>
    </section>
  );
}
