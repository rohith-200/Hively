import {
  Check,
  CheckCheck,
  ChevronDown,
  ExternalLink,
  Leaf,
  Plus,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
} from "lucide-react";
import { motion } from "motion/react";
import type { Run, RunItem, Store } from "../lib/types";
import { money, selectedTotals, STORE_NAMES } from "../lib/types";
import { executionLabel, roomLabel } from "../lib/workflow";
import { assetUrl } from "../lib/api";
import { RoomProfileCard, StoreMark } from "./ui";
import { BeeLoader } from "./BeeScene";

export function ReviewCollection({
  run,
  photo,
  selected,
  busy,
  simulation,
  reduced,
  onToggle,
  onDetail,
  onApprove,
  onReject,
  onAudit,
  onNewRoom,
}: {
  run: Run;
  photo: string;
  selected: string[];
  busy: boolean;
  simulation: boolean;
  reduced: boolean;
  onToggle: (id: string) => void;
  onDetail: (item: RunItem) => void;
  onApprove: () => void;
  onReject: () => void;
  onAudit: () => void;
  onNewRoom: () => void;
}) {
  const totals = selectedTotals(run.items, selected);
  const editable = run.state === "awaiting_approval";
  return (
    <div className="review-layout">
      <div className="collection-main">
        {run.room && (
          <div className="review-room-context">
            {photo && (
              <img src={photo} alt="The room guiding this collection" />
            )}
            <RoomProfileCard profile={run.room} demo={simulation} compact />
          </div>
        )}
        <div className="collection-heading">
          <div>
            <h2>Keep what feels right.</h2>
            <p>Each piece has a reason. Select the ones you love.</p>
          </div>
          <span className="selection-count" aria-live="polite">
            {selected.length} of {run.items.length} selected
          </span>
        </div>
        {run.items.length ? (
          (["shopify", "amazon", "walmart"] as Store[]).map((store) => {
            const items = run.items.filter((i) => i.product.store === store);
            if (!items.length) return null;
            return (
              <section
                className="store-group"
                key={store}
                aria-label={`${STORE_NAMES[store]} recommendations`}
              >
                <div className="store-group-title">
                  <StoreMark store={store} />
                  <h3>{STORE_NAMES[store]}</h3>
                  <span>
                    {items.length} {items.length === 1 ? "piece" : "pieces"}
                  </span>
                </div>
                <div className="product-grid">
                  {items.map((item) => (
                    <motion.article
                      layout={!reduced}
                      key={item.id}
                      className={`product-card ${selected.includes(item.id) ? "selected" : ""}`}
                    >
                      <div className="product-image">
                        <img
                          src={assetUrl(item.product.image_url)}
                          alt={item.product.name}
                          loading="lazy"
                          onError={(e) => {
                            if (
                              !e.currentTarget.src.endsWith(
                                "/products/fallback.svg",
                              )
                            )
                              e.currentTarget.src = "/products/fallback.svg";
                          }}
                        />
                        <label className="item-checkbox">
                          <input
                            type="checkbox"
                            checked={selected.includes(item.id)}
                            disabled={!editable || busy}
                            onChange={() => onToggle(item.id)}
                            aria-label={`Include ${item.product.name}`}
                          />
                          <span>
                            <Check size={15} />
                          </span>
                        </label>
                        {Number.isFinite(item.score) && item.score > 0 && (
                          <span className="match-chip">
                            <Sparkles size={12} />
                            {Math.round(item.score * 100)}% fit
                          </span>
                        )}
                      </div>
                      <div className="product-content">
                        <span className="category-label">{item.category}</span>
                        <div className="product-title">
                          <h4>{item.product.name}</h4>
                          <strong>{money(item.product.price_usd)}</strong>
                        </div>
                        <span className="execution-tag">
                          {executionLabel(item.execution_mode)}
                        </span>
                        <p>{item.reason}</p>
                        {item.critic_note && (
                          <span className="critic-note">
                            <ShieldCheck size={14} />
                            Checked & refined by the Critic
                          </span>
                        )}
                        <button
                          className="text-button"
                          onClick={() => onDetail(item)}
                        >
                          Why it belongs <Plus size={14} />
                        </button>
                      </div>
                    </motion.article>
                  ))}
                </div>
              </section>
            );
          })
        ) : (
          <div className="surface empty-state">
            <ShoppingBag size={32} />
            <h3>No suitable matches this time.</h3>
            <p>
              Try a larger budget, more stores, or another photo. Available
              products depend on the store catalog.
            </p>
            <button className="secondary-button" onClick={onNewRoom}>
              Try another direction
            </button>
          </div>
        )}
        {!!run.skipped.length && (
          <details className="skipped-items">
            <summary>
              <Leaf size={17} />
              {run.skipped.length}{" "}
              {run.skipped.length === 1 ? "category was" : "categories were"}{" "}
              left out <ChevronDown size={15} />
            </summary>
            {run.skipped.map((item, i) => (
              <div key={`${item.category}${i}`}>
                <strong>{item.category}</strong>
                <p>{item.reason}</p>
              </div>
            ))}
          </details>
        )}
      </div>
      <aside
        className="surface collection-summary"
        aria-label="Collection totals"
      >
        <span className="eyebrow">YOUR COLLECTION, YOUR CALL</span>
        <h2>A little more together.</h2>
        <div className="summary-total">
          <span>
            {totals.count} selected {totals.count === 1 ? "piece" : "pieces"}
          </span>
          <strong>{money(totals.total)}</strong>
          <small>of your {money(run.budget_usd)} budget</small>
        </div>
        <div
          className={`budget-meter ${totals.total > run.budget_usd ? "over-budget" : ""}`}
        >
          <span
            style={{
              width: `${Math.min(100, (totals.total / run.budget_usd) * 100)}%`,
            }}
          />
        </div>
        <p className="under-budget">
          <Leaf size={14} />
          {totals.total > run.budget_usd
            ? "Your selection exceeds the budget"
            : `${money(run.budget_usd - totals.total)} left in your budget`}
        </p>
        <div className="cost-breakdown">
          <div>
            <span>
              {simulation ? "Simulated order on approval" : "Order on approval"}
            </span>
            <strong>{money(totals.auto)}</strong>
          </div>
          <div>
            <span>Finish in store carts / pages</span>
            <strong>{money(totals.carts)}</strong>
          </div>
        </div>
        {run.payment.status === "held" && (
          <p className="held-caption">
            <ShieldCheck size={14} />
            Held {money(run.totals.held_usd)} · selected capture{" "}
            {money(totals.auto)}
          </p>
        )}
        <details className="checkout-details">
          <summary>
            Payment & checkout details <ChevronDown size={14} />
          </summary>
          <p className="checkout-explanation">
            {totals.auto > 0
              ? `Approving ${simulation ? "simulates ordering" : "orders"} the selected automatic-purchase items. `
              : ""}
            Other items open store carts or product pages for you to finish
            checkout.
          </p>
          {run.payment.status === "held" && (
            <div className="hold-note">
              <ShieldCheck size={16} />
              <p>
                {simulation ? "Demo" : "Temporary"} hold:{" "}
                <strong>{money(run.totals.held_usd)}</strong>.<br />
                Only the approved automatic-purchase amount is captured.
              </p>
            </div>
          )}
          <p className="tax-note">
            Item prices exclude tax and shipping. These are confirmed at
            checkout.
          </p>
        </details>
        {editable ? (
          <>
            <button
              className="primary-button full-width"
              disabled={
                busy || !selected.length || totals.total > run.budget_usd
              }
              onClick={onApprove}
            >
              {busy ? (
                <BeeLoader still={reduced} />
              ) : (
                <CheckCheck size={18} />
              )}
              {busy
                ? "Preparing your collection…"
                : simulation
                  ? "Approve demo collection"
                  : "Approve selected items"}
            </button>
            {!selected.length && (
              <p className="inline-hint">
                Select at least one piece to continue.
              </p>
            )}
            <button
              className="decline-button"
              onClick={onReject}
              disabled={busy}
            >
              Try a different direction
            </button>
          </>
        ) : (
          <span className="completed-label">
            <Check size={17} />
            This collection has been processed
          </span>
        )}
        <button className="text-button full-width" onClick={onAudit}>
          <Sparkles size={15} />
          See how the agents chose these
        </button>
        {simulation && (
          <p className="demo-disclosure">
            Demo only. No real orders or payments.
          </p>
        )}
      </aside>
      {editable && (
        <div className="mobile-review-bar">
          <div>
            <small>{totals.count} selected</small>
            <strong>{money(totals.total)}</strong>
          </div>
          <button
            className="primary-button"
            disabled={busy || !selected.length || totals.total > run.budget_usd}
            onClick={onApprove}
          >
            {busy ? (
              <BeeLoader still={reduced} />
            ) : (
              <CheckCheck size={17} />
            )}
            {simulation ? "Approve demo" : "Approve items"}
          </button>
        </div>
      )}
    </div>
  );
}
