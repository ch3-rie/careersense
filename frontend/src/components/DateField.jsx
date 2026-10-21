import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from "./icons";
import { dateFromIso, formatCalendarDate, isoFromDate } from "./AacCalendar";

const WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"];
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

function todayIso() {
  return isoFromDate(new Date());
}

function parseYear(value) {
  const match = /^(\d{4})/.exec(String(value || ""));
  return match ? Number(match[1]) : null;
}

function addDays(date, amount) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + amount);
}

function inRange(iso, min, max) {
  if (min && iso < min) return false;
  if (max && iso > max) return false;
  return true;
}

function monthCells(year, month) {
  const first = new Date(year, month, 1);
  const start = addDays(first, -first.getDay());
  return Array.from({ length: 42 }, (_, index) => addDays(start, index));
}

function shiftMonth(year, month, amount) {
  const next = new Date(year, month + amount, 1);
  return { year: next.getFullYear(), month: next.getMonth() };
}

function displayText(value) {
  if (!value) return "";
  if (/^\d{4}$/.test(value)) return value;
  return formatCalendarDate(value) || String(value);
}

function validationMessage(value, { mode, allowYear, min, max }) {
  if (!value) return "";
  if (mode === "year" || /^\d{4}$/.test(value)) {
    if (mode !== "year" && !allowYear) return "Enter a valid date.";
    if (!/^\d{4}$/.test(value)) return "Enter a four-digit year.";
    const year = Number(value);
    const minYear = parseYear(min) ?? 1950;
    const maxYear = mode === "year"
      ? (parseYear(max) ?? new Date().getFullYear() + 8)
      : new Date().getFullYear() + 1;
    if (year < minYear || year > maxYear) return "Enter a valid year.";
    return "";
  }
  if (!dateFromIso(value)) return "Enter a valid date.";
  if (min && value < min) return "Choose a later date.";
  if (max && value > max) return "Choose an earlier date.";
  return "";
}

function yearPage(year) {
  return year - (year % 12);
}

