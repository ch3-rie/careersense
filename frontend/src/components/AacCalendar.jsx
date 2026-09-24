import { ChevronLeftIcon, ChevronRightIcon } from "./icons";

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export function isoFromDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function dateFromIso(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) return null;
  return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
}

export function formatCalendarDate(value) {
  const date = dateFromIso(value);
  if (!date) return "";
  return date.toLocaleDateString("en-PH", { year: "numeric", month: "long", day: "numeric" });
}

function shiftMonth(month, amount) {
  return new Date(month.getFullYear(), month.getMonth() + amount, 1);
}

function sameMonth(left, right) {
  return left.getFullYear() === right.getFullYear() && left.getMonth() === right.getMonth();
}

export function MonthCalendar({
  month,
  onMonth,
  selected,
  onSelect,
  marks = {},
  isSelectable,
  ariaLabel = "Appointment calendar",
}) {
  const today = isoFromDate(new Date());
  const currentMonth = new Date();
  const year = month.getFullYear();
  const monthIndex = month.getMonth();
  const first = new Date(year, monthIndex, 1);
  const daysInMonth = new Date(year, monthIndex + 1, 0).getDate();
  const cells = [
    ...Array.from({ length: first.getDay() }, () => null),
    ...Array.from({ length: daysInMonth }, (_, index) => index + 1),
  ];
  const title = first.toLocaleDateString("en-PH", { month: "long", year: "numeric" });
  const previousDisabled = sameMonth(month, currentMonth) || month < new Date(currentMonth.getFullYear(), currentMonth.getMonth(), 1);

  return (
    <div className="aac-cal">
      <div className="aac-cal-nav">
        <button
          type="button"
          aria-label="Previous month"
          disabled={previousDisabled}
          onClick={() => onMonth(shiftMonth(month, -1))}
        >
          <ChevronLeftIcon size={16} />
        </button>
        <h3>{title}</h3>
        <button type="button" aria-label="Next month" onClick={() => onMonth(shiftMonth(month, 1))}>
          <ChevronRightIcon size={16} />
        </button>
      </div>
      <div className="aac-cal-grid" role="group" aria-label={ariaLabel}>
        {WEEKDAYS.map((day) => (
          <div key={day} className="aac-cal-dow">{day}</div>
        ))}
        {cells.map((day, index) => {
          if (!day) return <div key={`pad-${index}`} className="aac-cal-pad" />;
          const date = new Date(year, monthIndex, day);
          const iso = isoFromDate(date);
          const mark = marks[iso];
          const selectable = isSelectable ? isSelectable(iso, date) : true;
          const selectedDay = selected === iso;
          return (
            <button
              key={iso}
              type="button"
              className={[
                "aac-cal-day",
                iso === today ? "is-today" : "",
                mark ? "is-marked" : "",
                selectedDay ? "is-selected" : "",
              ].filter(Boolean).join(" ")}
              aria-label={mark?.label ? `${formatCalendarDate(iso)}, ${mark.label}` : formatCalendarDate(iso)}
              aria-pressed={selectedDay}
              disabled={!selectable}
              onClick={() => onSelect(iso)}
            >
              <span>{day}</span>
              {mark?.text ? <small>{mark.text}</small> : null}
            </button>
          );
        })}
      </div>
    </div>
  );
}
