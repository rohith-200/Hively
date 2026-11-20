import { Hexagon, ShoppingBag, Asterisk, Leaf, Sparkles } from "lucide-react";
import type { RoomProfile, Store } from "../lib/types";
import { roomLabel } from "../lib/workflow";

export function Brand() {
  return (
    <div className="brand">
      <span className="brand-symbol">
        <Hexagon size={33} strokeWidth={1.5} />
        <b>h</b>
      </span>
      <span>
        hivly<span className="brand-dot">.</span>
      </span>
    </div>
  );
}
export function StoreMark({ store }: { store: Store }) {
  return (
    <span className={`store-mark ${store}`} aria-hidden="true">
      {store === "shopify" ? (
        <ShoppingBag size={17} />
      ) : store === "amazon" ? (
        <b>a</b>
      ) : (
        <Asterisk size={20} />
      )}
    </span>
  );
}
export function RoomProfileCard({
  profile,
  demo = false,
  compact = false,
}: {
  profile: RoomProfile;
  demo?: boolean;
  compact?: boolean;
}) {
  return (
    <div className={`room-profile ${compact ? "compact" : ""}`}>
      <div className="profile-title">
        <span className="eyebrow">
          {demo ? "SAMPLE ROOM PROFILE" : "WHAT YOUR PHOTO TELLS US"}
        </span>
        {profile.style_confidence > 0 && (
          <span className="confidence">
            <Sparkles size={13} />
            {Math.round(profile.style_confidence * 100)}% confidence
          </span>
        )}
      </div>
      <h3>
        {roomLabel(profile.room_type)} <span>· {profile.style}</span>
      </h3>
      {(!compact || (demo && profile.style_confidence === 0)) && (
        <p>{profile.evidence}</p>
      )}
      {!!profile.palette?.length && (
        <div className="room-palette">
          {profile.palette.map((c) => (
            <span key={c.name}>
              <i
                style={{
                  background: /^#[0-9a-f]{3,8}$/i.test(c.hex)
                    ? c.hex
                    : "#b4bd9f",
                }}
              />
              {c.name}
            </span>
          ))}
        </div>
      )}
      {!compact && !!profile.materials?.length && (
        <div className="materials">
          <Leaf size={14} />
          {profile.materials.join(" · ")}
        </div>
      )}
    </div>
  );
}
