import {
  AlertCircle,
  Ban,
  BadgeCheck,
  CheckCheck,
  ExternalLink,
  FileCheck2,
  Plus,
  ShieldCheck,
  ShoppingBag,
} from "lucide-react";
import type { AuditEvent, MerchantResult, Run } from "../lib/types";
import { money, STORE_NAMES } from "../lib/types";
import { safeExternalUrl } from "../lib/workflow";
import { StoreMark } from "./ui";

export function RunResults({
  run,
  events,
  simulation,
  onCart,
  onAudit,
  onNewRoom,
}: {
  run: Run;
  events: AuditEvent[];
  simulation: boolean;
  onCart: (m: MerchantResult) => void;
  onAudit: () => void;
  onNewRoom: () => void;
}) {
  const success = ["completed", "partial"].includes(run.state);
  const rejected = run.state === "rejected";
  const learned = events.some(
    (e) => /learn|remember/.test(e.action) && e.actor === "memory",
  );
  return (
    <section className="results-screen">
      <div className="surface result-intro">
        <span className={`completion-icon ${success ? "" : "neutral"}`}>
          {success ? (
            <CheckCheck size={31} />
          ) : rejected ? (
            <Ban size={30} />
          ) : (
            <AlertCircle size={30} />
          )}
        </span>
        <div>
          <span className="eyebrow">
            {simulation ? "DEMO RESULTS" : "YOUR NEXT STEPS"}
          </span>
          <h2>
            {rejected
              ? "Your space, your choice."
              : run.state === "failed"
                ? "A little snag along the way."
                : run.state === "partial"
                  ? "Some pieces are ready."
                  : "Good things, brought together."}
          </h2>
          <p>
            {rejected
              ? run.payment.status === "canceled"
                ? "Your collection was declined and its payment hold was released."
                : "Your collection was declined. See the payment status below."
              : run.state === "failed"
                ? run.error?.message ||
                  "We could not finish this room. Try a clearer room photo or check the activity trail."
                : simulation
                  ? "This is a simulated order and cart handoff. No real orders were placed and no money moved."
                  : "Automatic-purchase orders and store checkout links are below. Open each store cart to complete its checkout."}
          </p>
        </div>
      </div>
      {success && (
        <>
          <div className="result-stats">
            <div>
              <span>Approved item subtotal</span>
              <strong>{money(run.totals.items_usd)}</strong>
            </div>
            <div>
              <span>
                {simulation ? "Simulated amount captured" : "Amount captured"}
              </span>
              <strong>{money(run.totals.captured_usd)}</strong>
            </div>
            <div>
              <span>Payment status</span>
              <strong className="payment-status">
                {run.payment.status.replaceAll("_", " ")}
              </strong>
            </div>
          </div>
          <div className="result-merchants">
            {run.merchant_results.map((result) => (
              <article
                className={`surface merchant-result ${result.status === "failed" ? "failed" : ""}`}
                key={result.store}
              >
                <div className="merchant-title">
                  <StoreMark store={result.store} />
                  <h3>{STORE_NAMES[result.store]}</h3>
                  <span className={`merchant-status ${result.status}`}>
                    {result.status === "ordered"
                      ? simulation
                        ? "Demo order"
                        : "Ordered"
                      : result.status === "cart_ready"
                        ? "Cart ready"
                        : result.status === "link_ready"
                          ? "Link ready"
                          : "Needs attention"}
                  </span>
                </div>
                <strong className="merchant-amount">
                  {money(result.amount_usd)}
                </strong>
                <p>
                  {result.item_ids.length} selected{" "}
                  {result.item_ids.length === 1 ? "piece" : "pieces"}
                  {result.order_id ? ` · Order ${result.order_id}` : ""}
                </p>
                {result.error && <p className="inline-error">{result.error}</p>}
                {result.status === "ordered" ? (
                  <span className="order-confirmation">
                    <BadgeCheck size={18} />
                    {simulation
                      ? "Simulated order recorded"
                      : "Order confirmed by the store"}
                  </span>
                ) : result.url && result.status !== "failed" ? (
                  simulation && result.url.startsWith("/demo-cart/") ? (
                    <button
                      className="secondary-button full-width"
                      onClick={() => onCart(result)}
                    >
                      Preview demo cart <ExternalLink size={15} />
                    </button>
                  ) : safeExternalUrl(result.url) ? (
                    <a
                      className="primary-button full-width"
                      target="_blank"
                      rel="noopener noreferrer"
                      href={safeExternalUrl(result.url)!}
                    >
                      {result.mode === "product_link"
                        ? "Open product page"
                        : "Open store cart"}
                      <ExternalLink size={15} />
                    </a>
                  ) : (
                    <p className="inline-error">
                      The store did not return a usable checkout link.
                    </p>
                  )
                ) : result.status === "failed" ? (
                  <p className="merchant-help">
                    This store needs attention. Review its error and the
                    activity trail before trying another order.
                  </p>
                ) : null}
              </article>
            ))}
          </div>
        </>
      )}
      {!success && (
        <div className="payment-outcome">
          <ShieldCheck size={17} />
          <span>
            Payment status:{" "}
            <strong>{run.payment.status.replaceAll("_", " ")}</strong> · Held{" "}
            {money(run.totals.held_usd)} · Captured{" "}
            {money(run.totals.captured_usd)}
          </span>
        </div>
      )}
      {learned && (
        <div className="learned-note">
          <ShieldCheck size={17} />
          <p>
            {simulation
              ? "Your selections were remembered for this local demo session."
              : "The memory agent recorded your choices for future rooms."}
          </p>
        </div>
      )}
      <div className="result-actions">
        <button className="primary-button" onClick={onNewRoom}>
          <Plus size={17} />
          Start another room
        </button>
        <button className="secondary-button" onClick={onAudit}>
          <FileCheck2 size={17} />
          View activity trail
        </button>
      </div>
    </section>
  );
}
