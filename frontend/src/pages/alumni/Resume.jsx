import { useEffect, useState } from "react";
import { ChevronDownIcon, ChevronUpIcon, DownloadIcon, EyeIcon, PencilIcon, PlusIcon, TrashIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { Alert, PageSkeleton } from "../../components/ui";
import { api, downloadAuthorized } from "../../lib/api";
import { showToast } from "../../lib/toasts";
import { friendlyError } from "../../lib/userMessages";

const SECTION_LABELS = {
  summary: "Professional summary",
  experience: "Work experience",
  education: "Educational background",
  further_studies: "Further studies and additional qualifications",
  skills: "Skills",
  certifications: "Certifications and licenses",
  seminars: "Seminars and training",
  awards: "Awards and achievements",
  projects: "Projects",
  languages: "Languages",
};

const ENTRY_ADD = {
  experience: "a position",
  education: "a program",
  further_studies: "a program",
  certifications: "a certification",
  seminars: "a seminar",
  awards: "an award",
};

const ADDABLE = Object.keys(SECTION_LABELS);

const BLANKS = {
  summary: { type: "summary", text: "" },
  experience: { type: "experience", entries: [{ title: "", company: "", dates: "", location: "", description: "" }] },
  education: { type: "education", entries: [{ program: "", institution: "", detail: "" }] },
  further_studies: { type: "further_studies", entries: [{ program: "", institution: "", detail: "" }] },
  skills: { type: "skills", items: [""] },
  certifications: { type: "certifications", entries: [{ name: "", detail: "" }] },
  seminars: { type: "seminars", entries: [{ title: "", detail: "" }] },
  awards: { type: "awards", entries: [{ title: "", detail: "", description: "" }] },
  projects: { type: "projects", items: [""] },
  languages: { type: "languages", items: [""] },
};

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function withKeys(document) {
  return {
    ...document,
    sections: (document.sections || []).map((section) => {
      const next = { ...section, _key: uid() };
      if (Array.isArray(section.entries)) {
        next.entries = section.entries.map((entry) => ({ ...entry, _key: uid() }));
      }
      return next;
    }),
  };
}

function strip(document) {
  return {
    name: document.name || "",
    phone: document.phone || "",
    email: document.email || "",
    address: document.address || "",
    sections: (document.sections || []).map((section) => {
      if (section.type === "summary") return { type: section.type, text: section.text || "" };
      if (section.items) return { type: section.type, items: section.items };
      return {
        type: section.type,
        entries: (section.entries || []).map(({ _key, ...entry }) => entry),
      };
    }),
  };
}

function moveItem(list, index, direction) {
  const next = index + direction;
  if (next < 0 || next >= list.length) return list;
  const copy = list.slice();
  const [item] = copy.splice(index, 1);
  copy.splice(next, 0, item);
  return copy;
}

function Editable({ value, editing, onChange, className, label }) {
  if (!editing) {
    if (!value) return null;
    return <span className={className}>{value}</span>;
  }
  return (
    <span
      className={`resume-edit ${className || ""}`}
      contentEditable
      role="textbox"
      aria-label={label}
      spellCheck
      suppressContentEditableWarning
      onPaste={(event) => {
        event.preventDefault();
        const text = event.clipboardData.getData("text/plain");
        const selection = window.getSelection();
        if (!selection?.rangeCount) return;
        selection.deleteFromDocument();
        selection.getRangeAt(0).insertNode(document.createTextNode(text));
        selection.collapseToEnd();
        onChange(event.currentTarget.innerText || "");
      }}
      onInput={(event) => onChange(event.currentTarget.innerText || "")}
      ref={(node) => {
        if (node && document.activeElement !== node && node.textContent !== (value || "")) {
          node.textContent = value || "";
        }
      }}
    />
  );
}

function EntryTools({ editing, onUp, onDown, onDelete, upDisabled, downDisabled }) {
  if (!editing) return null;
  return (
    <div className="resume-entry-tools">
      <button type="button" aria-label="Move up" onClick={onUp} disabled={upDisabled}><ChevronUpIcon size={14} /></button>
      <button type="button" aria-label="Move down" onClick={onDown} disabled={downDisabled}><ChevronDownIcon size={14} /></button>
      <button type="button" aria-label="Remove" onClick={onDelete}><TrashIcon size={14} /></button>
    </div>
  );
}

export default function AlumniResume() {
  const [doc, setDoc] = useState(null);
  const [notices, setNotices] = useState([]);
  const [baseline, setBaseline] = useState("");
  const [editing, setEditing] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    api("/api/alumni/resume/document")
      .then((payload) => {
        const next = withKeys(payload.document || {});
        setDoc(next);
        setBaseline(JSON.stringify(strip(next)));
        setNotices(payload.notices || []);
      })
      .catch((err) => setError(friendlyError(err, "We couldn't prepare your resume. Please try again.")));
  }, []);

  const dirty = Boolean(doc) && JSON.stringify(strip(doc)) !== baseline;

  function update(next) {
    setDoc(next);
  }

  function updateHeader(field, value) {
    update({ ...doc, [field]: value });
  }

  function updateSection(index, section) {
    const sections = doc.sections.slice();
    sections[index] = section;
    update({ ...doc, sections });
  }

  function addSection(type) {
    if (!type || doc.sections.some((section) => section.type === type)) return;
    const blank = BLANKS[type];
    const section = blank.entries
      ? { ...blank, _key: uid(), entries: blank.entries.map((entry) => ({ ...entry, _key: uid() })) }
      : { ...blank, _key: uid(), items: [...(blank.items || [])], text: blank.text || "" };
    update({ ...doc, sections: [...doc.sections, section] });
    setEditing(true);
  }

  async function save() {
    setBusy("save");
    setError("");
    try {
      const payload = await api("/api/alumni/resume/document", { method: "PUT", body: strip(doc), toast: false });
      const next = withKeys(payload.document);
      setDoc(next);
      setBaseline(JSON.stringify(strip(next)));
      setNotices([]);
      showToast("success", "Your resume changes are saved.");
      return next;
    } catch (err) {
      setError(friendlyError(err, "We couldn't save your resume. Please try again."));
      return null;
    } finally {
      setBusy("");
    }
  }

  async function exportPdf() {
    if (busy) return;
    setBusy("export");
    setError("");
    try {
      if (dirty) {
        const saved = await api("/api/alumni/resume/document", { method: "PUT", body: strip(doc), toast: false });
        const next = withKeys(saved.document);
        setDoc(next);
        setBaseline(JSON.stringify(strip(next)));
      }
      const filename = `${String(doc.name || "Alumni").replace(/[^\w]+/g, "-").replace(/^-|-$/g, "") || "Alumni"}-Resume.pdf`;
      await downloadAuthorized("/api/alumni/resume/export", filename);
      showToast("success", "Your resume PDF is downloading.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't create your resume. Please try again."));
    } finally {
      setBusy("");
    }
  }

  if (!doc && !error) return <PortalShell role="Alumni"><PageSkeleton variant="alumni" /></PortalShell>;

  const present = new Set((doc?.sections || []).map((section) => section.type));
  const missing = ADDABLE.filter((type) => !present.has(type));

  return (
    <PortalShell role="Alumni">
      <div className="resume-studio">
        <Alert type="error">{error}</Alert>
        {notices.map((notice) => <Alert key={notice} type="info">{notice}</Alert>)}
        <div className="resume-toolbar">
          <p className="resume-toolbar-note">
            {editing ? "Select any text on the resume to change it." : "Preview shows the resume without editing controls."}
          </p>
          <div className="resume-toolbar-actions">
          <button type="button" className={`btn btn-sm ${editing ? "btn-navy" : "btn-outline"}`} onClick={() => setEditing(true)} disabled={!doc}>
            <PencilIcon size={15} /> Edit
          </button>
          <button type="button" className="btn btn-outline btn-sm" onClick={save} disabled={!doc || !dirty || busy === "save"}>
            {busy === "save" ? "Saving…" : "Save changes"}
          </button>
          <button type="button" className="btn btn-outline btn-sm" onClick={() => setEditing(false)} disabled={!doc}>
            <EyeIcon size={15} /> Preview
          </button>
          <button type="button" className="btn btn-navy btn-sm" onClick={exportPdf} disabled={!doc || Boolean(busy)}>
            <DownloadIcon size={15} /> {busy === "export" ? "Preparing PDF…" : "Export as PDF"}
          </button>
          </div>
        </div>
        {doc && gapNote(doc) ? <p className="resume-gaps">{gapNote(doc)}</p> : null}
        {doc && (
          <article className={`resume-sheet ${editing ? "is-editing" : ""}`} aria-label="Resume">
            <header className="resume-sheet-head">
              <Editable className="resume-sheet-name" value={doc.name} editing={editing} label="Name" onChange={(value) => updateHeader("name", value)} />
              <p className="resume-sheet-contact">
                <Editable value={doc.phone} editing={editing} label="Phone" onChange={(value) => updateHeader("phone", value)} />
                {(editing || (doc.phone && doc.email)) && <span className="resume-dot" aria-hidden="true"> · </span>}
                <Editable value={doc.email} editing={editing} label="Email" onChange={(value) => updateHeader("email", value)} />
                {(editing || ((doc.phone || doc.email) && doc.address)) && <span className="resume-dot" aria-hidden="true"> · </span>}
                <Editable value={doc.address} editing={editing} label="Address" onChange={(value) => updateHeader("address", value)} />
              </p>
            </header>
            {doc.sections.map((section, index) => (
              <ResumeSection
                key={section._key}
                section={section}
                editing={editing}
                canUp={index > 0}
                canDown={index < doc.sections.length - 1}
                onChange={(next) => updateSection(index, next)}
                onMove={(direction) => update({ ...doc, sections: moveItem(doc.sections, index, direction) })}
                onRemove={() => update({ ...doc, sections: doc.sections.filter((item) => item._key !== section._key) })}
              />
            ))}
            {editing && missing.length > 0 && (
              <label className="resume-add-section">
                Add a section
                <select value="" onChange={(event) => addSection(event.target.value)} aria-label="Add a section">
                  <option value="">Choose</option>
                  {missing.map((type) => <option key={type} value={type}>{SECTION_LABELS[type]}</option>)}
                </select>
              </label>
            )}
            {!editing && doc.sections.length === 0 && (
              <p className="resume-sheet-empty">Choose Edit to add the sections you want on this resume.</p>
            )}
          </article>
        )}
      </div>
    </PortalShell>
  );
}

