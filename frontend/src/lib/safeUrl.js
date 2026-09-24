export function safeHttpUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw.includes("://") ? raw : `https://${raw}`);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return "";
    if (parsed.username || parsed.password) return "";
    return parsed.toString();
  } catch {
    return "";
  }
}

export function safeAlumniPath(value) {
  const raw = String(value || "").trim();
  if (!raw.startsWith("/alumni")) return "";
  if (raw.startsWith("//") || raw.includes("..") || raw.includes("\\")) return "";
  const pathOnly = raw.split("#")[0].split("?")[0];
  if (pathOnly.includes(":")) return "";
  return raw;
}
