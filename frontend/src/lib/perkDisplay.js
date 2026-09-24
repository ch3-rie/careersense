import { parsePerkDate } from "./perkFilters.js";

const LIMITED_DAYS = 14;

function daysUntil(parsed, today) {
  const end = Date.UTC(parsed.year, parsed.month - 1, parsed.day);
  const start = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((end - start) / 86400000);
}

export function parsePerkOffer(discount) {
  const text = String(discount || "").trim();
  if (!text) return { kind: "empty", value: "Perk", suffix: "", raw: "" };
  const percent = text.match(/(\d+(?:\.\d+)?)\s*%/);
  if (percent) {
    return { kind: "percent", value: `${percent[1]}%`, suffix: "OFF", raw: text };
  }
  const amountOff = text.match(/^(₱[\d,]+(?:\.\d+)?)\s*off$/i);
  if (amountOff) {
    return { kind: "amount", value: amountOff[1], suffix: "OFF", raw: text };
  }
  return { kind: "text", value: text, suffix: "", raw: text };
}

export function perkWebsiteLabel(url) {
  const raw = String(url || "").trim();
  if (!raw) return "";
  try {
    const parsed = new URL(raw.includes("://") ? raw : `https://${raw}`);
    const host = parsed.hostname.replace(/^www\./i, "");
    const path = parsed.pathname === "/" ? "" : parsed.pathname.replace(/\/$/, "");
    return `${host}${path}`;
  } catch {
    return raw.replace(/^https?:\/\//i, "").replace(/\/$/, "");
  }
}

export function perkLimitedHint(perk, today = new Date()) {
  if (!perk || perk.status === "Expired") return "";
  const parsed = parsePerkDate(perk.valid_to);
  if (!parsed) return "";
  const remaining = daysUntil(parsed, today);
  if (remaining < 0) return "";
  if (remaining === 0) return "Today only";
  if (remaining <= LIMITED_DAYS) {
    const label = new Date(parsed.year, parsed.month - 1, parsed.day).toLocaleDateString("en-PH", {
      month: "short",
      day: "numeric",
    });
    return `Valid until ${label}`;
  }
  return "";
}

export function featuredAlumniPerk(perks, today = new Date()) {
  const ranked = (perks || [])
    .filter((row) => row && row.status === "Available")
    .map((row) => {
      const parsed = parsePerkDate(row.valid_to);
      return parsed ? { row, remaining: daysUntil(parsed, today) } : null;
    })
    .filter((item) => item && item.remaining >= 0 && item.remaining <= LIMITED_DAYS)
    .sort((a, b) => a.remaining - b.remaining);
  return ranked[0]?.row || null;
}

export function perkCategoryKey(category) {
  const value = String(category || "").toLowerCase();
  if (/coffee|cafe|café/.test(value)) return "coffee";
  if (/salon|parlor|beauty|barber/.test(value)) return "salon";
  if (/wellness|spa|fitness/.test(value)) return "wellness";
  if (/hotel|resort|lodging/.test(value)) return "hotel";
  if (/dining|restaurant|food/.test(value)) return "dining";
  if (/event/.test(value)) return "events";
  if (/campus|library/.test(value)) return "campus";
  if (/career|job/.test(value)) return "career";
  return "gift";
}
