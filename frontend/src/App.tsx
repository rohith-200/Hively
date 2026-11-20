import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  AnimatePresence,
  motion,
  MotionConfig,
  useReducedMotion,
} from "motion/react";
import {
  Activity,
  AlertCircle,
  Aperture,
  ArrowUpRight,
  Camera,
  Check,
  CheckCheck,
  ChevronDown,
  CircleHelp,
  Eye,
  FileCheck2,
  Hexagon,
  Home,
  Leaf,
  Plus,
  RefreshCw,
  ShieldCheck,
  ShoppingBag,
  Sparkles,
  X,
} from "lucide-react";
import { Dialog } from "./components/Dialog";
import { Brand, StoreMark } from "./components/ui";
import { RoomStage } from "./components/RoomStage";
import { UploadPanel } from "./components/UploadPanel";
import { AgentWorkspace } from "./components/AgentWorkspace";
import { ReviewCollection } from "./components/ReviewCollection";
import { RunResults } from "./components/RunResults";
import { AuditTrail, EventDetails } from "./components/AuditTrail";
import { BeeLoader } from "./components/BeeScene";
import {
  api,
  ApiError,
  assetUrl,
  DEMO_MODE,
  friendlyErrors,
  subscribeToRun,
} from "./lib/api";
import {
  money,
  selectedTotals,
  STORE_NAMES,
  validatePhoto,
  type AuditEvent,
  type Health,
  type MerchantResult,
  type Run,
  type RunItem,
  type Store,
} from "./lib/types";
import { AGENTS, executionLabel, roomLabel } from "./lib/workflow";

type Screen = "upload" | "working" | "review" | "results";
type Popup =
  | "samples"
  | "help"
  | "audit"
  | "profile"
  | "reject"
  | "new"
  | "photo"
  | "connections"
  | null;
const screens = [
  { key: "upload", name: "Your room", icon: Camera },
  { key: "working", name: "Agents at work", icon: Sparkles },
  { key: "review", name: "Your collection", icon: ShoppingBag },
  { key: "results", name: "Next steps", icon: CheckCheck },
] as const;
const samples = [
  {
    kind: "living-room",
    name: "Living room",
    style: "Warm Scandinavian",
    src: "/samples/living-room.svg",
  },
  {
    kind: "kitchen",
    name: "Kitchen",
    style: "Mid-century warmth",
    src: "/samples/kitchen.svg",
  },
  {
    kind: "bedroom",
    name: "Bedroom",
    style: "Soft contemporary",
    src: "/samples/bedroom.svg",
  },
] as const;
function readPreference(key: string, fallback: string) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}
function errorText(error: unknown) {
  return error instanceof ApiError
    ? error.message || friendlyErrors[error.code] || friendlyErrors.INTERNAL
    : error instanceof Error
      ? error.message
      : friendlyErrors.INTERNAL;
}

