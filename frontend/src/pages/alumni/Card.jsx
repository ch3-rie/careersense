import { useEffect, useState } from "react";
import { MonthCalendar, dateFromIso, formatCalendarDate } from "../../components/AacCalendar";
import { Link } from "react-router-dom";
import {
  AlumniCardPreview,
  ProfilePhoto,
} from "../../components/AlumniProfileExtras";
import { DigitalAlumniCard } from "../../components/AngeleneanCard";
import { AacStatus } from "../../components/AlumniChrome";
import { PortalShell } from "../../components/Layout";
import { Alert, Dialog, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDate, formatDateTime, fullName } from "../../lib/format";
import { showToast } from "../../lib/toasts";
import { friendlyError } from "../../lib/userMessages";

const PLACEHOLDERS = {
  birthday: "Please provide your date of birth",
  phone: "Please provide your mobile number",
  home_address: "Please provide your home address",
};

function fieldMap(prefill) {
  return Object.fromEntries((prefill || []).map((field) => [field.key, field]));
}

function formFromPayload(payload) {
  const fields = fieldMap(payload?.prefill);
  const renew = payload?.card?.status === "ForRenewal";
  return {
    birthday: fields.birthday?.value || "",
    phone: fields.phone?.value || "",
    mailing_address: fields.home_address?.value || "",
    city: payload?.contact?.city || "",
    country_residence: payload?.contact?.country_residence || "Philippines",
    company_affiliation: fields.company_affiliation?.value || "",
    position: fields.position?.value || "",
    membership_type: renew ? "Renewal" : "New",
    pickup_acknowledged: true,
    appointment_date: "",
    appointment_time: "",
  };
}

function displayValue(field, form) {
  if (!field) return "";
  if (field.key === "birthday") return form.birthday;
  if (field.key === "phone") return form.phone;
  if (field.key === "home_address") return form.mailing_address;
  if (field.key === "company_affiliation") return form.company_affiliation;
  if (field.key === "position") return form.position;
  return field.value || "";
}

function OriginMark({ status }) {
  if (status === "needed") return <span className="aac-origin is-needed">Please complete</span>;
  if (status === "appointment") return <span className="aac-origin">Select appointment</span>;
  return <span className="aac-origin">Automatically filled</span>;
}

