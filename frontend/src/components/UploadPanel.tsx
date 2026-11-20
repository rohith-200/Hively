import type { FormEvent } from "react";
import {
  Check,
  CheckCircle2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  Wallet,
} from "lucide-react";
import type { Store } from "../lib/types";
import { STORE_NAMES } from "../lib/types";
import { StoreMark } from "./ui";
import { BeeLoader } from "./BeeScene";

export function UploadPanel({
  file,
  budget,
  stores,
  note,
  busy,
  error,
  demo,
  setBudget,
  setStores,
  setNote,
  onSubmit,
}: {
  file: File | null;
  budget: number;
  stores: Store[];
  note: string;
  busy: boolean;
  error: string;
  demo: boolean;
  setBudget: (n: number) => void;
  setStores: (s: Store[]) => void;
  setNote: (n: string) => void;
  onSubmit: (e: FormEvent) => void;
}) {
  return (
    <form className="surface upload-panel" onSubmit={onSubmit}>
      <div className="panel-heading">
        <span className="section-icon">
          <SlidersHorizontal size={22} />
        </span>
        <div>
          <h2>A little more you</h2>
          <p>Your priorities guide every pick.</p>
        </div>
      </div>
      <div className="budget-heading">
        <label htmlFor="room-budget">Your room budget</label>
        <div className="money-input">
          <span>$</span>
          <input
            id="room-budget"
            type="number"
            min={1}
            max={100000}
            step="0.01"
            value={Number.isNaN(budget) ? "" : budget}
            onChange={(e) => setBudget(e.target.valueAsNumber)}
            required
          />
        </div>
      </div>
      <input
        className="budget-slider"
        type="range"
        aria-label="Adjust room budget"
        min={50}
        max={2000}
        step={25}
        value={Math.max(50, Math.min(2000, budget || 50))}
        onChange={(e) => setBudget(Number(e.target.value))}
        style={
          {
            "--range-progress": `${((Math.max(50, Math.min(2000, budget || 50)) - 50) / 1950) * 100}%`,
          } as React.CSSProperties
        }
      />
      <div className="range-labels">
        <span>$50</span>
        <span>USD · before tax & shipping</span>
        <span>$2,000+</span>
      </div>
      <fieldset className="store-field">
        <legend>Where should we look?</legend>
        <div className="store-chips">
          {(["shopify", "amazon", "walmart"] as Store[]).map((store) => (
            <button
              key={store}
              type="button"
              aria-pressed={stores.includes(store)}
              className={`store-chip ${stores.includes(store) ? "selected" : ""}`}
              onClick={() =>
                setStores(
                  stores.includes(store)
                    ? stores.filter((s) => s !== store)
                    : [...stores, store],
                )
              }
            >
              <StoreMark store={store} />
              {STORE_NAMES[store]}
              {stores.includes(store) && <Check size={13} />}
            </button>
          ))}
        </div>
      </fieldset>
      <div className="style-note-field">
        <label htmlFor="style-note">
          Anything we should know? <span>Optional</span>
        </label>
        <textarea
          id="style-note"
          rows={3}
          maxLength={1000}
          placeholder="Keep the sofa, add warm lighting, avoid glossy finishes…"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <p>Your style, items to keep, or things to avoid.</p>
      </div>
      <div className="photo-ready">
        <CheckCircle2 size={16} />
        <span>
          {file
            ? "Room photo added. You’re ready to begin."
            : "Add a room photo to get started."}
        </span>
      </div>
      {error && (
        <p className="inline-error" role="alert">
          {error}
        </p>
      )}
      <button
        className="primary-button full-width"
        disabled={busy}
        type="submit"
      >
        {busy ? (
          <BeeLoader />
        ) : (
          <Sparkles size={18} />
        )}
        {busy ? "Getting your room ready…" : "Find my room’s finishing touches"}
      </button>
      <p className="safe-note">
        <ShieldCheck size={14} />
        You review every item before approving.
      </p>
      {demo && (
        <p className="demo-disclosure">
          Demo mode uses sample results. Live analysis will read your actual
          photo.
        </p>
      )}
    </form>
  );
}
