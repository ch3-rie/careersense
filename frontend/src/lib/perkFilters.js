export function parsePerkDate(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(value || ""));
  if (!match) return null;
  return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) };
}

export function perkIsExpired(row, today = new Date()) {
  if (row?.expired === true) return true;
  const parsed = parsePerkDate(row?.valid_to);
  if (!parsed) return false;
  const now = { year: today.getFullYear(), month: today.getMonth() + 1, day: today.getDate() };
  if (parsed.year !== now.year) return parsed.year < now.year;
  if (parsed.month !== now.month) return parsed.month < now.month;
  return parsed.day < now.day;
}

export function filterAlumniPerks(items, { query = "", category = "", status = "" } = {}) {
  const needle = String(query || "").trim().toLowerCase();
  return (items || []).filter((row) => {
    const hay = `${row.name || ""} ${row.partner || ""} ${row.discount || ""} ${row.category || ""} ${row.description || ""} ${row.eligibility || ""}`.toLowerCase();
    if (needle && !hay.includes(needle)) return false;
    if (category && row.category !== category) return false;
    if (status && row.status !== status) return false;
    return true;
  });
}

export function filterAdminPerks(items, { query = "", category = "", status = "", expiry = "" } = {}) {
  const needle = String(query || "").trim().toLowerCase();
  return (items || []).filter((row) => {
    const hay = `${row.name} ${row.partner} ${row.discount} ${row.category} ${row.description}`.toLowerCase();
    if (needle && !hay.includes(needle)) return false;
    if (category && row.category !== category) return false;
    if (status === "active" && !row.active) return false;
    if (status === "inactive" && row.active) return false;
    if (expiry === "expiring" && !row.expiring_soon) return false;
    if (expiry === "expired" && !perkIsExpired(row)) return false;
    return true;
  });
}