export default function App() {
  const [screen, setScreen] = useState<Screen>("upload");
  const [run, setRun] = useState<Run | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [photo, setPhoto] = useState("");
  const [budget, setBudget] = useState(400);
  const [stores, setStores] = useState<Store[]>([
    "shopify",
    "amazon",
    "walmart",
  ]);
  const [note, setNote] = useState("");
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [approving, setApproving] = useState(false);
  const [fallback, setFallback] = useState(false);
  const [error, setError] = useState("");
  const [photoError, setPhotoError] = useState("");
  const [toast, setToast] = useState("");
  const [popup, setPopup] = useState<Popup>(null);
  const [detail, setDetail] = useState<RunItem | null>(null);
  const [eventDetail, setEventDetail] = useState<AuditEvent | null>(null);
  const [cart, setCart] = useState<MerchantResult | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthBusy, setHealthBusy] = useState(false);
  const [userName, setUserName] = useState(() =>
    readPreference("hivly.displayName", "Naman"),
  );
  const [userId, setUserId] = useState(() =>
    readPreference("hivly.userId", "naman"),
  );
  const [motionOff, setMotionOff] = useState(
    () => readPreference("hivly.reduceMotion", "false") === "true",
  );
  const systemReduced = useReducedMotion();
  const reduced = !!systemReduced || motionOff;
  const [rejectReason, setRejectReason] = useState(
    "I would like a different style direction.",
  );
  const initializedSelection = useRef("");
  const mainTop = useRef<HTMLDivElement>(null);
  const previousScreen = useRef(screen);
  const simulation = DEMO_MODE || run?.payment.mode === "mock";
  const current = screens.findIndex((s) => s.key === screen);
  const dismiss = useCallback(() => {
    setPopup(null);
    setDetail(null);
    setEventDetail(null);
    setCart(null);
  }, []);

  const refreshHealth = useCallback(async () => {
    setHealthBusy(true);
    try {
      setHealth(await api.health());
    } catch {
      setHealth(null);
    } finally {
      setHealthBusy(false);
    }
  }, []);
  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);
  useEffect(() => {
    if (!file) {
      setPhoto("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPhoto(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4000);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    try {
      localStorage.setItem("hivly.reduceMotion", String(motionOff));
    } catch {
      /* private browsing */
    }
  }, [motionOff]);
  useEffect(() => {
    if (previousScreen.current !== screen) {
      previousScreen.current = screen;
      mainTop.current?.scrollIntoView({
        behavior: reduced ? "instant" : "smooth",
        block: "start",
      });
    }
  }, [screen, reduced]);

  const appendEvent = useCallback(
    (event: AuditEvent) =>
      setEvents((previous) =>
        previous.some((e) => e.seq === event.seq)
          ? previous
          : [...previous, event].sort((a, b) => a.seq - b.seq),
      ),
    [],
  );
  const applyRun = useCallback((value: Run) => {
    setRun(value);
    if (value.state === "awaiting_approval") {
      if (initializedSelection.current !== value.id) {
        initializedSelection.current = value.id;
        setSelected(value.items.filter((i) => i.selected).map((i) => i.id));
      }
      setScreen("review");
    } else if (
      ["completed", "partial", "rejected", "failed"].includes(value.state)
    )
      setScreen("results");
    else setScreen("working");
  }, []);
  useEffect(() => {
    if (
      !run ||
      approving ||
      !["created", "analyzing", "executing"].includes(run.state)
    )
      return;
    return subscribeToRun(run.id, {
      onStep: (event) => {
        appendEvent(event);
        setError("");
      },
      onRun: (value) => {
        applyRun(value);
        setError("");
      },
      onProfile: (profile) =>
        setRun((previous) =>
          previous ? { ...previous, room: profile } : previous,
        ),
      onError: (e) => setError(errorText(e)),
      onFallback: () => setFallback(true),
    });
  }, [run?.id, run?.state, approving, appendEvent, applyRun]);
  useEffect(() => {
    if (!approving || !run) return;
    const controller = new AbortController();
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      const [status, trail] = await Promise.allSettled([
        api.getRun(run.id, controller.signal),
        api.audit(run.id, controller.signal),
      ]);
      if (stopped) return;
      if (trail.status === "fulfilled") trail.value.events.forEach(appendEvent);
      if (status.status === "fulfilled") applyRun(status.value);
      timer = setTimeout(poll, 1000);
    };
    void poll();
    return () => {
      stopped = true;
      controller.abort();
      clearTimeout(timer);
    };
  }, [approving, run?.id, appendEvent, applyRun]);

  const choosePhoto = async (candidate?: File) => {
    if (!candidate || busy) return;
    const issue = validatePhoto(candidate);
    if (issue) {
      setPhotoError(issue);
      return;
    }
    setBusy(true);
    setPhotoError("");
    setError("");
    const temporary = URL.createObjectURL(candidate);
    try {
      const image = new Image();
      image.src = temporary;
      await image.decode();
      if (!image.naturalWidth || !image.naturalHeight)
        throw new Error("empty image");
      setFile(candidate);
    } catch {
      setPhotoError(
        "We could not open this image. Please choose a valid JPG or PNG room photo.",
      );
    } finally {
      URL.revokeObjectURL(temporary);
      setBusy(false);
    }
  };
  const useSample = async (sample: (typeof samples)[number]) => {
    setPhotoError("");
    setBusy(true);
    setError("");
    try {
      const image = new Image();
      image.src = sample.src;
      await image.decode();
      const canvas = document.createElement("canvas");
      canvas.width = 1200;
      canvas.height = 850;
      const context = canvas.getContext("2d");
      if (!context) throw new Error("Please upload a photo instead.");
      context.drawImage(image, 0, 0, 1200, 850);
      const blob = await new Promise<Blob>((resolve, reject) =>
        canvas.toBlob(
          (b) =>
            b
              ? resolve(b)
              : reject(new Error("The sample could not be prepared.")),
          "image/png",
        ),
      );
      setFile(
        new File([blob], `hivly-sample-${sample.kind}.png`, {
          type: "image/png",
        }),
      );
      setPopup(null);
      setToast(`${sample.name} sample added.`);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const startRun = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    if (!file) {
      setPhotoError("Add a room photo or try one of the samples first.");
      return;
    }
    if (!Number.isFinite(budget) || budget < 1 || budget > 100000) {
      setError("Choose a budget between $1 and $100,000.");
      return;
    }
    if (!stores.length) {
      setError("Choose at least one store.");
      return;
    }
    if (!userId.trim()) {
      setPopup("profile");
      setError(
        "Add your user ID so the memory agent can find your preferences.",
      );
      return;
    }
    setBusy(true);
    try {
      const created = await api.createRun({
        photo: file,
        user_id: userId.trim(),
        budget_usd: budget,
        stores,
        note,
      });
      setEvents([]);
      setSelected([]);
      initializedSelection.current = "";
      setFallback(false);
      const initial = await api.getRun(created.run_id).catch(
        () =>
          ({
            id: created.run_id,
            user_id: userId,
            state: created.state,
            created_at: new Date().toISOString(),
            budget_usd: budget,
            room: null,
            items: [],
            skipped: [],
            totals: {
              items_usd: 0,
              auto_buy_usd: 0,
              cart_link_usd: 0,
              held_usd: 0,
              captured_usd: 0,
            },
            payment: {
              mode: DEMO_MODE ? "mock" : "none",
              payment_intent_id: null,
              status: "none",
            },
            merchant_results: [],
            error: null,
          }) as Run,
      );
      applyRun(initial);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const refreshStatus = async () => {
    if (!run) return;
    setBusy(true);
    try {
      applyRun(await api.getRun(run.id));
      const audit = await api.audit(run.id);
      audit.events.forEach(appendEvent);
      setError("");
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const approve = async () => {
    if (
      !run ||
      busy ||
      approving ||
      !selected.length ||
      selectedTotals(run.items, selected).total > run.budget_usd
    )
      return;
    setBusy(true);
    setApproving(true);
    setError("");
    try {
      const result = await api.approve(run.id, selected);
      applyRun(result);
      const audit = await api.audit(run.id).catch(() => null);
      audit?.events.forEach(appendEvent);
    } catch (e) {
      setError(errorText(e));
      try {
        applyRun(await api.getRun(run.id));
      } catch {
        setError(
          "Approval status could not be confirmed. Check the room status before submitting again.",
        );
      }
    } finally {
      setBusy(false);
      setApproving(false);
    }
  };
  const reset = () => {
    setPhotoError("");
    setRun(null);
    setEvents([]);
    setSelected([]);
    setFile(null);
    setError("");
    setFallback(false);
    setScreen("upload");
    dismiss();
  };
  const newRoom = () => {
    if (run && ["created", "analyzing", "executing"].includes(run.state)) {
      setToast("Let the current step finish before starting another room.");
      return;
    }
    if (run?.state === "awaiting_approval") {
      setPopup("new");
      return;
    }
    reset();
  };
  const reject = async (restart = false) => {
    if (!run || busy) return;
    setBusy(true);
    setError("");
    try {
      const result = await api.reject(
        run.id,
        restart ? "Starting a new room" : rejectReason,
      );
      if (restart) reset();
      else {
        applyRun(result);
        dismiss();
        const audit = await api.audit(run.id).catch(() => null);
        audit?.events.forEach(appendEvent);
      }
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };
  const showReview = () => {
    if (
      run &&
      ["awaiting_approval", "completed", "partial"].includes(run.state)
    )
      setScreen("review");
  };
  const saveProfile = () => {
    if (!userId.trim()) {
      setError("Please enter a user ID.");
      return;
    }
    try {
      localStorage.setItem("hivly.displayName", userName.trim() || "Naman");
      localStorage.setItem("hivly.userId", userId.trim());
    } catch {
      /* local storage optional */
    }
    setUserName(userName.trim() || "Naman");
    setError("");
    dismiss();
    setToast("Your profile is ready.");
  };
  const heading =
    screen === "upload" ? (
      <>
        Your room. <em>A hive of possibilities.</em>
      </>
    ) : screen === "working" ? (
      <>
        Thoughtful choices, <em>taking shape.</em>
      </>
    ) : screen === "review" ? (
      <>
        The right pieces. <em>Your final say.</em>
      </>
    ) : run?.state === "rejected" ? (
      <>
        A fresh start. <em>Your next direction.</em>
      </>
    ) : run?.state === "failed" ? (
      <>
        A small snag. <em>Let’s make it right.</em>
      </>
    ) : run?.state === "partial" ? (
      <>
        Some finds. <em>A few next steps.</em>
      </>
    ) : (
      <>
        Good things, <em>brought together.</em>
      </>
    );

  return (
    <MotionConfig
      reducedMotion={reduced ? "always" : "user"}
      transition={{ type: "spring", stiffness: 320, damping: 32 }}
    >
      <div className="app-shell" data-motion={reduced ? "reduced" : "full"}>
        <a href="#main-content" className="skip-link">
          Skip to workspace
        </a>
        <aside className="sidebar">
          <Brand />
          <button className="new-room-button" onClick={newRoom}>
            <Plus size={18} />
            <span>New room</span>
          </button>
          <span className="nav-label">YOUR PERSONAL HIVE</span>
          <nav aria-label="Workspace">
            <button
              className={`nav-item ${screen === "upload" || screen === "working" ? "active" : ""}`}
              onClick={newRoom}
            >
              <Home size={19} />
              <span>Your room</span>
            </button>
            <button
              className={`nav-item ${screen === "review" || screen === "results" ? "active" : ""}`}
              disabled={!run || ["created", "analyzing"].includes(run.state)}
              onClick={() =>
                run &&
                ["completed", "partial", "rejected", "failed"].includes(
                  run.state,
                )
                  ? setScreen("results")
                  : showReview()
              }
            >
              <ShoppingBag size={19} />
              <span>Your collection</span>
            </button>
            <button className="nav-item" onClick={() => setPopup("audit")}>
              <Activity size={19} />
              <span>Activity trail</span>
            </button>
          </nav>
          <div className="sidebar-message">
            <Hexagon size={34} strokeWidth={1} />
            <h3>
              Small team.
              <br />
              Sweet possibilities.
            </h3>
            <p>
              Thoughtful agents.
              <br />Working together, for you.
            </p>
          </div>
          <div className="sidebar-bottom">
            <button className="nav-item" onClick={() => setPopup("help")}>
              <CircleHelp size={19} />
              <span>A little help</span>
            </button>
            <button
              className="profile-button"
              onClick={() => setPopup("profile")}
            >
              <span className="avatar">
                {(userName || "N")[0].toUpperCase()}
              </span>
              <span>
                <strong>{userName || "Naman"}</strong>
                <small>Your personal space</small>
              </span>
              <ChevronDown size={14} />
            </button>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="mobile-brand">
              <Brand />
            </div>
            <div className="breadcrumb">
              My workspace <span>/</span>
              <strong>
                {run ? roomLabel(run.room?.room_type) : "A fresh start"}
              </strong>
            </div>
            <div className="top-actions">
              <button
                className="connection-pill"
                onClick={() => setPopup("connections")}
              >
                <span className={`status-dot ${health?.ok ? "" : "offline"}`} />
                {DEMO_MODE
                  ? "Demo workspace"
                  : health?.ok
                    ? Object.values(health.modes).includes("mock")
                      ? "Mixed services"
                      : "Connected"
                    : "Backend offline"}
                <ChevronDown size={12} />
              </button>
              <button
                className="icon-button"
                aria-label={
                  motionOff ? "Enable animations" : "Reduce animations"
                }
                onClick={() => setMotionOff(!motionOff)}
              >
                <Aperture size={19} />
              </button>
              <button
                className="top-avatar"
                aria-label="Open profile"
                onClick={() => setPopup("profile")}
              >
                {(userName || "N")[0].toUpperCase()}
              </button>
            </div>
          </header>
          <main id="main-content">
            <div ref={mainTop} className="main-anchor" />
            <div className="page-heading">
              <div>
                <span className="eyebrow">
                  <Hexagon size={13} /> YOUR SPACE. OUR COLLECTIVE INTELLIGENCE.
                </span>
                <h1>{heading}</h1>
                <p>
                  {screen === "upload"
                    ? "One room photo. Thoughtful finds. A space that’s yours."
                    : screen === "working"
                      ? "Follow the decisions behind your collection, as they happen."
                      : screen === "review"
                        ? "Chosen across your stores, checked against your budget, and ready to review."
                        : run?.state === "rejected"
                          ? "Your collection was declined. You can try another direction."
                          : run?.state === "failed"
                            ? "Review what happened, then try again with another room photo."
                            : "Orders, checkout links, and payment status, all in one place."}
                </p>
              </div>
              <button
                className="text-button heading-help"
                onClick={() => setPopup("help")}
              >
                <CircleHelp size={15} />
                How it works
              </button>
            </div>
            <nav className="stepper" aria-label="Room styling progress">
              {screens.map(({ key, name, icon: Icon }, i) => (
                <button
                  key={key}
                  className={`step ${screen === key ? "current" : ""} ${current > i ? "done" : ""}`}
                  aria-current={screen === key ? "step" : undefined}
                  disabled={
                    key !== "upload" &&
                    key !== screen &&
                    !(
                      key === "review" &&
                      run &&
                      ["awaiting_approval", "completed", "partial"].includes(
                        run.state,
                      )
                    ) &&
                    !(key === "working" && !!events.length) &&
                    !(
                      key === "results" &&
                      run &&
                      ["completed", "partial", "rejected", "failed"].includes(
                        run.state,
                      )
                    )
                  }
                  onClick={() =>
                    key === "upload"
                      ? newRoom()
                      : key === "working"
                        ? setPopup("audit")
                        : key === "review"
                          ? showReview()
                          : setScreen("results")
                  }
                >
                  <span className="step-icon">
                    {current > i ? <Check size={15} /> : <Icon size={16} />}
                  </span>
                  <span>{name}</span>
                  <i />
                </button>
              ))}
            </nav>
            {error && screen !== "upload" && !popup && (
              <div className="error-banner" role="alert">
                <AlertCircle size={18} />
                <p>{error}</p>
                <button
                  className="text-button"
                  onClick={refreshStatus}
                  disabled={busy}
                >
                  <RefreshCw size={15} />
                  Check status
                </button>
                <button
                  className="icon-button"
                  aria-label="Dismiss error"
                  onClick={() => setError("")}
                >
                  <X size={16} />
                </button>
              </div>
            )}
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={screen}
                initial={{ opacity: 0, y: reduced ? 0 : 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: reduced ? 0 : -6 }}
                transition={{
                  type: "tween",
                  duration: reduced ? 0 : 0.2,
                  ease: [0.22, 1, 0.36, 1],
                }}
              >
                {(screen === "upload" || screen === "working") && (
                  <div className="workspace-grid">
                    <RoomStage
                      error={photoError}
                      photo={
                        photo ||
                        (run?.room?.photo_url
                          ? assetUrl(run.room.photo_url)
                          : "")
                      }
                      fileName={file?.name || ""}
                      profile={run?.room || null}
                      working={screen === "working"}
                      reduced={reduced}
                      demo={simulation}
                      onPhoto={choosePhoto}
                      onRemove={() => setFile(null)}
                      onSamples={() => setPopup("samples")}
                      onEnlarge={() => setPopup("photo")}
                    />
                    {screen === "upload" ? (
                      <UploadPanel
                        file={file}
                        budget={budget}
                        stores={stores}
                        note={note}
                        busy={busy}
                        error={error}
                        demo={DEMO_MODE}
                        setBudget={setBudget}
                        setStores={setStores}
                        setNote={setNote}
                        onSubmit={startRun}
                      />
                    ) : (
                      run && (
                        <AgentWorkspace
                          run={run}
                          events={events}
                          fallback={fallback}
                          reduced={reduced}
                          onEvent={setEventDetail}
                          onAudit={() => setPopup("audit")}
                        />
                      )
                    )}
                  </div>
                )}
                {screen === "review" && run && (
                  <ReviewCollection
                    run={run}
                    photo={photo || assetUrl(run.room?.photo_url)}
                    selected={selected}
                    busy={busy}
                    simulation={simulation}
                    reduced={reduced}
                    onToggle={(id) =>
                      setSelected((prev) =>
                        prev.includes(id)
                          ? prev.filter((i) => i !== id)
                          : [...prev, id],
                      )
                    }
                    onDetail={setDetail}
                    onApprove={approve}
                    onReject={() => setPopup("reject")}
                    onAudit={() => setPopup("audit")}
                    onNewRoom={newRoom}
                  />
                )}
                {screen === "results" && run && (
                  <RunResults
                    run={run}
                    events={events}
                    simulation={simulation}
                    onCart={setCart}
                    onAudit={() => setPopup("audit")}
                    onNewRoom={newRoom}
                  />
                )}
              </motion.div>
            </AnimatePresence>
            {screen === "upload" && (
              <div className="trust-strip">
                <span>
                  <Eye size={17} />
                  Your room leads the way
                </span>
                <span>
                  <Leaf size={17} />
                  Your budget stays in focus
                </span>
                <span>
                  <ShieldCheck size={17} />
                  Every purchase needs your approval
                </span>
              </div>
            )}
            <footer className="page-footer">
              <span>Thoughtful by design. Personal by nature.</span>
              <span>HIVLY{DEMO_MODE ? " · INTERACTIVE DEMO" : ""}</span>
            </footer>
          </main>
        </div>
        <AnimatePresence>
          {toast && (
            <motion.div
              className="toast"
              role="status"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 10 }}
            >
              <Check size={17} />
              {toast}
              <button
                className="icon-button"
                aria-label="Dismiss notification"
                onClick={() => setToast("")}
              >
                <X size={15} />
              </button>
            </motion.div>
          )}
          {popup === "samples" && (
            <Dialog title="A little inspiration to try" wide onClose={dismiss}>
              <p className="modal-description">
                Choose an illustrated sample to explore the full workflow. In
                live mode, your own photo determines the room profile.
              </p>
              <div className="sample-grid">
                {samples.map((sample) => (
                  <button
                    key={sample.kind}
                    className="sample-card"
                    onClick={() => useSample(sample)}
                    disabled={busy}
                  >
                    <img
                      src={sample.src}
                      alt={`${sample.name} sample illustration`}
                    />
                    <strong>{sample.name}</strong>
                    <span>{sample.style}</span>
                  </button>
                ))}
              </div>
              {busy && (
                <p className="safe-note">
                  <BeeLoader still={reduced} />
                  Preparing your sample
                </p>
              )}
              {error && (
                <p className="inline-error" role="alert">
                  {error}
                </p>
              )}
            </Dialog>
          )}
          {popup === "photo" && (
            <Dialog title="Your original room photo" wide onClose={dismiss}>
              <img
                className="enlarged-photo"
                src={photo || assetUrl(run?.room?.photo_url)}
                alt="Your original room photo, enlarged"
              />
              <p className="photo-modal-note">
                This is the photo you supplied. Hivly recommends products; it
                does not generate a renovated room image.
              </p>
            </Dialog>
          )}
          {popup === "help" && (
            <Dialog title="A little help from Hivly" onClose={dismiss}>
              <div className="help-steps">
                {[
                  {
                    icon: Camera,
                    title: "Start with any room",
                    text: "Add a clear room photo, your budget, stores, and optional style notes.",
                  },
                  {
                    icon: Sparkles,
                    title: "Watch the styling team work",
                    text: "The reader understands the space. Memory recalls your taste. The Stylist searches, the Curator chooses, and the Critic checks.",
                  },
                  {
                    icon: ShoppingBag,
                    title: "Make the collection yours",
                    text: "Review the products, see why each belongs, and remove anything you do not want. Totals update immediately.",
                  },
                  {
                    icon: ShieldCheck,
                    title: "Approve once, then finish checkout",
                    text: "Automatic-purchase items are ordered on approval. Other items open store carts or product pages. Every action is recorded in the activity trail.",
                  },
                ].map(({ icon: Icon, title, text }) => (
                  <div key={title}>
                    <span className="section-icon">
                      <Icon size={21} />
                    </span>
                    <div>
                      <h3>{title}</h3>
                      <p>{text}</p>
                    </div>
                  </div>
                ))}
              </div>
              {DEMO_MODE && (
                <div className="info-note">
                  <Eye size={19} />
                  <p>
                    This workspace currently runs sample analysis and simulated
                    commerce. Random uploads are accepted, but photo-specific
                    recommendations require the team’s live backend.
                  </p>
                </div>
              )}
            </Dialog>
          )}
          {popup === "connections" && (
            <Dialog title="Behind your styling team" onClose={dismiss}>
              <p className="modal-description">
                Service modes are reported by the backend. A mock service uses
                sample data.
              </p>
              <div className="connection-list">
                {[
                  {
                    key: "vision",
                    name: "Room reader",
                    service: "Claude vision",
                  },
                  {
                    key: "llm",
                    name: "Stylist, Curator & Critic",
                    service: "Arcee",
                  },
                  {
                    key: "db",
                    name: "Catalog & audit",
                    service: "SingleStore",
                  },
                  { key: "memory", name: "Taste memory", service: "Cognee" },
                  {
                    key: "analytics",
                    name: "Agent analytics",
                    service: "Amplitude",
                  },
                  {
                    key: "payments",
                    name: "Studio payments",
                    service: "Stripe",
                  },
                ].map((s) => (
                  <div key={s.key}>
                    <span>
                      <strong>{s.name}</strong>
                      <small>{s.service}</small>
                    </span>
                    <span
                      className={`service-mode ${health?.modes[s.key] === "mock" ? "mock" : ""}`}
                    >
                      {health?.modes[s.key] || "Unavailable"}
                    </span>
                  </div>
                ))}
              </div>
              <button
                className="secondary-button full-width"
                onClick={refreshHealth}
                disabled={healthBusy}
              >
                {healthBusy ? <BeeLoader still={reduced} /> : <RefreshCw size={16} />}
                Refresh connection status
              </button>
            </Dialog>
          )}
          {popup === "profile" && (
            <Dialog title="Your personal space" onClose={dismiss}>
              <label className="modal-label" htmlFor="display-name">
                Your name
              </label>
              <input
                id="display-name"
                className="modal-input"
                value={userName}
                onChange={(e) => setUserName(e.target.value)}
                maxLength={50}
              />
              <label className="modal-label" htmlFor="user-id">
                User ID for taste memory
              </label>
              <input
                id="user-id"
                className="modal-input"
                value={userId}
                onChange={(e) => setUserId(e.target.value)}
                maxLength={80}
              />
              <p className="field-help">
                Use the same ID for every room. Your team’s seeded demo user can
                be entered here.
              </p>
              <label className="motion-setting">
                <span>
                  <strong>Calmer transitions</strong>
                  <small>Reduce interface motion</small>
                </span>
                <input
                  type="checkbox"
                  checked={reduced}
                  disabled={!!systemReduced}
                  onChange={(e) => setMotionOff(e.target.checked)}
                />
              </label>
              {error && (
                <p role="alert" className="inline-error">
                  {error}
                </p>
              )}
              <button
                className="primary-button full-width"
                onClick={saveProfile}
              >
                Save my profile
              </button>
            </Dialog>
          )}
          {popup === "audit" && (
            <Dialog title="Every little step" drawer onClose={dismiss}>
              <AuditTrail run={run} events={events} demo={simulation} />
            </Dialog>
          )}
          {(popup === "reject" || popup === "new") && (
            <Dialog
              title={
                popup === "new"
                  ? "Make room for a fresh start?"
                  : "Let’s find a better fit"
              }
              onClose={dismiss}
            >
              <p className="modal-description">
                {popup === "new"
                  ? "Starting again declines the current collection and asks the backend to release its payment hold."
                  : "Your space should feel right to you. Declining this collection asks the backend to release its payment hold."}
              </p>
              {popup === "reject" && (
                <>
                  <label className="modal-label" htmlFor="reject-reason">
                    What would you change?
                  </label>
                  <textarea
                    id="reject-reason"
                    className="modal-input"
                    rows={3}
                    value={rejectReason}
                    maxLength={500}
                    onChange={(e) => setRejectReason(e.target.value)}
                  />
                </>
              )}
              {error && (
                <p className="inline-error" role="alert">
                  {error}
                </p>
              )}
              <div className="dialog-actions">
                <button
                  className="secondary-button"
                  onClick={dismiss}
                  disabled={busy}
                >
                  Keep reviewing
                </button>
                <button
                  className="primary-button"
                  onClick={() => reject(popup === "new")}
                  disabled={busy}
                >
                  {busy ? <BeeLoader still={reduced} /> : null}
                  {popup === "new" ? "Start fresh" : "Decline collection"}
                </button>
              </div>
            </Dialog>
          )}
          {detail && (
            <Dialog title="Why it belongs" onClose={dismiss}>
              <img
                className="detail-image"
                src={assetUrl(detail.product.image_url)}
                alt={detail.product.name}
              />
              <div className="detail-title">
                <h3>{detail.product.name}</h3>
                <strong>{money(detail.product.price_usd)}</strong>
              </div>
              <span className="execution-tag">
                {executionLabel(detail.execution_mode)}
              </span>
              <p className="modal-description">{detail.reason}</p>
              {detail.critic_note && (
                <div className="info-note">
                  <ShieldCheck size={18} />
                  <p>{detail.critic_note}</p>
                </div>
              )}
              <button className="primary-button full-width" onClick={dismiss}>
                Back to the collection
              </button>
            </Dialog>
          )}
          {eventDetail && (
            <Dialog title="The thought behind the step" onClose={dismiss}>
              <EventDetails event={eventDetail} />
            </Dialog>
          )}
          {cart && run && (
            <Dialog
              title={`${STORE_NAMES[cart.store]} · demo cart`}
              onClose={dismiss}
            >
              <div className="info-note">
                <ShoppingBag size={19} />
                <p>
                  This preview shows the store handoff. These sample products do
                  not create a real cart.
                </p>
              </div>
              <div className="demo-cart-items">
                {run.items
                  .filter((i) => cart.item_ids.includes(i.id))
                  .map((item) => (
                    <div key={item.id}>
                      <img
                        src={assetUrl(item.product.image_url)}
                        alt={item.product.name}
                      />
                      <span>
                        <strong>{item.product.name}</strong>
                        <small>Quantity 1</small>
                      </span>
                      <b>{money(item.product.price_usd)}</b>
                    </div>
                  ))}
              </div>
              <div className="cart-total">
                <span>Item subtotal</span>
                <strong>{money(cart.amount_usd)}</strong>
              </div>
              <button className="primary-button full-width" onClick={dismiss}>
                Back to my results
              </button>
            </Dialog>
          )}
        </AnimatePresence>
      </div>
    </MotionConfig>
  );
}