export default function AlumniCardPage() {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(formFromPayload(null));
  const [photoSrc, setPhotoSrc] = useState("");
  const [previewOpen, setPreviewOpen] = useState(false);
  const [formStarted, setFormStarted] = useState(false);
  const [confirmSubmit, setConfirmSubmit] = useState(false);
  const [calMonth, setCalMonth] = useState(() => new Date());

  useEffect(() => {
    api("/api/alumni/card")
      .then((payload) => {
        setData(payload);
        setForm(formFromPayload(payload));
        const first = dateFromIso(payload?.appointments?.[0]?.date);
        if (first) setCalMonth(first);
      })
      .catch((err) => setError(friendlyError(err, "We couldn't load your alumni card status. Please try again.")));
  }, []);

  useEffect(() => {
    if (!data?.identity?.has_photo) {
      setPhotoSrc("");
      return undefined;
    }
    let url = "";
    let cancelled = false;
    api("/api/alumni/profile/photo", { blob: true })
      .then((blob) => {
        if (cancelled || !(blob instanceof Blob)) return;
        url = URL.createObjectURL(blob);
        setPhotoSrc(url);
      })
      .catch(() => {
        if (!cancelled) setPhotoSrc("");
      });
    return () => {
      cancelled = true;
      if (url) URL.revokeObjectURL(url);
    };
  }, [data?.identity?.has_photo]);

  async function submitRequest() {
    setBusy(true);
    setError("");
    try {
      const payload = await api("/api/alumni/card/apply", { method: "POST", body: form });
      setData(payload);
      setFormStarted(false);
      setConfirmSubmit(false);
      showToast("success", "AAC application submitted. AAPS will review your application.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't submit your AAC application. Please review the form and try again."));
      setConfirmSubmit(false);
    } finally {
      setBusy(false);
    }
  }

  if (!data && !error) return <PortalShell role="Alumni"><PageSkeleton variant="alumni" /></PortalShell>;

  const card = data?.card || {};
  const identity = data?.identity || {};
  const office = data?.office || {};
  const steps = data?.steps || [];
  const prefill = data?.prefill || [];
  const appointments = data?.appointments || [];
  const selectedDay = appointments.find((day) => day.date === form.appointment_date);
  const name = fullName(identity);
  const waiting = card.status === "ForVerification" || card.status === "Approved";

  const claimed = card.status === "Claimed";

  return (
    <PortalShell role="Alumni">
      <div className="aac-page">
      <Alert type="error">{error && !confirmSubmit ? error : null}</Alert>
      {!data && error ? (
        <p className="muted">Please try again later, or reload this page.</p>
      ) : null}

      {data && (
        <>
          <section className="aac-status-panel" aria-labelledby="aac-status-title">
            <h1 id="aac-status-title">Alumni Card Status</h1>
            <AacStatus card={card} compact />
          </section>

          <section className="aac-card-stage" aria-label="Digital alumni card">
            <DigitalAlumniCard identity={identity} card={card} photoSrc={photoSrc} />
          </section>

          <section className="card aac-details" aria-labelledby="aac-info-title">
            <h2 id="aac-info-title">Card information</h2>
            <dl className="aac-facts">
              <div>
                <dt>Card status</dt>
                <dd>{card.label || "—"}</dd>
              </div>
              <div>
                <dt>Card holder</dt>
                <dd>{name}</dd>
              </div>
              <div>
                <dt>Alumni ID</dt>
                <dd>{identity.student_number || identity.student_id || "—"}</dd>
              </div>
              <div>
                <dt>Degree</dt>
                <dd>{identity.degree || "—"}</dd>
              </div>
              <div>
                <dt>Batch</dt>
                <dd>{identity.year_graduated || "—"}</dd>
              </div>
              {card.card_number ? (
                <div>
                  <dt>Card number</dt>
                  <dd>{card.card_number}</dd>
                </div>
              ) : null}
              {card.expires_at ? (
                <div>
                  <dt>Valid until</dt>
                  <dd>{formatDate(card.expires_at)}</dd>
                </div>
              ) : null}
            </dl>

            {!formStarted ? (
              <div className="aac-next">
                <h3>{card.headline}</h3>
                {card.next_action ? <p>{card.next_action}</p> : null}
                {card.can_apply ? (
                  <p className="muted">
                    The AAC is your official AUF alumni membership card. Use it for AAPS services, library access, and partner discounts.
                  </p>
                ) : null}
                {waiting ? (
                  <p>
                    {card.status === "Approved"
                      ? "Your AAC has been approved. Your card is currently being prepared."
                      : "AAPS is currently verifying your alumni information. You do not need to submit another application."}
                    {card.submitted_at ? ` Submitted ${formatDateTime(card.submitted_at)}.` : ""}
                  </p>
                ) : null}
                {card.membership_type ? (
                  <dl className="aac-facts">
                    <div>
                      <dt>Membership type</dt>
                      <dd>{card.membership_type}</dd>
                    </div>
                  </dl>
                ) : null}
                {card.show_pickup ? (
                  <div className="pickup-box is-emphasis" id="aac-pickup" aria-label="Pickup instructions">
                    <strong>Pickup location</strong>
                    <p>{office.name || "Alumni Affairs and Placement Services (AAPS)"}</p>
                    <p>{office.location || card.pickup_location}</p>
                    {office.hours ? <p><strong>Office hours</strong><br />{office.hours}</p> : null}
                    {office.phone ? <p><strong>Phone</strong><br />{office.phone}</p> : null}
                    <p>{office.bring || "Bring a valid government-issued ID that matches the name on your card."}</p>
                  </div>
                ) : null}
                {card.status !== "ForRenewal" ? (
                  <div className="aac-progress">
                    <p className="aac-progress-label">Application progress</p>
                    <ol className="lifecycle-track" aria-label="Angelenean Alumni Card progress">
                      {steps.map((item, index) => (
                        <li
                          key={item.id}
                          className={`${index === card.step_index ? "on" : ""} ${index < card.step_index ? "done" : ""}`}
                        >
                          <span className="track-bar" />
                          <span>{index + 1}. {item.label === "Not yet applied" ? "Application" : item.label === "For verification" ? "Verification" : item.label}</span>
                        </li>
                      ))}
                    </ol>
                  </div>
                ) : null}
                {waiting ? (
                  <p className="profile-note">Watch Notifications for the next status. You do not need to resubmit.</p>
                ) : null}
                {card.can_apply ? (
                  <button type="button" className="btn btn-navy" onClick={() => setFormStarted(true)}>
                    {card.status === "ForRenewal" ? "Apply for Renewal" : "Get Alumni Card"}
                  </button>
                ) : null}
                {card.gts_completed === false && (card.status === "NotYetApplied" || card.status === "ForRenewal") ? (
                  <p className="profile-note">
                    Submit the <Link to="/alumni/resume">Graduate Tracer Survey</Link> first. The alumni card is available after that, whether you are employed, unemployed, or continuing your studies.
                  </p>
                ) : null}
                {claimed ? (
                  <button type="button" className="btn btn-outline" onClick={() => setPreviewOpen(true)}>
                    Card details
                  </button>
                ) : null}
              </div>
            ) : null}
          </section>

          {card.can_apply && formStarted ? (
            <section className="card profile-section" aria-label="AAC application">
              <header className="profile-section-head">
                <div>
                  <h2>{card.status === "ForRenewal" ? "Renewal application" : "Get Alumni Card"}</h2>
                </div>
              </header>
              <p className="muted">Information already on your record is filled in. Add only what is missing, then choose an OAAPS appointment.</p>
              <div className="aac-review-head">
                <ProfilePhoto profile={identity} src={photoSrc} size="sm" />
                <h3>Review your information</h3>
              </div>
              <dl className="aac-facts aac-review">
                    {prefill.map((field) => {
                      const value = displayValue(field, form);
                      const needed = field.required && !String(value || "").trim();
                      const editable = !field.locked && (field.key === "birthday" || field.key === "phone" || field.key === "home_address");
                      return (
                        <div key={field.key}>
                          <dt>
                            {field.label}
                            {field.required ? <span aria-hidden="true"> *</span> : null}
                          </dt>
                          <dd>
                            <OriginMark status={needed ? "needed" : "filled"} />
                            {editable ? (
                              field.key === "home_address" ? (
                                <textarea
                                  rows={3}
                                  value={form.mailing_address}
                                  placeholder={PLACEHOLDERS.home_address}
                                  maxLength={240}
                                  aria-label={field.label}
                                  onChange={(event) => setForm({ ...form, mailing_address: event.target.value })}
                                />
                              ) : (
                                <input
                                  type={field.key === "birthday" ? "date" : "text"}
                                  value={field.key === "birthday" ? form.birthday : form.phone}
                                  placeholder={PLACEHOLDERS[field.key]}
                                  maxLength={field.key === "phone" ? 40 : undefined}
                                  aria-label={field.label}
                                  onChange={(event) => setForm({
                                    ...form,
                                    [field.key === "birthday" ? "birthday" : "phone"]: event.target.value,
                                  })}
                                />
                              )
                            ) : (
                              <span>{value || "—"}</span>
                            )}
                          </dd>
                        </div>
                      );
                    })}
              </dl>
              <div className="aac-appointment">
                <h3>Preferred AAC appointment <span aria-hidden="true">*</span></h3>
                <OriginMark status="appointment" />
                {!appointments.length ? (
                  <p className="profile-note">OAAPS has not published appointment times yet. Check again when dates are available.</p>
                ) : (
                  <div className="aac-cal-layout">
                    <MonthCalendar
                      month={calMonth}
                      onMonth={setCalMonth}
                      selected={form.appointment_date}
                      onSelect={(iso) => setForm({ ...form, appointment_date: iso, appointment_time: "" })}
                      marks={Object.fromEntries(appointments.map((day) => [day.date, { label: "available" }]))}
                      isSelectable={(iso) => appointments.some((day) => day.date === iso)}
                      ariaLabel="Preferred AAC appointment date"
                    />
                    <div className="aac-day-panel">
                      <h3>{selectedDay ? formatCalendarDate(selectedDay.date) : "Available times"}</h3>
                      {selectedDay ? (
                        <div className="aac-time-picks" role="group" aria-label="Preferred AAC appointment time">
                          {selectedDay.times.map((slot) => (
                            <button
                              key={slot.time}
                              type="button"
                              className={form.appointment_time === slot.time ? "is-selected" : ""}
                              aria-pressed={form.appointment_time === slot.time}
                              onClick={() => setForm({ ...form, appointment_time: slot.time })}
                            >
                              {slot.time}
                            </button>
                          ))}
                        </div>
                      ) : (
                        <p className="muted aac-day-placeholder">Choose an open date on the calendar.</p>
                      )}
                    </div>
                  </div>
                )}
              </div>
              {!identity.has_photo ? (
                <p className="profile-note">Add a photo on <Link to="/alumni">Home</Link> so AAPS can print it on the card.</p>
              ) : null}
              <div className="form-nav">
                <button type="button" className="btn btn-outline" onClick={() => setFormStarted(false)}>Back</button>
                <button
                  type="button"
                  className="btn btn-navy"
                  disabled={busy || !appointments.length}
                  onClick={() => {
                    if (!form.birthday || !form.phone.trim() || form.mailing_address.trim().length < 8) {
                      setError("Date of birth, mobile number, and home address are required.");
                      return;
                    }
                    if (!form.appointment_date || !form.appointment_time) {
                      setError("Select an available OAAPS appointment date and time.");
                      return;
                    }
                    setError("");
                    setConfirmSubmit(true);
                  }}
                >
                  Submit
                </button>
              </div>
            </section>
          ) : null}
        </>
      )}
      </div>

      {confirmSubmit ? (
        <Dialog
          title="Submit AAC application?"
          confirmLabel={busy ? "Submitting…" : "Submit application"}
          busy={busy}
          onConfirm={submitRequest}
          onClose={() => { if (!busy) setConfirmSubmit(false); }}
        >
          <Alert type="error">{error}</Alert>
          <p>AAPS will review the information from your record and the appointment you selected. You will be notified when your card is ready.</p>
        </Dialog>
      ) : null}

      <AlumniCardPreview
        profile={identity}
        user={{ student_id: identity.student_number || identity.student_id }}
        card={card}
        photoSrc={photoSrc}
        open={previewOpen}
        onClose={() => setPreviewOpen(false)}
      />
    </PortalShell>
  );
}
