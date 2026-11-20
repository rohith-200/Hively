import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import {
  Camera,
  CheckCircle2,
  Expand,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import type { RoomProfile } from "../lib/types";
import { RoomProfileCard } from "./ui";
import { BeeLoader, BeeScene } from "./BeeScene";

export function RoomStage({
  error,
  photo,
  fileName,
  profile,
  working,
  reduced,
  demo,
  onPhoto,
  onRemove,
  onSamples,
  onEnlarge,
}: {
  error: string;
  photo: string;
  fileName: string;
  profile: RoomProfile | null;
  working: boolean;
  reduced: boolean;
  demo: boolean;
  onPhoto: (file?: File) => void;
  onRemove: () => void;
  onSamples: () => void;
  onEnlarge: () => void;
}) {
  const upload = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const stage = useRef<HTMLElement>(null);
  useEffect(() => {
    if (error)
      stage.current?.scrollIntoView({
        behavior: reduced ? "instant" : "smooth",
        block: "center",
      });
  }, [error, reduced]);
  return (
    <div className="stage-column">
      <input
        ref={upload}
        className="visually-hidden"
        type="file"
        accept="image/jpeg,image/png"
        aria-label="Upload a room photo"
        disabled={working}
        onChange={(e) => {
          onPhoto(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <input
        ref={camera}
        className="visually-hidden"
        type="file"
        accept="image/jpeg,image/png"
        capture="environment"
        aria-label="Take a room photo"
        disabled={working}
        onChange={(e) => {
          onPhoto(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
      <section
        ref={stage}
        className={`photo-stage ${drag && !working ? "dragging" : ""} ${photo ? "has-photo" : ""}`}
        aria-label="Your room photo"
        onDragOver={(e) => {
          e.preventDefault();
          if (!working) setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!working) onPhoto(e.dataTransfer.files[0]);
        }}
      >
        <div className="photo-stage-header">
          <span className="eyebrow">
            {photo ? "YOUR STARTING POINT" : "EVERY SPACE HAS A STARTING POINT"}
          </span>
          {photo && (
            <div className="photo-tools">
              <button
                className="icon-button"
                aria-label="Enlarge room photo"
                onClick={onEnlarge}
              >
                <Expand size={17} />
              </button>
              {!working && (
                <button
                  className="icon-button"
                  aria-label="Remove room photo"
                  onClick={onRemove}
                >
                  <X size={17} />
                </button>
              )}
            </div>
          )}
        </div>
        <AnimatePresence mode="wait" initial={false}>
          {photo ? (
            <motion.div
              key={photo}
              className="uploaded-room"
              initial={{ opacity: 0, scale: reduced ? 1 : 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
            >
              <img src={photo} alt="Your original uploaded room photo" />
              {working && !reduced && <div className="photo-scan" />}
              <div className="photo-caption">
                <span>
                  <CheckCircle2 size={14} />
                  Your original photo
                </span>
                {working && (
                  <span>
                    <BeeLoader still={reduced} />
                    Your hive at work
                  </span>
                )}
              </div>
            </motion.div>
          ) : (
            <motion.div
              key="empty"
              className="upload-empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <BeeScene reduced={reduced} />
              <h2>A little hive. A home that feels like you.</h2>
              <p>
                Drop in a photo of your space.
                <br />
                We’ll help you find what belongs.
              </p>
              <div className="upload-actions">
                <button
                  type="button"
                  className="primary-button"
                  onClick={() => upload.current?.click()}
                >
                  <Upload size={17} />
                  Upload a room photo
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => camera.current?.click()}
                >
                  <Camera size={17} />
                  Use camera
                </button>
              </div>
              <small>
                Living room, kitchen, bedroom, or another indoor space.
                <br />
                JPG or PNG · Up to 8 MB
              </small>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="photo-stage-footer">
          {photo ? (
            <>
              <span className="file-name">{fileName || "Your room photo"}</span>
              {!working && (
                <button
                  className="text-button"
                  onClick={() => upload.current?.click()}
                >
                  <Upload size={14} />
                  Change photo
                </button>
              )}
            </>
          ) : (
            <>
              <span>No perfect photo needed. A clear view is enough.</span>
              <button className="text-button" onClick={onSamples}>
                <Sparkles size={14} />
                Try a sample
              </button>
            </>
          )}
        </div>
      </section>
      {error && (
        <p className="inline-error photo-error" role="alert">
          {error}
        </p>
      )}
      {profile ? (
        <RoomProfileCard profile={profile} demo={demo} />
      ) : (
        <div className="photo-guidance">
          <CheckCircle2 size={17} />
          <p>
            Show the main furniture and a little of the surrounding room. Your
            uploaded photo stays at the center of the experience.
          </p>
        </div>
      )}
    </div>
  );
}
