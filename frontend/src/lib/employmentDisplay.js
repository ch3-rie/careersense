function text(value) {
  return String(value || "").trim();
}

function isYes(value) {
  return ["yes", "y", "true", "1"].includes(text(value).toLowerCase());
}

function isNo(value) {
  return ["no", "n", "false", "0"].includes(text(value).toLowerCase());
}

export function relatedAlignment(value) {
  const v = String(value || "").trim().toLowerCase();
  if (["yes", "aligned", "related"].includes(v)) return { label: "Aligned", tone: "aligned" };
  if (["no", "misaligned", "not related", "unrelated"].includes(v)) return { label: "Misaligned", tone: "misaligned" };
  if (!v) return { label: "Unknown", tone: "unknown" };
  return { label: String(value), tone: "unknown" };
}

export function isStaleDate(value, days = 365) {
  if (!value) return false;
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return false;
  return Date.now() - then > days * 24 * 60 * 60 * 1000;
}

export function officialEmploymentFromGts(data = {}) {
  const firstOccupation = text(data.first_occ);
  const firstEmployer = text(data.first_emp);
  const presentOccupation = text(data.pres_occ);
  const presentEmployer = text(data.pres_emp);
  const currentlyEmployed = isYes(data.is_currently_employed);
  if (!currentlyEmployed) {
    return {
      currentlyEmployed: false,
      answered: isNo(data.is_currently_employed),
      presentIsFirst: false,
      occupation: "",
      employer: "",
      related: "",
    };
  }
  const presentIsFirst = !isNo(data.present_job_is_first);
  return {
    currentlyEmployed: true,
    answered: true,
    presentIsFirst,
    occupation: presentIsFirst ? firstOccupation : presentOccupation,
    employer: presentIsFirst ? firstEmployer : presentEmployer,
    related: presentIsFirst ? text(data.first_related) : text(data.present_related_degree),
  };
}