function gapNote(document) {
  const gaps = [];
  if (!document.phone && !document.email && !document.address) gaps.push("contact details");
  const present = new Set((document.sections || []).map((section) => section.type));
  if (!present.has("summary")) gaps.push("a professional summary");
  if (!present.has("experience")) gaps.push("work experience");
  if (!present.has("education")) gaps.push("educational background");
  if (!gaps.length) return "";
  return `This draft has no ${gaps.join(", ")}. Add them on the resume if you want them included. Nothing is filled in for you.`;
}

function hasContent(section) {
  if (section.type === "summary") return Boolean(String(section.text || "").trim());
  if (section.items) return section.items.some((item) => String(item || "").trim());
  return (section.entries || []).some((entry) => Object.entries(entry).some(([key, value]) => key !== "_key" && String(value || "").trim()));
}

function ResumeSection({ section, editing, onChange, onMove, onRemove, canUp, canDown }) {
  if (!editing && !hasContent(section)) return null;
  const label = SECTION_LABELS[section.type] || "Section";
  return (
    <section className="resume-block">
      <div className="resume-block-head">
        <h2>{label}</h2>
        <EntryTools editing={editing} onUp={() => onMove(-1)} onDown={() => onMove(1)} onDelete={onRemove} upDisabled={!canUp} downDisabled={!canDown} />
      </div>
      {section.type === "summary" && (
        <Editable className="resume-summary" value={section.text} editing={editing} label="Professional summary" onChange={(text) => onChange({ ...section, text })} />
      )}
      {section.entries && section.entries.map((entry, index) => (
        <div className="resume-entry" key={entry._key}>
          <EntryTools
            editing={editing}
            onUp={() => onChange({ ...section, entries: moveItem(section.entries, index, -1) })}
            onDown={() => onChange({ ...section, entries: moveItem(section.entries, index, 1) })}
            onDelete={() => onChange({ ...section, entries: section.entries.filter((item) => item._key !== entry._key) })}
            upDisabled={index === 0}
            downDisabled={index === section.entries.length - 1}
          />
          <EntryBody entry={entry} type={section.type} editing={editing} onChange={(next) => {
            const entries = section.entries.slice();
            entries[index] = next;
            onChange({ ...section, entries });
          }} />
        </div>
      ))}
      {section.items && section.type === "projects" && section.items.map((item, index) => (
        <p className="resume-entry" key={`${section._key}-${index}`}>
          <Editable className="resume-body" value={item} editing={editing} label="Project" onChange={(value) => {
            const items = section.items.slice();
            items[index] = value;
            onChange({ ...section, items });
          }} />
          {editing && <button type="button" className="resume-inline-remove" aria-label="Remove project" onClick={() => onChange({ ...section, items: section.items.filter((_, itemIndex) => itemIndex !== index) })}><TrashIcon size={12} /></button>}
        </p>
      ))}
      {section.items && section.type !== "projects" && (
        <p className="resume-items">
          {section.items.map((item, index) => (
            <span className="resume-item" key={`${section._key}-${index}`}>
              {index > 0 && <span className="resume-dot" aria-hidden="true">, </span>}
              <Editable value={item} editing={editing} label={label} onChange={(value) => {
                const items = section.items.slice();
                items[index] = value;
                onChange({ ...section, items });
              }} />
              {editing && (
                <button type="button" aria-label={`Remove ${label}`} onClick={() => onChange({ ...section, items: section.items.filter((_, itemIndex) => itemIndex !== index) })}>
                  <TrashIcon size={12} />
                </button>
              )}
            </span>
          ))}
        </p>
      )}
      {editing && ENTRY_ADD[section.type] && (
        <button type="button" className="resume-add" onClick={() => onChange({ ...section, entries: [...(section.entries || []), { ...BLANKS[section.type].entries[0], _key: uid() }] })}>
          <PlusIcon size={14} /> Add {ENTRY_ADD[section.type] || "an entry"}
        </button>
      )}
      {editing && section.items && (
        <button type="button" className="resume-add" onClick={() => onChange({ ...section, items: [...section.items, ""] })}>
          <PlusIcon size={14} /> Add {section.type === "skills" ? "a skill" : section.type === "languages" ? "a language" : "a project"}
        </button>
      )}
    </section>
  );
}