export function DateField({
  id,
  name,
  value,
  defaultValue = "",
  onChange,
  disabled = false,
  min,
  max,
  mode = "date",
  allowYear = false,
  placeholder,
  "aria-label": ariaLabel,
  "aria-required": ariaRequired,
  "aria-invalid": ariaInvalid,
  "aria-describedby": ariaDescribedBy,
}) {
  const autoId = useId();
  const controlId = id || autoId;
  const messageId = `${controlId}-invalid`;
  const popId = `${controlId}-calendar`;
  const controlled = value !== undefined;
  const [inner, setInner] = useState(defaultValue || "");
  const current = controlled ? (value || "") : inner;
  const [open, setOpen] = useState(false);
  const [view, setView] = useState(() => initialView(current));
  const [focusIso, setFocusIso] = useState("");
  const triggerRef = useRef(null);
  const popRef = useRef(null);
  const restoreFocus = useRef(false);
  const message = validationMessage(current, { mode, allowYear, min, max });
  const describedBy = [ariaDescribedBy, message ? messageId : null].filter(Boolean).join(" ") || undefined;
  const emptyLabel = placeholder || (mode === "year" ? "Select year" : "Select Date");

  useEffect(() => {
    if (!controlled) setInner(defaultValue || "");
  }, [controlled, defaultValue]);

  useEffect(() => {
    if (!open) return undefined;
    function onPointer(event) {
      if (popRef.current?.contains(event.target) || triggerRef.current?.contains(event.target)) return;
      setOpen(false);
    }
    function onKey(event) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      restoreFocus.current = true;
      setOpen(false);
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    if (open || !restoreFocus.current) return;
    restoreFocus.current = false;
    triggerRef.current?.focus();
  }, [open]);

  useLayoutEffect(() => {
    if (!open || !popRef.current || !triggerRef.current) return undefined;
    function place() {
      const pop = popRef.current;
      const trigger = triggerRef.current;
      if (!pop || !trigger) return;
      const rect = trigger.getBoundingClientRect();
      const width = pop.offsetWidth;
      const height = pop.offsetHeight;
      const margin = 8;
      let top = rect.bottom + margin;
      let left = rect.left;
      if (top + height > window.innerHeight - margin) top = Math.max(margin, rect.top - height - margin);
      if (left + width > window.innerWidth - margin) left = Math.max(margin, window.innerWidth - width - margin);
      pop.style.top = `${top}px`;
      pop.style.left = `${left}px`;
    }
    place();
    window.addEventListener("resize", place);
    document.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      document.removeEventListener("scroll", place, true);
    };
  }, [open, view.year, view.month, mode]);

  useLayoutEffect(() => {
    if (!open || !focusIso) return;
    popRef.current?.querySelector(`[data-iso="${focusIso}"]`)?.focus();
  }, [open, focusIso, view.year, view.month]);

  function commit(next) {
    if (!controlled) setInner(next);
    onChange?.({ target: { name: name || "", value: next } });
    restoreFocus.current = true;
    setOpen(false);
  }

  function openCalendar() {
    if (disabled) return;
    const nextView = initialView(current);
    setView(nextView);
    const selected = dateFromIso(current) ? current : "";
    setFocusIso(mode === "year" ? "" : (selected || firstSelectable(nextView.year, nextView.month, min, max) || todayIso()));
    setOpen(true);
  }

  function moveFocus(delta) {
    const origin = dateFromIso(focusIso) || dateFromIso(current) || new Date();
    let next = addDays(origin, delta);
    const step = delta < 0 ? -1 : 1;
    for (let guard = 0; guard < 400; guard += 1) {
      const iso = isoFromDate(next);
      if (inRange(iso, min, max)) {
        setView({ year: next.getFullYear(), month: next.getMonth() });
        setFocusIso(iso);
        return;
      }
      next = addDays(next, step);
    }
  }

  function onGridKey(event) {
    const jumps = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    if (jumps[event.key]) {
      event.preventDefault();
      moveFocus(jumps[event.key]);
      return;
    }
    if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const origin = dateFromIso(focusIso) || new Date();
      const sunday = addDays(origin, -origin.getDay());
      moveFocus(isoDayDelta(origin, event.key === "Home" ? sunday : addDays(sunday, 6)));
      return;
    }
    if (event.key === "PageUp" || event.key === "PageDown") {
      event.preventDefault();
      const amount = (event.key === "PageUp" ? -1 : 1) * (event.shiftKey ? 12 : 1);
      const origin = dateFromIso(focusIso) || new Date();
      const shifted = new Date(origin.getFullYear(), origin.getMonth() + amount, origin.getDate());
      const iso = isoFromDate(shifted);
      if (inRange(iso, min, max)) {
        setView({ year: shifted.getFullYear(), month: shifted.getMonth() });
        setFocusIso(iso);
      }
    }
  }

  const startYear = parseYear(min) ?? 1950;
  const endYear = parseYear(max) ?? new Date().getFullYear() + (mode === "year" ? 8 : 10);
  const today = todayIso();
  const previous = shiftMonth(view.year, view.month, -1);
  const following = shiftMonth(view.year, view.month, 1);
  const previousDisabled = !monthSelectable(previous.year, previous.month, min, max);
  const nextDisabled = !monthSelectable(following.year, following.month, min, max);

  return (
    <div className={`date-field${open ? " is-open" : ""}${message || ariaInvalid ? " has-error" : ""}`}>
      <button
        ref={triggerRef}
        id={controlId}
        type="button"
        className="date-field-trigger"
        disabled={disabled}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? popId : undefined}
        aria-label={ariaLabel}
        aria-required={ariaRequired || undefined}
        aria-invalid={message || ariaInvalid ? true : undefined}
        aria-describedby={describedBy}
        onClick={() => (open ? setOpen(false) : openCalendar())}
        onKeyDown={(event) => {
          if (event.key === "ArrowDown" || event.key === "ArrowUp") {
            event.preventDefault();
            openCalendar();
          }
        }}
      >
        <span className={current ? "date-field-value" : "date-field-placeholder"}>
          {current ? displayText(current) : emptyLabel}
        </span>
        <CalendarIcon size={18} />
      </button>
      {name ? <input type="hidden" name={name} value={current} /> : null}
      {message ? <span className="field-error" id={messageId}>{message}</span> : null}
      {open ? createPortal(
        <div
          ref={popRef}
          id={popId}
          className="date-popover"
          role="dialog"
          aria-modal="false"
          aria-label={mode === "year" ? "Choose a year" : "Choose a date"}
          onKeyDown={(event) => {
            if (event.key !== "Tab") return;
            const items = [...popRef.current.querySelectorAll("button, select")].filter((el) => !el.disabled);
            if (!items.length) return;
            const first = items[0];
            const last = items[items.length - 1];
            if (event.shiftKey && document.activeElement === first) {
              event.preventDefault();
              last.focus();
            } else if (!event.shiftKey && document.activeElement === last) {
              event.preventDefault();
              first.focus();
            }
          }}
        >
          {mode === "year" ? (
            <YearPanel
              page={yearPage(view.year)}
              selected={/^\d{4}$/.test(current) ? Number(current) : parseYear(current)}
              minYear={startYear}
              maxYear={endYear}
              onPage={(page) => setView({ year: page, month: 0 })}
              onSelect={(year) => commit(String(year))}
            />
          ) : (
            <>
              <div className="date-popover-head">
                <button type="button" className="date-popover-nav" aria-label="Previous month" disabled={previousDisabled} onClick={() => setView(previous)}>
                  <ChevronLeftIcon size={16} />
                </button>
                <select aria-label="Month" value={view.month} onChange={(event) => setView({ ...view, month: Number(event.target.value) })}>
                  {MONTHS.map((label, index) => (
                    <option key={label} value={index}>{label}</option>
                  ))}
                </select>
                <select aria-label="Year" value={view.year} onChange={(event) => setView({ ...view, year: Number(event.target.value) })}>
                  {yearOptions(startYear, endYear).map((year) => (
                    <option key={year} value={year}>{year}</option>
                  ))}
                </select>
                <button type="button" className="date-popover-nav" aria-label="Next month" disabled={nextDisabled} onClick={() => setView(following)}>
                  <ChevronRightIcon size={16} />
                </button>
              </div>
              <div className="date-popover-grid" role="grid" aria-label="Calendar" onKeyDown={onGridKey}>
                {WEEKDAYS.map((day) => (
                  <div key={day} className="date-popover-dow" role="columnheader">{day}</div>
                ))}
                {monthCells(view.year, view.month).map((date) => {
                  const iso = isoFromDate(date);
                  const outside = date.getMonth() !== view.month;
                  const disabledDay = !inRange(iso, min, max);
                  const selected = current === iso;
                  return (
                    <button
                      key={iso}
                      type="button"
                      role="gridcell"
                      data-iso={iso}
                      className={[
                        "date-popover-day",
                        outside ? "is-outside" : "",
                        iso === today ? "is-today" : "",
                        selected ? "is-selected" : "",
                      ].filter(Boolean).join(" ")}
                      aria-label={formatCalendarDate(iso)}
                      aria-selected={selected}
                      aria-current={iso === today ? "date" : undefined}
                      aria-disabled={disabledDay || undefined}
                      disabled={disabledDay}
                      tabIndex={focusIso === iso ? 0 : -1}
                      onClick={() => commit(iso)}
                    >
                      {date.getDate()}
                    </button>
                  );
                })}
              </div>
              <div className="date-popover-foot">
                <button type="button" disabled={!inRange(today, min, max)} onClick={() => commit(today)}>Today</button>
                {allowYear ? (
                  <button type="button" onClick={() => commit(String(view.year))}>Year only</button>
                ) : <span />}
                <button type="button" onClick={() => commit("")}>Clear</button>
              </div>
            </>
          )}
        </div>,
        document.body,
      ) : null}
    </div>
  );
}

