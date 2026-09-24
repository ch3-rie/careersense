import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { MoreVerticalIcon } from "./icons";

function useCompactActions(query = "(max-width: 767px)") {
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const media = window.matchMedia(query);
    const update = () => setCompact(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [query]);
  return compact;
}

export function RowActions({ primary = [], more = [], collapseQuery = "(max-width: 767px)" }) {
  const compact = useCompactActions(collapseQuery);
  const menuId = useId();
  const wrapRef = useRef(null);
  const buttonRef = useRef(null);
  const menuRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState(null);

  const visible = compact ? [] : primary;
  const menuItems = compact ? [...primary, ...more] : more;
  const showMenu = menuItems.length > 0;

  useEffect(() => {
    function onOtherOpen(event) {
      if (event.detail !== menuId) setOpen(false);
    }
    window.addEventListener("cs-row-actions-open", onOtherOpen);
    return () => window.removeEventListener("cs-row-actions-open", onOtherOpen);
  }, [menuId]);

  useEffect(() => {
    if (!open) return undefined;
    function onPointer(event) {
      if (wrapRef.current?.contains(event.target) || menuRef.current?.contains(event.target)) return;
      setOpen(false);
    }
    function onKey(event) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useLayoutEffect(() => {
    if (!open) return undefined;
    function place() {
      const button = buttonRef.current;
      const menu = menuRef.current;
      if (!button || !menu) return;
      const rect = button.getBoundingClientRect();
      const gap = 6;
      const margin = 8;
      const width = Math.max(menu.offsetWidth, 188);
      const height = menu.offsetHeight;
      const spaceBelow = window.innerHeight - rect.bottom - margin;
      const openUp = spaceBelow < height && rect.top - margin > spaceBelow;
      let top = openUp ? rect.top - height - gap : rect.bottom + gap;
      let left = rect.right - width;
      left = Math.min(Math.max(margin, left), window.innerWidth - width - margin);
      top = Math.min(Math.max(margin, top), window.innerHeight - height - margin);
      setCoords({ top, left, width });
    }
    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [open, menuItems.length]);

  function toggleMenu(event) {
    event.stopPropagation();
    if (!open) window.dispatchEvent(new CustomEvent("cs-row-actions-open", { detail: menuId }));
    setOpen((value) => !value);
  }

  function run(item, event) {
    event.stopPropagation();
    if (item.disabled) return;
    setOpen(false);
    item.onClick?.();
  }

  return (
    <div className="row-actions" ref={wrapRef} onClick={(event) => event.stopPropagation()}>
      {visible.map((item) => (
        <button
          key={item.id}
          type="button"
          className={`btn btn-outline btn-sm row-action-btn${item.danger ? " row-action-danger" : ""}`}
          title={item.disabled ? item.disabledReason || item.label : item.label}
          aria-label={item.label}
          disabled={item.disabled}
          onClick={(event) => run(item, event)}
        >
          {item.icon ? <item.icon size={14} /> : null}
          <span>{item.label}</span>
        </button>
      ))}
      {showMenu ? (
        <>
          <button
            ref={buttonRef}
            type="button"
            className="btn btn-outline btn-sm icon-btn row-action-more"
            title="More actions"
            aria-label="More actions"
            aria-haspopup="menu"
            aria-expanded={open}
            onClick={toggleMenu}
          >
            <MoreVerticalIcon size={16} />
          </button>
          {open && typeof document !== "undefined"
            ? createPortal(
              <div
                ref={menuRef}
                className="mini-menu row-actions-menu"
                role="menu"
                style={coords
                  ? { top: coords.top, left: coords.left, minWidth: coords.width }
                  : { visibility: "hidden", pointerEvents: "none" }}
              >
                {menuItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    role="menuitem"
                    className={item.danger ? "danger" : undefined}
                    disabled={item.disabled}
                    title={item.disabled ? item.disabledReason : undefined}
                    onClick={(event) => run(item, event)}
                  >
                    {item.icon ? <item.icon size={14} /> : null}
                    {item.label}
                  </button>
                ))}
              </div>,
              document.body
            )
            : null}
        </>
      ) : null}
    </div>
  );
}