function EntryBody({ entry, type, editing, onChange }) {
  const set = (field) => (value) => onChange({ ...entry, [field]: value });
  if (type === "experience") {
    return (
      <>
        <Editable className="resume-strong" value={entry.title} editing={editing} label="Job title" onChange={set("title")} />
        <Editable className="resume-body" value={entry.company} editing={editing} label="Company" onChange={set("company")} />
        <p className="resume-meta">
          <Editable value={entry.dates} editing={editing} label="Dates" onChange={set("dates")} />
          {(editing || (entry.dates && entry.location)) && <span className="resume-dot" aria-hidden="true"> · </span>}
          <Editable value={entry.location} editing={editing} label="Location" onChange={set("location")} />
        </p>
        <Editable className="resume-body" value={entry.description} editing={editing} label="Responsibilities" onChange={set("description")} />
      </>
    );
  }
  if (type === "education" || type === "further_studies") {
    return (
      <>
        <Editable className="resume-strong" value={entry.program} editing={editing} label="Program" onChange={set("program")} />
        <Editable className="resume-body" value={entry.institution} editing={editing} label="Institution" onChange={set("institution")} />
        <Editable className="resume-meta" value={entry.detail} editing={editing} label="Dates" onChange={set("detail")} />
      </>
    );
  }
  return (
    <>
      <Editable className="resume-strong" value={entry.title || entry.name} editing={editing} label="Title" onChange={set(entry.name !== undefined ? "name" : "title")} />
      <Editable className="resume-meta" value={entry.detail} editing={editing} label="Details" onChange={set("detail")} />
      {entry.description !== undefined && (
        <Editable className="resume-body" value={entry.description} editing={editing} label="Description" onChange={set("description")} />
      )}
    </>
  );
}
