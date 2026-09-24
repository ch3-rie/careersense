import { useEffect, useMemo, useRef, useState } from "react";
import { ProfilePhoto, initials } from "./AlumniProfileExtras";
import { MinusIcon, PlusIcon } from "./icons";
import { Alert, Dialog } from "./ui";
import { api } from "../lib/api";
import {
  PHOTO_ACCEPT,
  COVER_ASPECT,
  clampPan,
  clampPanFrame,
  coverFrame,
  coverVisible,
  cropFrameStyle,
  cropImageStyle,
  exportCroppedFrame,
  exportCroppedPhoto,
  initialCrop,
  initialCropFrame,
  loadOrientedImage,
  maxZoomFor,
  maxZoomForFrame,
  validatePhotoFile,
} from "../lib/profilePhoto";
import { friendlyError } from "../lib/userMessages";

function sameCrop(a, b) {
  if (!a || !b) return false;
  return a.zoom === b.zoom && Math.abs(a.sx - b.sx) < 0.5 && Math.abs(a.sy - b.sy) < 0.5;
}

export function ProfilePhotoControl({
  profile,
  src,
  size = "lg",
  compact = false,
  quiet = false,
  disabled,
  onFile,
  onInvalid,
  onRemoved,
}) {
  const inputRef = useRef(null);
  const hasPhoto = Boolean(src) || Boolean(profile?.has_photo);
  const label = hasPhoto ? "Change photo" : "Add profile photo";
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [removeError, setRemoveError] = useState("");
  const removingRef = useRef(false);
  const locked = disabled || removing;

  function openPicker() {
    if (locked) return;
    inputRef.current?.click();
  }

  function onChange(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const invalid = validatePhotoFile(file);
    if (invalid) {
      onInvalid?.(invalid);
      return;
    }
    onInvalid?.("");
    onFile?.(file);
  }

  async function removePhoto() {
    if (removingRef.current) return;
    removingRef.current = true;
    setRemoving(true);
    setRemoveError("");
    try {
      const payload = await api("/api/alumni/profile/photo", { method: "DELETE" });
      setConfirmRemove(false);
      onRemoved?.(payload);
    } catch (err) {
      setRemoveError(friendlyError(err, "We couldn't remove your profile photo. Please try again."));
    } finally {
      removingRef.current = false;
      setRemoving(false);
    }
  }

  return (
    <div className={`profile-photo-control ${compact ? "is-compact" : ""} ${quiet ? "is-quiet" : ""}`}>
      <button
        type="button"
        className="profile-photo-pick"
        onClick={openPicker}
        disabled={locked}
        aria-label={label}
      >
        <ProfilePhoto profile={profile} src={src} size={size} />
      </button>
      {!quiet ? (
        <div className="profile-photo-control-copy">
          <div className="profile-photo-actions">
            <button type="button" className="btn btn-outline btn-sm" onClick={openPicker} disabled={locked}>
              {label}
            </button>
            {hasPhoto ? (
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => {
                  setRemoveError("");
                  setConfirmRemove(true);
                }}
                disabled={locked}
              >
                Remove photo
              </button>
            ) : null}
          </div>
          <p className="muted photo-guidance">JPG, PNG, or WebP · Maximum 5 MB</p>
          <p className="muted photo-guidance">For best results, use a clear photo where your face is visible.</p>
        </div>
      ) : null}
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept={PHOTO_ACCEPT}
        disabled={locked}
        onChange={onChange}
      />
      {confirmRemove ? (
        <Dialog
          title="Remove profile photo?"
          description="Your alumni profile will show your initials instead. You can add a new photo later."
          confirmLabel={removing ? "Removing…" : "Remove photo"}
          danger
          busy={removing}
          onConfirm={removePhoto}
          onClose={() => {
            if (!removing) setConfirmRemove(false);
          }}
        >
          <Alert type="error">{removeError}</Alert>
        </Dialog>
      ) : null}
    </div>
  );
}

