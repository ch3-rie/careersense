import { useState } from "react";
import { Link } from "react-router-dom";
import { AuthImage } from "./AlumniChrome";
import {
  BedIcon,
  BriefcaseIcon,
  CalendarIcon,
  CoffeeIcon,
  ExternalLinkIcon,
  GiftIcon,
  GraduationIcon,
  InfoIcon,
  LockIcon,
  ScissorsIcon,
  SparklesIcon,
  UtensilsIcon,
} from "./icons";
import { Badge, Dialog, Empty } from "./ui";
import { formatDate } from "../lib/format";
import {
  parsePerkOffer,
  perkCategoryKey,
  perkLimitedHint,
  perkWebsiteLabel,
} from "../lib/perkDisplay";
import { safeHttpUrl } from "../lib/safeUrl";

function CategoryGlyph({ category, size = 14 }) {
  const key = perkCategoryKey(category);
  if (key === "coffee") return <CoffeeIcon size={size} />;
  if (key === "salon") return <ScissorsIcon size={size} />;
  if (key === "wellness") return <SparklesIcon size={size} />;
  if (key === "hotel") return <BedIcon size={size} />;
  if (key === "dining") return <UtensilsIcon size={size} />;
  if (key === "events") return <CalendarIcon size={size} />;
  if (key === "campus") return <GraduationIcon size={size} />;
  if (key === "career") return <BriefcaseIcon size={size} />;
  return <GiftIcon size={size} />;
}

function PartnerLogo({ perk }) {
  const name = perk.partner || perk.name || "Partner";
  return (
    <div className="perk-dir-logo">
      <span className="perk-dir-logo-fallback" aria-hidden="true">
        <CategoryGlyph category={perk.category} size={22} />
      </span>
      {perk.has_image && perk.image_url ? (
        <AuthImage
          src={perk.image_url}
          alt={`${name} photo`}
          className="perk-dir-logo-img"
          loading="lazy"
        />
      ) : null}
    </div>
  );
}

function DiscountDisplay({ perk }) {
  const offer = parsePerkOffer(perk.discount || perk.name);
  const hint = perkLimitedHint(perk);
  return (
    <div className={`perk-dir-offer is-${offer.kind}${perk.status === "Expired" ? " is-expired" : ""}`}>
      {offer.kind === "percent" || offer.kind === "amount" ? (
        <>
          <span className="perk-dir-offer-kicker">Discount</span>
          <strong className="perk-dir-offer-value">{offer.value}</strong>
          {offer.suffix ? <span className="perk-dir-offer-suffix">{offer.suffix}</span> : null}
        </>
      ) : (
        <>
          <span className="perk-dir-offer-kicker">Offer</span>
          <strong className="perk-dir-offer-text">{offer.value}</strong>
        </>
      )}
      {hint ? <span className="perk-dir-offer-hint">{hint}</span> : null}
    </div>
  );
}

function statusLabel(perk) {
  if (perk.status === "Locked") return "Requires AAC";
  if (perk.status === "Used") return "Claimed";
  if (perk.status === "Expired") return "Expired";
  return "";
}

function perkTone(status) {
  if (status === "Available") return "aligned";
  if (status === "Used") return "unknown";
  if (status === "Expired") return "rejected";
  return "pending";
}

function ExternalPerkLink({ url }) {
  const href = safeHttpUrl(url);
  if (!href) return null;
  const label = perkWebsiteLabel(href);
  return (
    <a className="perk-dir-link" href={href} target="_blank" rel="noopener noreferrer">
      <span>{label}</span>
      <ExternalLinkIcon size={13} />
    </a>
  );
}

export function PerksHeader() {
  return (
    <header className="perk-dir-head">
      <span className="perk-dir-head-icon" aria-hidden="true">
        <GiftIcon size={22} />
      </span>
      <div>
        <h1>Perks & Discounts</h1>
        <p>Enjoy exclusive discounts from our partner establishments.</p>
      </div>
    </header>
  );
}

export function PerksDisclaimer() {
  return (
    <p className="perk-dir-disclaimer">
      <InfoIcon size={14} />
      Discounts are available to eligible CareerSense alumni. Partner terms and Angelenean Alumni Card requirements may apply.
    </p>
  );
}

function PerkAction({ perk, onOpen }) {
  return (
    <button type="button" className="btn btn-perk" onClick={() => onOpen(perk)}>
      View<span className="perk-cta-rest"> Details</span>
    </button>
  );
}

