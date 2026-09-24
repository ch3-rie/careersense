import { useEffect, useMemo, useState } from "react";
import { PortalShell } from "../../components/Layout";
import {
  PerksDirectory,
  PerksDisclaimer,
  PerksHeader,
  PerksSkeleton,
} from "../../components/PerksDirectory";
import { Alert, Dialog, LoadError } from "../../components/ui";
import { api } from "../../lib/api";
import { filterAlumniPerks } from "../../lib/perkFilters";
import { showToast } from "../../lib/toasts";
import { friendlyError } from "../../lib/userMessages";

const STATUS_ORDER = { Available: 0, Locked: 1, Used: 2, Expired: 3 };

export default function AlumniPerksPage() {
  const [perks, setPerks] = useState(null);
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [category, setCategory] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [pending, setPending] = useState(null);
  const [claimed, setClaimed] = useState(null);

  function loadPerks() {
    setError("");
    return api("/api/alumni/perks").then((data) => setPerks(data.perks || []));
  }

  useEffect(() => {
    loadPerks().catch((err) => setError(friendlyError(err, "We couldn't load the available perks right now.")));
  }, []);

  const categories = useMemo(
    () => [...new Set((perks || []).map((row) => row.category).filter(Boolean))].sort(),
    [perks]
  );

  const filtered = useMemo(() => {
    return filterAlumniPerks(perks || [], { query, status, category }).sort(
      (a, b) => (STATUS_ORDER[a.status] ?? 9) - (STATUS_ORDER[b.status] ?? 9)
    );
  }, [perks, query, status, category]);

  async function claimPerk(perk) {
    setBusyId(perk.id);
    setError("");
    try {
      const result = await api(`/api/alumni/perks/${perk.id}/claim`, { method: "POST" });
      const next = result.perks || [];
      setPerks(next);
      const updated = next.find((row) => row.id === perk.id);
      setPending(null);
      setClaimed(updated || perk);
      showToast("success", "Perk claimed successfully.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't claim this perk. Please try again."));
      setPending(null);
    } finally {
      setBusyId(null);
    }
  }

  if (!perks && !error) {
    return (
      <PortalShell role="Alumni">
        <PerksSkeleton />
      </PortalShell>
    );
  }

  const noSourcePerks = !(perks || []).length;
  const filtersActive = Boolean(query || status || category);

  return (
    <PortalShell role="Alumni">
      <Alert type="error">{error}</Alert>
      {!perks && error ? (
        <LoadError title="We couldn't load the available perks right now." onRetry={() => loadPerks().catch((err) => setError(friendlyError(err, "We couldn't load the available perks right now.")))}>
          Please try again.
        </LoadError>
      ) : (
        <article className="perks-directory">
          <div className="perk-dir-top">
            <PerksHeader />
            {!noSourcePerks ? (
              <div className="perk-dir-filter-block">
                <button
                  type="button"
                  className="perk-dir-filter-toggle"
                  aria-expanded={filtersOpen}
                  onClick={() => setFiltersOpen((open) => !open)}
                >
                  Search and filter
                </button>
                <div className={`perk-dir-filters${filtersOpen ? " is-open" : ""}`}>
                  <label className="sr-only" htmlFor="perk-search">Search perks</label>
                  <input
                    id="perk-search"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Search partner, offer, or category"
                  />
                  <label className="sr-only" htmlFor="perk-status">Filter by status</label>
                  <select id="perk-status" value={status} onChange={(e) => setStatus(e.target.value)}>
                    <option value="">All statuses</option>
                    <option value="Available">Available</option>
                    <option value="Locked">Requires AAC</option>
                    <option value="Used">Claimed</option>
                    <option value="Expired">Expired</option>
                  </select>
                  {categories.length ? (
                    <>
                      <label className="sr-only" htmlFor="perk-category">Filter by category</label>
                      <select id="perk-category" value={category} onChange={(e) => setCategory(e.target.value)}>
                        <option value="">All categories</option>
                        {categories.map((item) => (
                          <option key={item} value={item}>{item}</option>
                        ))}
                      </select>
                    </>
                  ) : null}
                </div>
              </div>
            ) : null}
          </div>
          <PerksDirectory
            perks={filtered}
            onClaim={setPending}
            busyId={busyId}
            emptyTitle={noSourcePerks ? "No perks and discounts are currently available." : "No matching perks"}
            emptyHint={
              noSourcePerks
                ? "Check back later for new partner offers."
                : "Try a different search or status, or check back later for new partner offers."
            }
          />
          {filtersActive && perks?.length && !filtered.length ? (
            <p className="empty-action">
              <button
                type="button"
                className="btn btn-outline btn-sm"
                onClick={() => {
                  setQuery("");
                  setStatus("");
                  setCategory("");
                }}
              >
                Clear filters
              </button>
            </p>
          ) : null}
          <PerksDisclaimer />
        </article>
      )}

      {pending ? (
        <Dialog
          title="Claim this perk?"
          confirmLabel={busyId === pending.id ? "Claiming…" : "Claim perk"}
          busy={Boolean(busyId)}
          onConfirm={() => claimPerk(pending)}
          onClose={() => { if (!busyId) setPending(null); }}
        >
          <p>
            A unique claim code will be generated for {pending.partner || pending.name}. Partner terms still apply, and this perk can only be claimed once.
          </p>
        </Dialog>
      ) : null}

      {claimed ? (
        <Dialog
          title="Perk claimed successfully"
          confirmLabel="Done"
          onConfirm={() => setClaimed(null)}
          onClose={() => setClaimed(null)}
        >
          <p>{claimed.name || claimed.discount}</p>
          {claimed.code ? (
            <p className="perk-code-hero">
              <span>Your claim code</span>
              <strong>{claimed.code}</strong>
            </p>
          ) : (
            <p>Your perk is now marked as claimed.</p>
          )}
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