export function PhotoCropDialog({ file, onClose, onUploaded, onReplace, kind = "profile" }) {
  const isCover = kind === "cover";
  const replaceRef = useRef(null);
  const viewRef = useRef(null);
  const pointers = useRef(new Map());
  const pinch = useRef(null);
  const drag = useRef(null);
  const [cropSize, setCropSize] = useState(280);
  const [prepared, setPrepared] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [crop, setCrop] = useState({ zoom: 1, sx: 0, sy: 0 });
  const [origin, setOrigin] = useState(null);
  const [saving, setSaving] = useState(false);
  const [preparing, setPreparing] = useState(true);
  const [error, setError] = useState("");
  const [confirmDiscard, setConfirmDiscard] = useState(false);
  const [status, setStatus] = useState("Preparing photo…");

  const cropRef = useRef(crop);
  cropRef.current = crop;
  const preparedRef = useRef(prepared);
  preparedRef.current = prepared;

  const maxZoom = prepared
    ? (isCover ? maxZoomForFrame(prepared.width, prepared.height) : maxZoomFor(prepared.width, prepared.height))
    : 3;
  const dirty = origin ? !sameCrop(crop, origin) : false;

  useEffect(() => {
    let cancelled = false;
    let objectUrl = "";
    setPreparing(true);
    setError("");
    setStatus("Preparing photo…");
    loadOrientedImage(file)
      .then(async (loaded) => {
        const canvas = document.createElement("canvas");
        canvas.width = loaded.width;
        canvas.height = loaded.height;
        canvas.getContext("2d").drawImage(loaded.source, 0, 0);
        const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.92));
        if (cancelled) {
          loaded.source.close?.();
          return;
        }
        objectUrl = blob ? URL.createObjectURL(blob) : "";
        const start = isCover ? initialCropFrame(loaded.width, loaded.height) : initialCrop(loaded.width, loaded.height);
        setPrepared(loaded);
        setPreviewUrl(objectUrl);
        setCrop(start);
        setOrigin(start);
        setPreparing(false);
        setStatus(isCover ? "Adjust your cover photo." : "Adjust your profile photo.");
      })
      .catch((err) => {
        if (cancelled) return;
        setPreparing(false);
        setError(friendlyError(err, "We couldn't read this image. Please choose another photo."));
        setStatus("");
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [file, isCover]);

  useEffect(() => {
    const node = viewRef.current;
    if (!node) return undefined;
    const sync = () => setCropSize(Math.max(200, Math.round(node.clientWidth)));
    sync();
    const observer = new ResizeObserver(sync);
    observer.observe(node);
    return () => observer.disconnect();
  }, [prepared, preparing]);

  function frameHeight() {
    return isCover ? cropSize / COVER_ASPECT : cropSize;
  }

  function applyCrop(next) {
    const image = preparedRef.current;
    if (!image) return;
    const limit = isCover ? maxZoomForFrame(image.width, image.height) : maxZoomFor(image.width, image.height);
    const zoom = Math.min(limit, Math.max(1, next.zoom));
    const pan = isCover
      ? clampPanFrame(next.sx, next.sy, image.width, image.height, zoom)
      : clampPan(next.sx, next.sy, image.width, image.height, zoom);
    setCrop({ zoom, ...pan });
  }

  function zoomAround(nextZoom, focusX, focusY) {
    const image = preparedRef.current;
    const current = cropRef.current;
    if (!image) return;
    const limit = isCover ? maxZoomForFrame(image.width, image.height) : maxZoomFor(image.width, image.height);
    const zoom = Math.min(limit, Math.max(1, nextZoom));
    const currentFrame = isCover
      ? coverFrame(image.width, image.height, current.zoom)
      : { visibleW: coverVisible(image.width, image.height, current.zoom), visibleH: coverVisible(image.width, image.height, current.zoom) };
    const scale = cropSize / currentFrame.visibleW;
    const imageX = current.sx + focusX / scale;
    const imageY = current.sy + focusY / scale;
    const nextFrame = isCover
      ? coverFrame(image.width, image.height, zoom)
      : { visibleW: coverVisible(image.width, image.height, zoom), visibleH: coverVisible(image.width, image.height, zoom) };
    applyCrop({
      zoom,
      sx: imageX - (focusX / cropSize) * nextFrame.visibleW,
      sy: imageY - (focusY / frameHeight()) * nextFrame.visibleH,
    });
  }

  function resetCrop() {
    if (!origin) return;
    setCrop(origin);
    setError("");
  }

  function pickReplacement(event) {
    const next = event.target.files?.[0];
    event.target.value = "";
    if (!next || !onReplace) return;
    const invalid = validatePhotoFile(next);
    if (invalid) {
      setError(invalid);
      return;
    }
    setError("");
    onReplace(next);
  }

  function requestClose() {
    if (saving) return;
    if (dirty) setConfirmDiscard(true);
    else onClose();
  }

  async function savePhoto() {
    if (!prepared || saving) return;
    setSaving(true);
    setError("");
    setStatus("Saving…");
    try {
      const blob = isCover
        ? await exportCroppedFrame(prepared.source, prepared.width, prepared.height, crop)
        : await exportCroppedPhoto(prepared.source, prepared.width, prepared.height, crop);
      const payload = new FormData();
      payload.append(isCover ? "cover" : "photo", blob, isCover ? "cover.jpg" : "profile.jpg");
      const result = await api(isCover ? "/api/alumni/profile/cover" : "/api/alumni/profile/photo", { method: "POST", form: payload });
      onUploaded(result);
    } catch (err) {
      setError(friendlyError(err, isCover ? "We couldn't update your cover photo. Please try again." : "We couldn't update your profile photo. Please try again."));
      setStatus("");
    } finally {
      setSaving(false);
    }
  }

  function onPointerDown(event) {
    if (!prepared || saving) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 1) {
      drag.current = { x: event.clientX, y: event.clientY, sx: cropRef.current.sx, sy: cropRef.current.sy };
    } else if (pointers.current.size === 2) {
      const pts = [...pointers.current.values()];
      const dx = pts[0].x - pts[1].x;
      const dy = pts[0].y - pts[1].y;
      pinch.current = { distance: Math.hypot(dx, dy) || 1, zoom: cropRef.current.zoom };
      drag.current = null;
    }
  }

  function onPointerMove(event) {
    if (!pointers.current.has(event.pointerId)) return;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.current.size === 2 && pinch.current) {
      const pts = [...pointers.current.values()];
      const distance = Math.hypot(pts[0].x - pts[1].x, pts[0].y - pts[1].y) || 1;
      const nextZoom = pinch.current.zoom * (distance / pinch.current.distance);
      zoomAround(nextZoom, cropSize / 2, frameHeight() / 2);
      return;
    }
    const image = preparedRef.current;
    if (!drag.current || !image) return;
    const visible = isCover
      ? coverFrame(image.width, image.height, cropRef.current.zoom)
      : { visibleW: coverVisible(image.width, image.height, cropRef.current.zoom), visibleH: coverVisible(image.width, image.height, cropRef.current.zoom) };
    const scale = cropSize / visible.visibleW;
    applyCrop({
      zoom: cropRef.current.zoom,
      sx: drag.current.sx - (event.clientX - drag.current.x) / scale,
      sy: drag.current.sy - (event.clientY - drag.current.y) / scale,
    });
  }

  function onPointerUp(event) {
    pointers.current.delete(event.pointerId);
    if (pointers.current.size < 2) pinch.current = null;
    if (pointers.current.size === 0) drag.current = null;
  }

  const imageStyle = useMemo(() => {
    if (!prepared) return null;
    return isCover
      ? cropFrameStyle(prepared.width, prepared.height, crop, cropSize)
      : cropImageStyle(prepared.width, prepared.height, crop, cropSize);
  }, [prepared, crop, cropSize, isCover]);

  const previewStyle = useMemo(() => {
    if (!prepared) return null;
    const previewWidth = isCover ? 220 : 88;
    return isCover
      ? cropFrameStyle(prepared.width, prepared.height, crop, previewWidth)
      : cropImageStyle(prepared.width, prepared.height, crop, previewWidth);
  }, [prepared, crop, isCover]);

  return (
    <>
      <Dialog
        wide
        busy={saving}
        hideActions
        title={isCover ? "Adjust cover photo" : "Adjust profile photo"}
        description={isCover
          ? "Drag and zoom so the profile header shows the part of the photo you want."
          : "Position your photo so it looks good inside your alumni profile."}
        onClose={requestClose}
        footer={(
          <>
            <button type="button" className="btn btn-outline" onClick={requestClose} disabled={saving}>
              Cancel
            </button>
            <button type="button" className="btn btn-navy" onClick={savePhoto} disabled={saving || preparing || !prepared}>
              {saving ? "Saving…" : "Save Photo"}
            </button>
          </>
        )}
      >
        <div className="sr-only" aria-live="polite">{status}</div>
        <Alert type="error">{error}</Alert>
        {error && prepared ? (
          <button type="button" className="btn btn-outline btn-sm" onClick={savePhoto} disabled={saving}>
            Try again
          </button>
        ) : null}
        {error && !prepared && !preparing ? (
          <button type="button" className="btn btn-outline btn-sm" onClick={onClose}>
            Choose another photo
          </button>
        ) : null}

        {preparing ? (
          <p className="muted">Preparing photo…</p>
        ) : prepared ? (
          <div className="photo-crop">
            <div className="photo-crop-stage">
              <p className="photo-crop-caption">
                {isCover ? "This area will become your profile header." : "This area will become your profile picture."}
              </p>
              <div
                ref={viewRef}
                className={`photo-crop-viewport${isCover ? " is-cover" : ""}`}
                tabIndex={0}
                role="group"
                aria-label={isCover
                  ? "Cover photo crop area. Drag or use arrow keys to reposition."
                  : "Profile photo crop area. Drag or use arrow keys to reposition."}
                onPointerDown={onPointerDown}
                onPointerMove={onPointerMove}
                onPointerUp={onPointerUp}
                onPointerCancel={onPointerUp}
                onKeyDown={(event) => {
                  if (!prepared || saving) return;
                  const frame = isCover
                    ? coverFrame(prepared.width, prepared.height, crop.zoom)
                    : { visibleW: coverVisible(prepared.width, prepared.height, crop.zoom), visibleH: coverVisible(prepared.width, prepared.height, crop.zoom) };
                  const stepX = frame.visibleW * 0.05;
                  const stepY = frame.visibleH * 0.05;
                  if (event.key === "ArrowLeft") {
                    event.preventDefault();
                    applyCrop({ ...crop, sx: crop.sx - stepX });
                  } else if (event.key === "ArrowRight") {
                    event.preventDefault();
                    applyCrop({ ...crop, sx: crop.sx + stepX });
                  } else if (event.key === "ArrowUp") {
                    event.preventDefault();
                    applyCrop({ ...crop, sy: crop.sy - stepY });
                  } else if (event.key === "ArrowDown") {
                    event.preventDefault();
                    applyCrop({ ...crop, sy: crop.sy + stepY });
                  }
                }}
              >
                {previewUrl ? (
                  <img
                    src={previewUrl}
                    alt=""
                    draggable={false}
                    className="photo-crop-image"
                    style={imageStyle}
                  />
                ) : null}
                <span className={`photo-crop-mask${isCover ? " is-cover" : ""}`} aria-hidden="true" />
              </div>
              <div className="photo-crop-preview-wrap">
                <p className="eyebrow">Preview</p>
                <div className={isCover ? "photo-crop-preview is-cover" : "profile-photo md photo-crop-preview"} aria-hidden="true">
                  {previewUrl ? <img src={previewUrl} alt="" draggable={false} style={previewStyle} /> : <span>{initials({})}</span>}
                </div>
              </div>
            </div>

            <div className="photo-crop-zoom">
              <label htmlFor="profile-photo-zoom">Zoom</label>
              <div className="photo-crop-zoom-row">
                <button
                  type="button"
                  className="btn btn-outline btn-sm photo-crop-zoom-btn"
                  aria-label="Zoom out"
                  disabled={saving || crop.zoom <= 1}
                  onClick={() => zoomAround(crop.zoom - 0.15, cropSize / 2, frameHeight() / 2)}
                >
                  <MinusIcon size={16} />
                </button>
                <input
                  id={isCover ? "cover-photo-zoom" : "profile-photo-zoom"}
                  type="range"
                  min={1}
                  max={maxZoom}
                  step={0.01}
                  value={crop.zoom}
                  aria-label={isCover ? "Cover photo zoom" : "Profile photo zoom"}
                  disabled={saving}
                  onChange={(event) => zoomAround(Number(event.target.value), cropSize / 2, frameHeight() / 2)}
                />
                <button
                  type="button"
                  className="btn btn-outline btn-sm photo-crop-zoom-btn"
                  aria-label="Zoom in"
                  disabled={saving || crop.zoom >= maxZoom}
                  onClick={() => zoomAround(crop.zoom + 0.15, cropSize / 2, frameHeight() / 2)}
                >
                  <PlusIcon size={16} />
                </button>
              </div>
            </div>
            {isCover && onReplace ? (
              <input
                ref={replaceRef}
                className="sr-only"
                type="file"
                accept={PHOTO_ACCEPT}
                onChange={pickReplacement}
              />
            ) : null}
            <div className="photo-crop-actions">
              <button type="button" className="btn btn-outline btn-sm" onClick={resetCrop} disabled={saving || !dirty}>
                Reset
              </button>
              {isCover && onReplace ? (
                <button type="button" className="btn btn-outline btn-sm" onClick={() => replaceRef.current?.click()} disabled={saving}>
                  Choose another photo
                </button>
              ) : null}
            </div>
          </div>
        ) : null}
      </Dialog>

      {confirmDiscard ? (
        <Dialog
          compact
          hideActions
          title="Discard changes?"
          description="Your photo adjustments haven't been saved."
          onClose={() => setConfirmDiscard(false)}
          footer={(
            <>
              <button type="button" className="btn btn-outline" onClick={() => setConfirmDiscard(false)}>
                Keep editing
              </button>
              <button
                type="button"
                className="btn btn-danger"
                onClick={() => {
                  setConfirmDiscard(false);
                  onClose();
                }}
              >
                Discard
              </button>
            </>
          )}
        />
      ) : null}
    </>
  );
}

