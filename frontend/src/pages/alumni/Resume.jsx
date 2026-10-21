import { createContext, useContext, useEffect, useRef, useState } from "react";
import { ChevronDownIcon, ChevronUpIcon, DownloadIcon, EyeIcon, PencilIcon, PlusIcon, RedoIcon, TrashIcon, UndoIcon } from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { Alert } from "../../components/ui";
import { api, downloadAuthorized } from "../../lib/api";
import { showToast } from "../../lib/toasts";
import { friendlyError } from "../../lib/userMessages";

const SECTION_LABELS = {
  summary: "Professional Summary",
  experience: "Work Experience",
  education: "Educational Background",
  further_studies: "Further Studies and Additional Qualifications",
  skills: "Skills",
  certifications: "Certifications and Licenses",
  seminars: "Seminars and Training",
  awards: "Awards and Achievements",
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

const SECTION_GUIDE = [
  { type: "summary", label: "Professional Summary", description: "A brief introduction highlighting professional background, strengths, and career goals." },
  { type: "experience", label: "Work Experience", description: "Job titles, companies, employment dates, locations, and responsibilities." },
  { type: "education", label: "Educational Background", description: "Degree or program, institution, and graduation year or dates." },
  { type: "further_studies", label: "Further Studies and Additional Qualifications", description: "Additional academic programs and qualifications beyond the primary bachelor's degree." },
  { type: "skills", label: "Skills", description: "Professional, technical, and relevant personal skills." },
  { type: "certifications", label: "Certifications and Licenses", description: "Certification or license names and supporting details." },
  { type: "seminars", label: "Seminars and Training", description: "Seminar or training titles and relevant details." },
  { type: "awards", label: "Awards and Achievements", description: "Award titles, details, and descriptions." },
  { type: "projects", label: "Projects", description: "Relevant projects or work samples described in concise entries." },
  { type: "languages", label: "Languages", description: "Languages the alumnus can communicate in." },
];
const ADDABLE = SECTION_GUIDE.map((item) => item.type);
const HISTORY_LIMIT = 100;
const ResumeRevision = createContext(0);

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

function readText(node) {
  return (node.textContent || "").replace(/\u00a0/g, " ");
}

function placeCaret(node) {
  const range = document.createRange();
  range.selectNodeContents(node);
  range.collapse(false);
  const selection = window.getSelection();
  selection?.removeAllRanges();
  selection?.addRange(range);
}

function Editable({ value, editing, onChange, className, label, placeholder, maxLength, multiline = false }) {
  const revision = useContext(ResumeRevision);
  const text = String(value || "");
  if (!editing) {
    if (!text.trim()) return null;
    return <span className={className}>{text}</span>;
  }
  function commit(node, collapse) {
    let next = readText(node);
    if (maxLength && next.length > maxLength) {
      next = next.slice(0, maxLength);
      node.textContent = next;
      if (collapse) placeCaret(node);
    }
    onChange(next);
  }
  return (
    <span
      className={`resume-edit ${className || ""}`}
      contentEditable
      role="textbox"
      aria-label={label}
      aria-multiline={multiline ? "true" : "false"}
      data-placeholder={placeholder || ""}
      data-empty={text ? undefined : "true"}
      spellCheck
      suppressContentEditableWarning
      onKeyDown={(event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        if (!multiline) return;
        const selection = window.getSelection();
        if (!selection?.rangeCount) return;
        selection.deleteFromDocument();
        selection.getRangeAt(0).insertNode(document.createTextNode("\n"));
        selection.collapseToEnd();
        commit(event.currentTarget, false);
      }}
      onPaste={(event) => {
        event.preventDefault();
        const pasted = event.clipboardData.getData("text/plain");
        const selection = window.getSelection();
        if (!selection?.rangeCount) return;
        selection.deleteFromDocument();
        selection.getRangeAt(0).insertNode(document.createTextNode(multiline ? pasted : pasted.replace(/\s+/g, " ")));
        selection.collapseToEnd();
        commit(event.currentTarget, true);
      }}
      onInput={(event) => commit(event.currentTarget, true)}
      ref={(node) => {
        if (!node) return;
        const stamped = node.dataset.revision === String(revision);
        if (node.textContent === text && stamped) return;
        if (document.activeElement === node && stamped) return;
        const focused = document.activeElement === node;
        node.textContent = text;
        node.dataset.revision = String(revision);
        if (focused) placeCaret(node);
      }}
    />
  );
}

function dutyLines(value) {
  return String(value || "")
    .replace(/\r/g, "")
    .split(/\n+/)
    .map((line) => line.replace(/^[-•*]\s*/, "").trim())
    .filter(Boolean);
}

function Duties({ value, editing, onChange }) {
  if (editing) {
    return <Editable className="resume-body" value={value} editing multiline maxLength={2000} label="Responsibilities" placeholder="Responsibilities" onChange={onChange} />;
  }
  const lines = dutyLines(value);
  if (!lines.length) return null;
  if (lines.length === 1) return <span className="resume-body">{lines[0]}</span>;
  return (
    <ul className="resume-duties">
      {lines.map((line, index) => <li key={`${index}-${line}`}>{line}</li>)}
    </ul>
  );
}

function AddSectionMenu({ options, disabled, exhausted, onAdd }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const rootRef = useRef(null);
  const buttonRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    function onPointer(event) {
      if (!rootRef.current?.contains(event.target)) setOpen(false);
    }
    function onKey(event) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      buttonRef.current?.focus();
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const optionKey = options.map((option) => option.type).join("|");

  useEffect(() => {
    if (!open) return;
    const panel = rootRef.current?.querySelector(".resume-add-menu-panel");
    const button = buttonRef.current;
    if (!panel || !button) return;
    const rect = button.getBoundingClientRect();
    const spaceRight = window.innerWidth - rect.left - 12;
    const spaceLeft = rect.right - 12;
    const alignRight = spaceRight < 320 && spaceLeft > spaceRight;
    const available = Math.max(220, Math.min(380, alignRight ? spaceLeft : spaceRight));
    panel.classList.toggle("is-right", alignRight);
    panel.style.width = `${available}px`;
  }, [open, optionKey]);

  useEffect(() => {
    if (!open) return;
    if (!options.length) {
      setOpen(false);
      return;
    }
    const next = Math.min(active, options.length - 1);
    if (next !== active) {
      setActive(next);
      return;
    }
    rootRef.current?.querySelectorAll("[role='menuitem']")[next]?.focus({ preventScroll: true });
  }, [open, active, optionKey, options.length]);

  function toggle() {
    if (disabled) return;
    setActive(0);
    setOpen((value) => !value);
  }

  function choose(type) {
    setOpen(false);
    onAdd(type);
  }

  function onMenuKey(event) {
    if (!options.length) return;
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActive((index) => (index + 1) % options.length);
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActive((index) => (index - 1 + options.length) % options.length);
    } else if (event.key === "Home") {
      event.preventDefault();
      setActive(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActive(options.length - 1);
    }
  }

  return (
    <div className="resume-add-menu" ref={rootRef}>
      <button
        type="button"
        className="btn btn-outline btn-sm resume-add-menu-button"
        ref={buttonRef}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls="resume-add-menu"
        aria-describedby={exhausted ? "resume-add-menu-note" : undefined}
        onClick={toggle}
        disabled={disabled}
      >
        Add a Section
        <ChevronDownIcon size={14} />
      </button>
      {open && options.length > 0 ? (
        <div id="resume-add-menu" className="resume-add-menu-panel" role="menu" aria-label="Add a Resume Section" onKeyDown={onMenuKey}>
          <div className="resume-add-menu-head">
            <strong>Add a Resume Section</strong>
            <p>Choose a section to add to your resume.</p>
          </div>
          <div className="resume-add-menu-list">
            {options.map((option, index) => (
              <button
                type="button"
                role="menuitem"
                key={option.type}
                className={index === active ? "is-active" : ""}
                onMouseEnter={() => setActive(index)}
                onClick={() => choose(option.type)}
              >
                <span className="resume-add-menu-copy">
                  <strong>{option.label}</strong>
                  <span>{option.description}</span>
                </span>
                <span className="resume-add-menu-action">Add</span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
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
  const [persisted, setPersisted] = useState(false);
  const [editing, setEditing] = useState(true);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const [loadId, setLoadId] = useState(0);
  const [steps, setSteps] = useState({ undo: 0, redo: 0 });
  const [revision, setRevision] = useState(0);
  const [focusKey, setFocusKey] = useState("");
  const pastRef = useRef([]);
  const futureRef = useRef([]);

  function publishHistory() {
    setSteps({ undo: pastRef.current.length, redo: futureRef.current.length });
  }

  function resetHistory() {
    pastRef.current = [];
    futureRef.current = [];
    publishHistory();
    setRevision(0);
  }

  useEffect(() => {
    let cancelled = false;
    setError("");
    api("/api/alumni/resume/document")
      .then((payload) => {
        if (cancelled) return;
        const next = withKeys(payload.document || {});
        setDoc(next);
        setBaseline(JSON.stringify(strip(next)));
        setPersisted(Boolean(payload.saved));
        setNotices(payload.notices || []);
        resetHistory();
      })
      .catch((err) => {
        if (!cancelled) setError(friendlyError(err, "We couldn't prepare your resume. Please try again."));
      });
    return () => {
      cancelled = true;
    };
  }, [loadId]);

  const dirty = Boolean(doc) && JSON.stringify(strip(doc)) !== baseline;

  function update(next) {
    if (doc && JSON.stringify(strip(doc)) !== JSON.stringify(strip(next))) {
      pastRef.current.push(doc);
      if (pastRef.current.length > HISTORY_LIMIT) pastRef.current.shift();
      futureRef.current = [];
      publishHistory();
    }
    setDoc(next);
  }

  function undo() {
    const previous = pastRef.current.pop();
    if (!previous || !doc) {
      if (previous) pastRef.current.push(previous);
      return;
    }
    futureRef.current.push(doc);
    setDoc(previous);
    setRevision((value) => value + 1);
    publishHistory();
  }

  function redo() {
    const next = futureRef.current.pop();
    if (!next || !doc) {
      if (next) futureRef.current.push(next);
      return;
    }
    pastRef.current.push(doc);
    setDoc(next);
    setRevision((value) => value + 1);
    publishHistory();
  }

  function onStudioKeyDown(event) {
    const key = event.key.toLowerCase();
    const modified = event.ctrlKey || event.metaKey;
    if (!modified || busy) return;
    if (key === "z") {
      event.preventDefault();
      if (event.shiftKey) redo();
      else undo();
    } else if (key === "y") {
      event.preventDefault();
      redo();
    }
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
    const key = uid();
    const section = blank.entries
      ? { ...blank, _key: key, entries: blank.entries.map((entry) => ({ ...entry, _key: uid() })) }
      : { ...blank, _key: key, items: [...(blank.items || [])], text: blank.text || "" };
    const sections = doc.sections.slice();
    const rank = ADDABLE.indexOf(type);
    const insertAt = sections.findIndex((item) => ADDABLE.indexOf(item.type) > rank);
    sections.splice(insertAt < 0 ? sections.length : insertAt, 0, section);
    update({ ...doc, sections });
    setEditing(true);
    setFocusKey(key);
  }

  async function save() {
    setBusy("save");
    setError("");
    try {
      const payload = await api("/api/alumni/resume/document", { method: "PUT", body: strip(doc), toast: false });
      const next = withKeys(payload.document);
      setDoc(next);
      setBaseline(JSON.stringify(strip(next)));
      setPersisted(true);
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
      let source = doc;
      if (dirty) {
        const saved = await api("/api/alumni/resume/document", { method: "PUT", body: strip(doc), toast: false });
        source = withKeys(saved.document);
        setDoc(source);
        setBaseline(JSON.stringify(strip(source)));
        setPersisted(true);
      }
      const filename = `${String(source.name || "Alumni").replace(/[^\w]+/g, "-").replace(/^-|-$/g, "") || "Alumni"}-Resume.pdf`;
      await downloadAuthorized("/api/alumni/resume/export", filename);
      showToast("success", "Your resume PDF is downloading.");
    } catch (err) {
      setError(friendlyError(err, "We couldn't create your resume. Please try again."));
    } finally {
      setBusy("");
    }
  }

  if (!doc && !error) {
    return (
      <PortalShell role="Alumni">
        <ResumeSkeleton />
      </PortalShell>
    );
  }

  const present = new Set((doc?.sections || []).map((section) => section.type));
  const missing = ADDABLE.filter((type) => !present.has(type));
  const available = SECTION_GUIDE.filter((item) => missing.includes(item.type));
  const status = !doc ? "" : dirty ? "Unsaved changes" : persisted ? "All changes saved" : "Not saved yet";

  return (
    <PortalShell role="Alumni">
      <div className="resume-studio" onKeyDown={onStudioKeyDown}>
        <header className="resume-page-head">
          <h1>Extract Resume</h1>
          <p className="lead">Build, edit, and export your professional resume using your saved profile and readable uploaded resume files.</p>
        </header>
        {doc ? <Alert type="error">{error}</Alert> : null}
        {notices.map((notice) => <Alert key={notice} type="info">{notice}</Alert>)}
        <div className="resume-toolbar">
          <div className="resume-toolbar-lead">
            <div className="resume-mode" role="group" aria-label="Resume view">
              <button type="button" className={editing ? "on" : ""} aria-pressed={editing} onClick={() => setEditing(true)} disabled={!doc}>
                <PencilIcon size={15} /> Edit
              </button>
              <button type="button" className={!editing ? "on" : ""} aria-pressed={!editing} onClick={() => setEditing(false)} disabled={!doc}>
                <EyeIcon size={15} /> Preview
              </button>
            </div>
            <div className="resume-history" role="group" aria-label="Edit history">
              <button type="button" className="btn btn-outline btn-sm" onClick={undo} disabled={!doc || steps.undo === 0 || Boolean(busy)} aria-label="Undo">
                <UndoIcon size={15} /> Undo
              </button>
              <button type="button" className="btn btn-outline btn-sm" onClick={redo} disabled={!doc || steps.redo === 0 || Boolean(busy)} aria-label="Redo">
                <RedoIcon size={15} /> Redo
              </button>
            </div>
          </div>
          <div className="resume-toolbar-actions">
            <AddSectionMenu
              options={available}
              disabled={!doc || missing.length === 0}
              exhausted={Boolean(doc) && missing.length === 0}
              onAdd={addSection}
            />
            <button type="button" className="btn btn-outline btn-sm" onClick={save} disabled={!doc || !dirty || busy === "save"}>
              {busy === "save" ? "Saving…" : "Save Changes"}
            </button>
            <button type="button" className="btn btn-navy btn-sm" onClick={exportPdf} disabled={!doc || Boolean(busy)}>
              <DownloadIcon size={15} /> {busy === "export" ? "Preparing PDF…" : "Export as PDF"}
            </button>
          </div>
          <p className="resume-toolbar-note">
            <span className="resume-toolbar-hint">
              <span className={editing ? "is-on" : ""} aria-hidden={editing ? undefined : true}>Select any text on the resume to change it.</span>
              <span className={editing ? "" : "is-on"} aria-hidden={editing ? true : undefined}>Preview shows the resume without editing controls.</span>
            </span>
            {status ? <span className={dirty ? "is-dirty" : persisted ? "is-saved" : ""}>{status}</span> : null}
            {Boolean(doc) && missing.length === 0 ? (
              <span id="resume-add-menu-note" className="resume-add-menu-note">All available resume sections have been added.</span>
            ) : null}
          </p>
        </div>
        {!doc && error ? (
          <section className="resume-load-error" role="alert">
            <h2>Unable to open your resume.</h2>
            <p>Please try again.</p>
            <button type="button" className="btn btn-navy" onClick={() => setLoadId((value) => value + 1)}>Retry</button>
          </section>
        ) : null}
        {doc && gapNote(doc) ? <p className="resume-gaps">{gapNote(doc)}</p> : null}
        {doc && (
          <ResumeRevision.Provider value={revision}>
          <article className={`resume-sheet ${editing ? "is-editing" : ""}`} aria-label="Resume">
            {(editing || [doc.name, doc.phone, doc.email, doc.address].some((value) => String(value || "").trim())) && (
            <header className="resume-sheet-head">
              <Editable className="resume-sheet-name" value={doc.name} editing={editing} label="Name" placeholder="Full name" maxLength={160} onChange={(value) => updateHeader("name", value)} />
              <ContactLine doc={doc} editing={editing} onChange={updateHeader} />
            </header>
            )}
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
                focusRequest={section._key === focusKey}
                onFocusHandled={() => setFocusKey("")}
              />
            ))}
            {!editing && doc.sections.every((section) => !hasContent(section)) && (
              <p className="resume-sheet-empty">Choose Edit to add the sections you want on this resume.</p>
            )}
          </article>
          </ResumeRevision.Provider>
        )}
      </div>
    </PortalShell>
  );
}

function ContactLine({ doc, editing, onChange }) {
  const fields = [
    ["phone", "Phone", doc.phone],
    ["email", "Email", doc.email],
    ["address", "Address", doc.address],
  ];
  const visible = editing ? fields : fields.filter(([, , value]) => String(value || "").trim());
  if (!visible.length) return null;
  return (
    <p className="resume-sheet-contact">
      {visible.map(([field, label, value], index) => (
        <span key={field}>
          {index > 0 ? <span className="resume-dot" aria-hidden="true"> · </span> : null}
          <Editable value={value} editing={editing} label={label} placeholder={label} maxLength={field === "phone" ? 40 : field === "email" ? 255 : 300} onChange={(next) => onChange(field, next)} />
        </span>
      ))}
    </p>
  );
}

function ResumeSkeleton() {
  return (
    <div className="resume-studio" aria-hidden="true">
      <div className="resume-page-head">
        <div className="skeleton resume-skel-title" />
        <div className="skeleton resume-skel-lead" />
      </div>
      <div className="skeleton resume-skel-toolbar" />
      <div className="resume-sheet">
        <div className="skeleton resume-skel-name" />
        <div className="skeleton resume-skel-contact" />
        <div className="skeleton resume-skel-heading" />
        <div className="skeleton resume-skel-line" />
        <div className="skeleton resume-skel-line is-short" />
        <div className="skeleton resume-skel-heading" />
        <div className="skeleton resume-skel-line" />
        <div className="skeleton resume-skel-line is-mid" />
      </div>
    </div>
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

function entryHasContent(entry) {
  return Object.entries(entry).some(([key, value]) => key !== "_key" && String(value || "").trim());
}

function ResumeSection({ section, editing, onChange, onMove, onRemove, canUp, canDown, focusRequest, onFocusHandled }) {
  const rootRef = useRef(null);
  const handledRef = useRef(onFocusHandled);
  handledRef.current = onFocusHandled;
  useEffect(() => {
    if (!focusRequest) return;
    const field = rootRef.current?.querySelector(".resume-edit");
    if (field) {
      field.classList.add("is-start");
      field.focus({ preventScroll: true });
      field.scrollIntoView({ block: "nearest", behavior: "smooth" });
      const clear = () => field.classList.remove("is-start");
      field.addEventListener("input", clear, { once: true });
      field.addEventListener("blur", clear, { once: true });
    }
    handledRef.current();
  }, [focusRequest]);
  if (!editing && !hasContent(section)) return null;
  const label = SECTION_LABELS[section.type] || "Section";
  const items = section.items
    ? (editing ? section.items : section.items.filter((item) => String(item || "").trim()))
    : [];
  return (
    <section className="resume-block" ref={rootRef}>
      <div className="resume-block-head">
        <h2>{label}</h2>
        <EntryTools editing={editing} onUp={() => onMove(-1)} onDown={() => onMove(1)} onDelete={onRemove} upDisabled={!canUp} downDisabled={!canDown} />
      </div>
      {section.type === "summary" && (
        <Editable className="resume-summary" value={section.text} editing={editing} multiline maxLength={2000} label="Professional summary" placeholder="Your background, strengths, and goals" onChange={(text) => onChange({ ...section, text: String(text || "").slice(0, 2000) })} />
      )}
      {section.entries && section.entries.map((entry, index) => {
        if (!editing && !entryHasContent(entry)) return null;
        return (
          <div className="resume-entry" key={entry._key}>
            <div className="resume-entry-body">
              <EntryBody entry={entry} type={section.type} editing={editing} onChange={(next) => {
                const entries = section.entries.slice();
                entries[index] = next;
                onChange({ ...section, entries });
              }} />
            </div>
            <EntryTools
              editing={editing}
              onUp={() => onChange({ ...section, entries: moveItem(section.entries, index, -1) })}
              onDown={() => onChange({ ...section, entries: moveItem(section.entries, index, 1) })}
              onDelete={() => onChange({ ...section, entries: section.entries.filter((item) => item._key !== entry._key) })}
              upDisabled={index === 0}
              downDisabled={index === section.entries.length - 1}
            />
          </div>
        );
      })}
      {section.type === "projects" && section.items.map((item, index) => {
        if (!editing && !String(item || "").trim()) return null;
        return (
          <div className="resume-entry" key={`${section._key}-${index}`}>
            <div className="resume-entry-body">
              <Editable className="resume-body" value={item} editing={editing} maxLength={200} label="Project" placeholder="Project name or description" onChange={(value) => {
                const next = section.items.slice();
                next[index] = value;
                onChange({ ...section, items: next });
              }} />
            </div>
            <EntryTools
              editing={editing}
              onUp={() => onChange({ ...section, items: moveItem(section.items, index, -1) })}
              onDown={() => onChange({ ...section, items: moveItem(section.items, index, 1) })}
              onDelete={() => onChange({ ...section, items: section.items.filter((_, itemIndex) => itemIndex !== index) })}
              upDisabled={index === 0}
              downDisabled={index === section.items.length - 1}
            />
          </div>
        );
      })}
      {section.items && section.type !== "projects" && (
        <p className="resume-items">
          {items.map((item, index) => (
            <span className="resume-item" key={`${section._key}-${index}`}>
              {index > 0 && <span className="resume-dot" aria-hidden="true">, </span>}
              <Editable value={item} editing={editing} maxLength={200} label={section.type === "skills" ? "Skill" : "Language"} placeholder={section.type === "skills" ? "A professional or technical skill" : "Language"} onChange={(value) => {
                const source = editing ? section.items : items;
                const next = source.slice();
                next[index] = value;
                onChange({ ...section, items: next });
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
        <Editable className="resume-strong" value={entry.title} editing={editing} label="Job title" placeholder="Job title" maxLength={200} onChange={set("title")} />
        <Editable className="resume-org" value={entry.company} editing={editing} label="Company" placeholder="Company" maxLength={200} onChange={set("company")} />
        {(editing || entry.dates || entry.location) && (
          <p className="resume-meta">
            <Editable value={entry.dates} editing={editing} label="Dates" placeholder="Dates" maxLength={200} onChange={set("dates")} />
            {(editing || (entry.dates && entry.location)) && <span className="resume-dot" aria-hidden="true"> · </span>}
            <Editable value={entry.location} editing={editing} label="Location" placeholder="Location" maxLength={200} onChange={set("location")} />
          </p>
        )}
        <Duties value={entry.description} editing={editing} onChange={set("description")} />
      </>
    );
  }
  if (type === "education" || type === "further_studies") {
    return (
      <>
        <Editable className="resume-strong" value={entry.program} editing={editing} label={type === "education" ? "Degree or program" : "Program or qualification"} placeholder={type === "education" ? "Degree or program" : "Program or qualification"} maxLength={200} onChange={set("program")} />
        <Editable className="resume-org" value={entry.institution} editing={editing} label="Institution" placeholder="Institution" maxLength={200} onChange={set("institution")} />
        <Editable className="resume-meta" value={entry.detail} editing={editing} label="Dates" placeholder={type === "education" ? "Graduation year or dates" : "Enrollment or completion dates"} maxLength={500} onChange={set("detail")} />
      </>
    );
  }
  const copy = {
    certifications: { title: "Certification or license", detail: "Issuing body and date" },
    seminars: { title: "Seminar or training", detail: "Organizer, place, or date" },
    awards: { title: "Award title", detail: "Issuer and date", description: "What it recognizes" },
  }[type] || { title: "Title", detail: "Details", description: "Description" };
  return (
    <>
      <Editable className="resume-strong" value={entry.title || entry.name} editing={editing} label={copy.title} placeholder={copy.title} maxLength={200} onChange={set(entry.name !== undefined ? "name" : "title")} />
      <Editable className="resume-meta" value={entry.detail} editing={editing} label={copy.detail} placeholder={copy.detail} maxLength={500} onChange={set("detail")} />
      {entry.description !== undefined && (
        <Editable className="resume-body" value={entry.description} editing={editing} multiline maxLength={2000} label={copy.description} placeholder={copy.description} onChange={set("description")} />
      )}
    </>
  );
}
