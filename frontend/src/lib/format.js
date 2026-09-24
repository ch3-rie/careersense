export function toPascalCase(value) {
  if (typeof value !== "string") return value;
  if (value === "—" || value === "–" || value === "-") return value;
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) return value;
  if (/^https?:\/\//i.test(trimmed) || /^mailto:/i.test(trimmed)) return value;
  if (/^[\d₱$.,%\-–—/:]+$/.test(trimmed)) return value;
  return trimmed
    .split(/\s+/)
    .map((word) => {
      if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(word)) return word;
      if (/^[\d₱$.,%\-–—/:]+$/.test(word)) return word;
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join("");
}

export function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-PH", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatLongDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-PH", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function formatMonthYear(value) {
  if (!value) return "";
  const text = String(value).slice(0, 10);
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
  const date = match
    ? new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
    : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleDateString("en-PH", { year: "numeric", month: "long" });
}

export function formatEmploymentPeriod(start, end, isCurrent) {
  const startText = formatMonthYear(start);
  const endText = isCurrent ? "Present" : formatMonthYear(end);
  if (!startText && !endText) return "";
  return startText && endText ? `${startText} – ${endText}` : startText || endText;
}

export function formatDateTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-PH", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleTimeString("en-PH", {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatChartDate(value) {
  if (!value) return "";
  const raw = String(value);
  const date = new Date(raw.includes("T") ? raw : `${raw}T00:00:00`);
  if (Number.isNaN(date.getTime())) return raw;
  return date.toLocaleDateString("en-PH", { month: "short", day: "numeric" });
}

export function displayValue(value) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function fullName(obj = {}) {
  return [obj.first_name, obj.middle_name, obj.last_name].filter(Boolean).join(" ") || "—";
}

export function parserLabel(source) {
  const labels = {
    gemini: "AI extraction",
    heuristic: "Built-in parser",
    ocr: "OCR extraction",
    "gemini+heuristic": "AI + built-in parser",
    empty: "No text extracted",
    failed: "Extraction failed",
  };
  return labels[source] || source || "—";
}

export function sectionLabel(key) {
  return (
    {
      general: "General information",
      employment: "Employment",
      studies: "Further studies",
      feedback: "Institutional feedback",
    }[key] || key
  );
}

export function questionTypeLabel(type) {
  return (
    {
      short_answer: "Short answer",
      paragraph: "Paragraph",
      multiple_choice: "Multiple choice",
      checkboxes: "Checkboxes",
      dropdown: "Dropdown",
      scale: "Linear scale",
      yes_no: "Yes/No",
      date: "Date",
      number: "Number",
      email: "Email",
      skills: "Skills list",
      repeatable_group: "Repeatable group",
    }[type] || type
  );
}

export function ratingLabel(value) {
  const map = { 3: "Great extent", 2: "Small extent", 1: "Not at all" };
  if (value === "" || value == null) return "—";
  return map[value] ? `${value} · ${map[value]}` : String(value);
}

export function suggestionLabel(key) {
  return (
    {
      include_new_courses: "Include new courses or subjects",
      develop_competencies: "Develop more competencies",
      improve_teaching_methods: "Improve teaching methods",
      increase_ojt_duration: "Increase OJT duration",
      other: "Other suggestions",
    }[key] || String(key).replace(/_/g, " ")
  );
}

export function questionLabelsFrom(questions = []) {
  return Object.fromEntries((questions || []).map((q) => [q.id, q.label]));
}

export function splitList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value.map(String).map((s) => s.trim()).filter(Boolean);
  return String(value).split(/[,;|]+/).map((s) => s.trim()).filter(Boolean);
}