export function CoverPhotoControl({ hasCover, disabled, onFile, onUploaded, onInvalid }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState("");
  const [confirmRemove, setConfirmRemove] = useState(false);
  const [removeError, setRemoveError] = useState("");
  const locked = disabled || Boolean(busy);
  const label = hasCover ? "Change cover photo" : "Add cover photo";

  function openPicker() {
    if (locked) return;
    inputRef.current?.click();
  }

  function onChange(event) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    const invalid = validatePhotoFile(file);
    if (invalid) {
      onInvalid?.(invalid);
      return;
    }
    onInvalid?.("");
    onFile?.(file);
  }

  async function removeCover() {
    setBusy("removing");
    setRemoveError("");
    try {
      const payload = await api("/api/alumni/profile/cover", { method: "DELETE" });
      setConfirmRemove(false);
      onUploaded?.(payload, "Cover photo removed.");
    } catch (err) {
      setRemoveError(friendlyError(err, "We couldn't remove your cover photo. Please try again."));
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="cover-photo-control">
      <button
        type="button"
        className="btn btn-outline btn-sm"
        onClick={openPicker}
        disabled={locked}
        aria-label={label}
      >
        {label}
      </button>
      {hasCover ? (
        <button
          type="button"
          className="btn btn-outline btn-sm"
          onClick={() => {
            setRemoveError("");
            setConfirmRemove(true);
          }}
          disabled={locked}
        >
          {busy === "removing" ? "Removing…" : "Remove cover photo"}
        </button>
      ) : null}
      <input
        ref={inputRef}
        className="sr-only"
        type="file"
        accept={PHOTO_ACCEPT}
        disabled={locked}
        onChange={onChange}
      />
      {confirmRemove ? (
        <Dialog
          title="Remove cover photo?"
          description="Your alumni profile will use the default header background. You can add a new cover photo later."
          confirmLabel={busy === "removing" ? "Removing…" : "Remove cover photo"}
          danger
          busy={busy === "removing"}
          onConfirm={removeCover}
          onClose={() => {
            if (busy !== "removing") setConfirmRemove(false);
          }}
        >
          <Alert type="error">{removeError}</Alert>
        </Dialog>
      ) : null}
    </div>
  );
}