function PerkCard({ perk, onOpen }) {
  const partner = perk.partner || perk.name || "Partner";
  const description = String(perk.description || perk.eligibility || "").trim();
  const label = statusLabel(perk);
  return (
    <article className={`perk-dir-card is-${String(perk.status || "").toLowerCase()}`}>
      <PartnerLogo perk={perk} />
      <div className="perk-dir-body">
        <div className="perk-dir-meta">
          <p className="perk-dir-category">
            <CategoryGlyph category={perk.category} />
            {perk.category || "Partner offer"}
          </p>
          {label ? <span className={`perk-dir-status is-${String(perk.status).toLowerCase()}`}>{label}</span> : null}
        </div>
        <h2 className="perk-dir-name">{partner}</h2>
        {description ? <p className="perk-dir-desc">{description}</p> : null}
        <ExternalPerkLink url={perk.website} />
        {perk.status === "Locked" ? (
          <p className="perk-lock">
            <LockIcon size={14} /> Available after your AAC is ready
          </p>
        ) : null}
      </div>
      <div className="perk-dir-side">
        <DiscountDisplay perk={perk} />
        <PerkAction perk={perk} onOpen={onOpen} />
      </div>
    </article>
  );
}

export function PerksSkeleton() {
  return (
    <div className="perks-directory" aria-hidden="true">
      <div className="perk-dir-top">
        <div className="perk-dir-head">
          <span className="skeleton" style={{ width: 36, height: 36, borderRadius: 10 }} />
          <div>
            <div className="skeleton" style={{ width: 220, height: 24 }} />
            <div className="skeleton" style={{ width: 280, height: 12, marginTop: 8 }} />
          </div>
        </div>
      </div>
      <ul className="perk-dir-list">
        {Array.from({ length: 4 }, (_, index) => (
          <li key={index} className="perk-dir-card is-skeleton">
            <span className="skeleton perk-dir-logo" />
            <div className="perk-dir-body">
              <div className="skeleton" style={{ width: 90, height: 10 }} />
              <div className="skeleton" style={{ width: "70%", height: 16, marginTop: 8 }} />
              <div className="skeleton" style={{ width: "90%", height: 12, marginTop: 8 }} />
            </div>
            <div className="perk-dir-side">
              <div className="skeleton" style={{ width: 56, height: 36 }} />
              <div className="skeleton" style={{ width: 92, height: 32, borderRadius: 999 }} />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function PerksDirectory({
  perks = [],
  onClaim,
  busyId,
  emptyTitle = "No perks and discounts are currently available.",
  emptyHint = "Check back later for new partner offers.",
}) {
  const [detail, setDetail] = useState(null);

  function openPerk(perk) {
    setDetail(perk);
  }

  return (
    <>
      {!perks.length ? (
        <Empty title={emptyTitle}>{emptyHint}</Empty>
      ) : (
        <ul className="perk-dir-list">
          {perks.map((perk) => (
            <li key={perk.id}>
              <PerkCard perk={perk} onOpen={openPerk} />
            </li>
          ))}
        </ul>
      )}
      {detail ? (
        <Dialog
          title={detail.partner || detail.name || "Perk details"}
          confirmLabel={detail.status === "Available" ? (busyId === detail.id ? "Claiming…" : "Claim perk") : "Close"}
          busy={Boolean(busyId)}
          onConfirm={() => {
            if (detail.status === "Available") {
              const perk = detail;
              setDetail(null);
              onClaim(perk);
            } else {
              setDetail(null);
            }
          }}
          onClose={() => { if (!busyId) setDetail(null); }}
        >
          {detail.has_image && detail.image_url ? (
            <AuthImage src={detail.image_url} alt="" className="perk-dir-detail-img" />
          ) : null}
          <p className="perk-offer">{detail.discount || detail.name}</p>
          <p>
            <Badge tone={perkTone(detail.status)}>{detail.status === "Locked" ? "Requires AAC" : detail.status === "Used" ? "Claimed" : detail.status}</Badge>
          </p>
          {detail.category ? <p className="perk-category">{detail.category}</p> : null}
          {detail.description && detail.description !== detail.discount ? <p>{detail.description}</p> : null}
          <ExternalPerkLink url={detail.website} />
          {detail.eligibility ? <p className="perk-terms"><strong>Eligibility.</strong> {detail.eligibility}</p> : null}
          {detail.terms || detail.how_to_claim ? (
            <p className="perk-terms"><strong>How to use.</strong> {detail.terms || detail.how_to_claim}</p>
          ) : null}
          {detail.valid_from || detail.valid_to ? (
            <p className="muted">
              {detail.valid_from && detail.valid_to
                ? `Valid ${formatDate(detail.valid_from)} – ${formatDate(detail.valid_to)}`
                : detail.valid_to
                  ? `Valid until ${formatDate(detail.valid_to)}`
                  : `Available from ${formatDate(detail.valid_from)}`}
            </p>
          ) : null}
          {detail.status === "Used" && detail.code ? (
            <p className="perk-code-hero">
              <span>Your claim code</span>
              <strong>{detail.code}</strong>
            </p>
          ) : null}
          {detail.status === "Locked" ? (
            <p className="perk-lock">
              <LockIcon size={14} /> Available after your AAC is ready. <Link to="/alumni/card">Review your card</Link>
            </p>
          ) : null}
        </Dialog>
      ) : null}
    </>
  );
}