function YearPanel({ page, selected, minYear, maxYear, onPage, onSelect }) {
  const years = Array.from({ length: 12 }, (_, index) => page + index);
  const current = new Date().getFullYear();
  return (
    <>
      <div className="date-popover-head is-year">
        <button type="button" className="date-popover-nav" aria-label="Previous years" disabled={page <= minYear} onClick={() => onPage(page - 12)}>
          <ChevronLeftIcon size={16} />
        </button>
        <strong>{years[0]} – {years[years.length - 1]}</strong>
        <button type="button" className="date-popover-nav" aria-label="Next years" disabled={page + 11 >= maxYear} onClick={() => onPage(page + 12)}>
          <ChevronRightIcon size={16} />
        </button>
      </div>
      <div className="date-popover-years">
        {years.map((year) => {
          const blocked = year < minYear || year > maxYear;
          return (
            <button
              key={year}
              type="button"
              className={[
                "date-popover-year",
                year === current ? "is-today" : "",
                year === selected ? "is-selected" : "",
              ].filter(Boolean).join(" ")}
              disabled={blocked}
              aria-pressed={year === selected}
              onClick={() => onSelect(year)}
            >
              {year}
            </button>
          );
        })}
      </div>
    </>
  );
}

function initialView(value) {
  const date = dateFromIso(value) || (/^\d{4}$/.test(value || "") ? new Date(Number(value), 0, 1) : new Date());
  return { year: date.getFullYear(), month: date.getMonth() };
}

function yearOptions(start, end) {
  const years = [];
  for (let year = start; year <= end; year += 1) years.push(year);
  return years;
}

function firstSelectable(year, month, min, max) {
  const last = new Date(year, month + 1, 0).getDate();
  for (let day = 1; day <= last; day += 1) {
    const iso = isoFromDate(new Date(year, month, day));
    if (inRange(iso, min, max)) return iso;
  }
  return "";
}

function monthSelectable(year, month, min, max) {
  const last = new Date(year, month + 1, 0).getDate();
  for (let day = 1; day <= last; day += 1) {
    if (inRange(isoFromDate(new Date(year, month, day)), min, max)) return true;
  }
  return false;
}

function isoDayDelta(from, to) {
  return Math.round((to - from) / 86400000);
}
