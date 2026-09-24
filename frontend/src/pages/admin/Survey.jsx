import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useSearchParams } from "react-router-dom";
import { openAdminTab } from "../../components/AdminReview";
import GtsForm from "../../components/GtsForm";
import {
  ChevronDownIcon,
  ChevronUpIcon,
  CopyIcon,
  ExternalLinkIcon,
  EyeIcon,
  GripIcon,
  LayersIcon,
  PencilIcon,
  PlusIcon,
  TrashIcon,
} from "../../components/icons";
import { PortalShell } from "../../components/Layout";
import { Alert, Badge, Dialog, Empty, Field, LoadError, PageHeader, PageSkeleton } from "../../components/ui";
import { api } from "../../lib/api";
import { formatDateTime, questionTypeLabel } from "../../lib/format";
import { notifyPublishedSurvey } from "../../lib/surveyLive";
import { showToast } from "../../lib/toasts";
import {
  ALIGNMENT_FIELD_KEYS,
  CHOICE_TYPES,
  CORE_SECTION_KEYS,
  QUESTION_TYPES,
  SYSTEM_FIELD_KEYS,
  cloneSurvey,
  createQuestion,
  createSection,
  duplicateQuestion,
  findQuestionLocation,
  findSectionLocation,
  flattenQuestions,
  moveItem,
  optionsForType,
  optionLabel,
  optionText,
  optionValue,
  questionIndex,
  schemaIssues,
  systemWarning,
  visibilitySummary,
  wouldCreateCycle,
} from "../../lib/surveySchema";

const PREVIEW_SEED = {};
const TEXT_TYPES = new Set(["short_answer", "paragraph", "email"]);

function patchAt(schema, locator, question) {
  const next = cloneSurvey(schema);
  next.sections[locator.sectionIndex].subsections[locator.subsectionIndex].questions[locator.questionIndex] = question;
  return next;
}

function parseDrag(event) {
  const raw = event.dataTransfer.getData("application/json");
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

function defaultValueText(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (value == null) return "";
  return String(value);
}

function numericScaleBounds(options) {
  const values = (options || []).map(optionValue).filter((item) => /^\d+$/.test(item)).map(Number);
  if (!values.length) return { min: 1, max: 5 };
  return { min: Math.min(...values), max: Math.max(...values) };
}

function scaleOptions(min, max) {
  const start = Number(min);
  const end = Number(max);
  if (!Number.isFinite(start) || !Number.isFinite(end) || end < start) return ["1", "2", "3", "4", "5"];
  const size = Math.min(11, Math.max(2, Math.round(end) - Math.round(start) + 1));
  return Array.from({ length: size }, (_, index) => String(Math.round(start) + index));
}

function isSystemQuestion(question) {
  const key = question?.field_key || question?.id;
  return Boolean(question?.system || SYSTEM_FIELD_KEYS.has(key) || ALIGNMENT_FIELD_KEYS.has(key) || question?.type === "repeatable_group");
}

function optionKey(opt) {
  return typeof opt === "object" ? opt.value || opt.label : opt;
}

function parentOptions(question) {
  if (!question) return [];
  if (question.type === "yes_no") return ["Yes", "No"];
  return (question.options || []).map((item) => optionValue(item)).filter(Boolean);
}

export default function AdminSurvey() {
  const [searchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [draft, setDraft] = useState(null);
  const [error, setError] = useState("");
  const [saveState, setSaveState] = useState("idle");
  const [selectedKind, setSelectedKind] = useState("header");
  const [selectedId, setSelectedId] = useState("header");
  const [expanded, setExpanded] = useState({});
  const [workspaceMode, setWorkspaceMode] = useState("edit");
  const [addMenu, setAddMenu] = useState(null);
  const [dropHint, setDropHint] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleteSectionTarget, setDeleteSectionTarget] = useState(null);
  const [moveTarget, setMoveTarget] = useState(null);
  const [moveDest, setMoveDest] = useState("");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [publishWarnings, setPublishWarnings] = useState(null);
  const [typeWarn, setTypeWarn] = useState(null);
  const [conditionOpen, setConditionOpen] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionBusy, setActionBusy] = useState("");
  const saveTimer = useRef(null);
  const skipSave = useRef(true);
  const persistLock = useRef(false);
  const draftRef = useRef(null);
  const deleteLock = useRef(false);
  const addLock = useRef(false);

  const byId = useMemo(() => questionIndex(draft), [draft]);
  const issues = useMemo(() => schemaIssues(draft), [draft]);
  const addableTypes = data?.addable_types || QUESTION_TYPES.map((item) => item[0]);

  function selectQuestion(id) {
    setSelectedKind("question");
    setSelectedId(id);
    setWorkspaceMode("edit");
    setAddMenu(null);
  }

  function selectSection(id) {
    setSelectedKind("section");
    setSelectedId(id);
    setWorkspaceMode("edit");
    setAddMenu(null);
  }

  function selectHeader() {
    setSelectedKind("header");
    setSelectedId("header");
    setWorkspaceMode("edit");
  }

  async function load() {
    setError("");
    try {
      const result = await api("/api/admin/survey");
      setData(result);
      const next = cloneSurvey(result.draft);
      setDraft(next);
      draftRef.current = next;
      skipSave.current = true;
      const questionId = new URLSearchParams(window.location.search).get("question");
      const sectionId = new URLSearchParams(window.location.search).get("section");
      if (questionId && findQuestionLocation(next, questionId)) {
        setSelectedKind("question");
        setSelectedId(questionId);
      } else if (sectionId && findSectionLocation(next, sectionId)) {
        setSelectedKind("section");
        setSelectedId(sectionId);
      } else {
        setSelectedKind("header");
        setSelectedId("header");
      }
      const open = {};
      (result.draft?.sections || []).forEach((section) => { open[section.id] = true; });
      setExpanded(open);
    } catch (err) {
      setError(err.message);
      showToast("error", err.message || "Unable to load the survey.");
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (!draft) return undefined;
    const questionId = searchParams.get("question");
    const sectionId = searchParams.get("section");
    if (questionId) {
      const loc = findQuestionLocation(draft, questionId);
      if (loc) {
        setExpanded((prev) => ({ ...prev, [loc.section.id]: true }));
        setSelectedKind("question");
        setSelectedId(questionId);
        setWorkspaceMode("edit");
      }
    } else if (sectionId) {
      const loc = findSectionLocation(draft, sectionId);
      if (loc) {
        setExpanded((prev) => ({ ...prev, [sectionId]: true }));
        setSelectedKind("section");
        setSelectedId(sectionId);
        setWorkspaceMode("edit");
      }
    }
    return undefined;
  }, [searchParams, draft ? 1 : 0]);

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);

  useEffect(() => {
    if (!addMenu) return undefined;
    function close(event) {
      if (!event.target.closest(".gform-type-menu, .gform-type-popover")) setAddMenu(null);
    }
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [addMenu]);

  useEffect(() => {
    function onKey(event) {
      if (event.key === "Escape") {
        setAddMenu(null);
        setDropHint(null);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const persist = useCallback(async (schema, auto = true, options = {}) => {
    if (!schema) return false;
    if (persistLock.current && auto) return false;
    const start = Date.now();
    while (persistLock.current && Date.now() - start < 8000) {
      await new Promise((resolve) => window.setTimeout(resolve, 50));
    }
    if (persistLock.current) return false;
    persistLock.current = true;
    setSaveState("saving");
    try {
      const result = await api("/api/admin/survey/draft", { method: "PUT", body: { schema, auto }, toast: false });
      setData(result);
      if (!auto) {
        skipSave.current = true;
        if (result.draft) {
          const next = cloneSurvey(result.draft);
          setDraft(next);
          draftRef.current = next;
        }
        if (options.toast !== false) showToast("success", result.message || "Survey draft saved successfully.");
      } else if (JSON.stringify(draftRef.current) !== JSON.stringify(schema)) {
        setSaveState("unsaved");
        return true;
      }
      setSaveState("saved");
      return true;
    } catch (err) {
      setSaveState("error");
      showToast("error", err.message || "Unable to save the survey. Please try again.");
      return false;
    } finally {
      persistLock.current = false;
    }
  }, []);

  useEffect(() => {
    if (!draft || skipSave.current) {
      skipSave.current = false;
      return undefined;
    }
    setSaveState("unsaved");
    window.clearTimeout(saveTimer.current);
    if (schemaIssues(draft).length) return undefined;
    saveTimer.current = window.setTimeout(() => persist(draft, true), 1200);
    return () => window.clearTimeout(saveTimer.current);
  }, [draft, persist]);

  function updateDraft(next) {
    setDraft(next);
  }

  function updateQuestionById(questionId, partial) {
    const locator = findQuestionLocation(draft, questionId);
    if (!locator) return;
    updateDraft(patchAt(draft, locator, { ...locator.question, ...partial }));
  }

  function updateSectionById(sectionId, partial) {
    const loc = findSectionLocation(draft, sectionId);
    if (!loc) return;
    const next = cloneSurvey(draft);
    next.sections[loc.sectionIndex] = { ...next.sections[loc.sectionIndex], ...partial };
    updateDraft(next);
  }

  function addQuestion(sectionIndex, subsectionIndex, type = "short_answer") {
    if (addLock.current || !draft) return;
    addLock.current = true;
    const section = draft.sections[sectionIndex];
    const subIndex = subsectionIndex ?? Math.max(0, (section.subsections || []).length - 1);
    const question = createQuestion({
      label: "Untitled question",
      type,
      options: optionsForType(type),
    });
    const next = cloneSurvey(draft);
    next.sections[sectionIndex].subsections[subIndex].questions.push(question);
    updateDraft(next);
    selectQuestion(question.id);
    setAddMenu(null);
    addLock.current = false;
    showToast("info", "Question added to the draft.");
  }

  function addQuestionNearSelection(type = "short_answer") {
    if (!draft?.sections?.length) return;
    if (selectedKind === "question") {
      const loc = findQuestionLocation(draft, selectedId);
      if (loc) {
        addQuestion(loc.sectionIndex, loc.subsectionIndex, type);
        return;
      }
    }
    if (selectedKind === "section") {
      const loc = findSectionLocation(draft, selectedId);
      if (loc) {
        addQuestion(loc.sectionIndex, undefined, type);
        return;
      }
    }
    addQuestion(draft.sections.length - 1, undefined, type);
  }

  function addNewSection() {
    if (!draft) return;
    const section = createSection({ name: "Untitled section" });
    const next = cloneSurvey(draft);
    next.sections.push(section);
    updateDraft(next);
    setExpanded((prev) => ({ ...prev, [section.id]: true }));
    selectSection(section.id);
    setWorkspaceMode("edit");
    showToast("info", "Section added to the draft.");
  }

  function applyDelete() {
    if (!deleteTarget || deleteLock.current) return;
    deleteLock.current = true;
    setActionBusy("delete");
    const locator = findQuestionLocation(draft, deleteTarget.id);
    if (!locator) {
      setDeleteTarget(null);
      deleteLock.current = false;
      setActionBusy("");
      return;
    }
    const next = cloneSurvey(draft);
    next.sections[locator.sectionIndex].subsections[locator.subsectionIndex].questions.splice(locator.questionIndex, 1);
    updateDraft(next);
    if (selectedId === deleteTarget.id) selectHeader();
    setDeleteTarget(null);
    showToast("success", "Question deleted from the draft. Historical answers stay on existing tracer records.");
    deleteLock.current = false;
    setActionBusy("");
  }

  function applyDeleteSection() {
    if (!deleteSectionTarget) return;
    if (CORE_SECTION_KEYS.includes(deleteSectionTarget.key)) {
      showToast("error", "The four main GTS sections cannot be removed.");
      setDeleteSectionTarget(null);
      return;
    }
    const next = cloneSurvey(draft);
    next.sections = next.sections.filter((section) => section.id !== deleteSectionTarget.id);
    updateDraft(next);
    selectHeader();
    setDeleteSectionTarget(null);
    showToast("success", "Section removed from the draft.");
  }

  function applyDuplicate(question) {
    const locator = findQuestionLocation(draft, question.id);
    if (!locator) return;
    const copy = duplicateQuestion(question);
    const next = cloneSurvey(draft);
    next.sections[locator.sectionIndex].subsections[locator.subsectionIndex].questions.splice(locator.questionIndex + 1, 0, copy);
    updateDraft(next);
    selectQuestion(copy.id);
    showToast("info", "Question duplicated in the draft.");
  }

  function applyMove() {
    if (!moveTarget) return;
    const [sectionId, subsectionId] = String(moveDest || "").split("::");
    const locator = findQuestionLocation(draft, moveTarget.id);
    if (!locator || !sectionId) return;
    const next = cloneSurvey(draft);
    const destSection = next.sections.findIndex((section) => section.id === sectionId);
    if (destSection < 0) return;
    const destSub = next.sections[destSection].subsections.findIndex((sub) => sub.id === subsectionId);
    if (destSub < 0) return;
    const [question] = next.sections[locator.sectionIndex].subsections[locator.subsectionIndex].questions.splice(locator.questionIndex, 1);
    next.sections[destSection].subsections[destSub].questions.push(question);
    updateDraft(next);
    setMoveTarget(null);
    selectQuestion(question.id);
    showToast("info", "Question moved.");
  }

  function moveQuestion(questionId, delta) {
    const locator = findQuestionLocation(draft, questionId);
    if (!locator) return;
    const questions = draft.sections[locator.sectionIndex].subsections[locator.subsectionIndex].questions;
    const dest = locator.questionIndex + delta;
    if (dest < 0 || dest >= questions.length) return;
    const next = cloneSurvey(draft);
    next.sections[locator.sectionIndex].subsections[locator.subsectionIndex].questions = moveItem(questions, locator.questionIndex, dest);
    updateDraft(next);
  }

  function moveSection(sectionId, delta) {
    const locator = findSectionLocation(draft, sectionId);
    if (!locator) return;
    const dest = locator.sectionIndex + delta;
    if (dest < 0 || dest >= draft.sections.length) return;
    const next = cloneSurvey(draft);
    next.sections = moveItem(next.sections, locator.sectionIndex, dest);
    updateDraft(next);
  }

  function onDropQuestion(event, destSection, destSub, destIndex) {
    event.preventDefault();
    event.stopPropagation();
    const source = parseDrag(event);
    setDropHint(null);
    if (!source || source.kind !== "question") return;
    const next = cloneSurvey(draft);
    const list = next.sections[source.s]?.subsections[source.b]?.questions;
    if (!list) return;
    const [question] = list.splice(source.q, 1);
    if (!question) return;
    let insertAt = destIndex;
    if (source.s === destSection && source.b === destSub && source.q < destIndex) insertAt -= 1;
    next.sections[destSection].subsections[destSub].questions.splice(Math.max(0, insertAt), 0, question);
    updateDraft(next);
    selectQuestion(question.id);
  }

  function onDropSection(event, destIndex) {
    event.preventDefault();
    event.stopPropagation();
    const source = parseDrag(event);
    setDropHint(null);
    if (!source || source.kind !== "section") return;
    const next = cloneSurvey(draft);
    next.sections = moveItem(next.sections, source.s, destIndex);
    updateDraft(next);
  }

  async function saveNow() {
    if (busy || saveState === "saving") return;
    if (issues.length) {
      showToast("warning", `${issues[0]} Save Draft is blocked until this is fixed.`);
      return;
    }
    window.clearTimeout(saveTimer.current);
    await persist(draft, false);
  }

  async function publish(confirmImpact = false) {
    if (busy) return;
    if (issues.length) {
      showToast("warning", `${issues[0]} Publish is blocked until this is fixed.`);
      return;
    }
    setBusy(true);
    window.clearTimeout(saveTimer.current);
    try {
      const saved = await persist(draft, false, { toast: false });
      if (!saved) return;
      const current = draftRef.current;
      const result = await api("/api/admin/survey/publish", { method: "POST", body: { confirm_impact: confirmImpact }, toast: false });
      skipSave.current = true;
      setData(result);
      setDraft(cloneSurvey(result.draft));
      setPublishWarnings(null);
      const unchanged = result.published_version === data?.published_version && !result.dirty;
      const alreadyLive = unchanged && JSON.stringify(current) === JSON.stringify(result.published);
      showToast(
        alreadyLive ? "info" : "success",
        alreadyLive ? "Published version is already up to date." : (result.message || "Survey published successfully. Changes are now live.")
      );
      setSaveState("saved");
      notifyPublishedSurvey(result.published_version);
    } catch (err) {
      const detail = err.payload?.detail;
      if (err.status === 409 && detail?.warnings) {
        setPublishWarnings(detail.warnings);
      } else {
        showToast("error", err.message || "Unable to publish the survey.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function saveSettings(event) {
    event.preventDefault();
    if (busy) return;
    const form = new FormData(event.target);
    setBusy(true);
    try {
      const result = await api("/api/admin/survey/settings", {
        method: "PUT",
        toast: false,
        body: {
          title: form.get("title"),
          description: form.get("description"),
          intro: form.get("intro"),
          confirmation_message: form.get("confirmation_message"),
          accepting_responses: form.get("accepting_responses") === "on",
          allow_alumni_edit: form.get("allow_alumni_edit") === "on",
          start_date: form.get("start_date") || null,
          end_date: form.get("end_date") || null,
        },
      });
      skipSave.current = true;
      setData(result);
      setDraft(cloneSurvey(result.draft));
      setSettingsOpen(false);
      showToast("success", "Survey settings updated.");
      setSaveState("saved");
      notifyPublishedSurvey(result.published_version);
    } catch (err) {
      showToast("error", err.message || "Unable to update survey settings.");
    } finally {
      setBusy(false);
    }
  }

  async function restoreVersion(version) {
    if (busy) return;
    setBusy(true);
    try {
      const result = await api(`/api/admin/survey/versions/${version}/restore`, { method: "POST", toast: false });
      skipSave.current = true;
      setData(result);
      setDraft(cloneSurvey(result.draft));
      setVersionsOpen(false);
      showToast("success", result.message || "Version restored to draft.");
      setSaveState("unsaved");
    } catch (err) {
      showToast("error", err.message || "Unable to restore that survey version.");
    } finally {
      setBusy(false);
    }
  }

  function requestTypeChange(question, nextType) {
    if (nextType === question.type) return;
    const warning = systemWarning(question);
    const apply = () => updateQuestionById(question.id, { type: nextType, options: optionsForType(nextType, question.options) });
    if (warning) {
      setTypeWarn({ warning, apply });
      return;
    }
    apply();
  }

  if (!draft && !error) return <PortalShell role="Admin"><PageSkeleton /></PortalShell>;

  const saveLabel = saveState === "saving"
    ? "Saving..."
    : saveState === "saved"
      ? "All changes saved"
      : saveState === "unsaved"
        ? "Unsaved changes"
        : saveState === "error"
          ? "Unable to save changes. Please try again."
          : "";
  const statusLabel = saveState === "unsaved" || saveState === "error" ? "Unsaved changes" : data?.dirty ? "Draft" : "Published";
  const saveBusy = busy || saveState === "saving";
  const publisher = data?.versions?.[0]?.published_by;
  const selectedQuestion = selectedKind === "question" ? findQuestionLocation(draft, selectedId)?.question : null;

  return (
    <PortalShell role="Admin">
      <div className="survey-page gform-page">
        <PageHeader
          actions={
            <div className="survey-toolbar">
              <span className={`save-chip is-${saveState}`}>{saveLabel}</span>
              <Badge tone={statusLabel === "Published" ? "active" : "pending"}>{statusLabel}</Badge>
              <div className="gform-mode" role="tablist" aria-label="Survey workspace">
                <button type="button" className={workspaceMode === "edit" ? "on" : ""} onClick={() => setWorkspaceMode("edit")}>
                  <PencilIcon size={14} /> Edit
                </button>
                <button type="button" className={workspaceMode === "preview" ? "on" : ""} onClick={() => setWorkspaceMode("preview")}>
                  <EyeIcon size={14} /> Preview
                </button>
              </div>
              <button className="btn btn-outline btn-sm" type="button" onClick={() => setSettingsOpen(true)}>Settings</button>
              <button className="btn btn-outline btn-sm" type="button" onClick={() => setVersionsOpen(true)}>Versions</button>
              <button className="btn btn-outline btn-sm" type="button" onClick={saveNow} disabled={saveBusy}>Save Draft</button>
              <button className="btn btn-navy btn-sm" type="button" onClick={() => publish(false)} disabled={saveBusy}>
                {busy ? "Publishing..." : "Publish"}
              </button>
            </div>
          }
        />
        {error && !draft ? <LoadError onRetry={load}>{error}</LoadError> : null}

        {workspaceMode === "preview" ? (
          <div className="gform-workspace">
            <div className="gform-canvas gform-preview-pane">
              <div className="gform-card">
                <p className="gform-kicker">Live Preview</p>
                <h2>{draft.title || "Graduate Tracer Survey"}</h2>
                <p className="muted">This preview uses the same survey configuration and renderer as registration and the Alumni Portal. Unpublished draft changes appear here immediately; alumni see them after you publish.</p>
              </div>
              <div className="gform-card gform-preview-body">
                <GtsForm schema={draft} initial={PREVIEW_SEED} preview submitLabel="Preview only" />
              </div>
            </div>
          </div>
        ) : (
          <div className="gform-workspace">
            <div className="gform-canvas">
              <SurveyHeaderCard
                draft={draft}
                selected={selectedKind === "header"}
                statusLabel={statusLabel}
                updatedAt={data?.draft_updated_at}
                publisher={publisher}
                version={data?.published_version}
                onSelect={selectHeader}
                onChange={(partial) => updateDraft({ ...draft, ...partial })}
              />

              {(draft.sections || []).map((section, sIndex) => (
                <div key={section.id}>
                  {dropHint?.kind === "section" && dropHint.s === sIndex ? <div className="gform-drop" aria-hidden="true" /> : null}
                  <SectionCard
                    section={section}
                    sIndex={sIndex}
                    selected={selectedKind === "section" && selectedId === section.id}
                    expanded={expanded[section.id] !== false}
                    selectedQuestionId={selectedKind === "question" ? selectedId : null}
                    dropHint={dropHint}
                    byId={byId}
                    schema={draft}
                    types={addableTypes}
                    addMenu={addMenu}
                    conditionOpen={conditionOpen}
                    onSelect={() => selectSection(section.id)}
                    onToggle={() => setExpanded((prev) => ({ ...prev, [section.id]: prev[section.id] === false }))}
                    onChange={(partial) => updateSectionById(section.id, partial)}
                    onMove={(delta) => moveSection(section.id, delta)}
                    disableUp={sIndex === 0}
                    disableDown={sIndex === draft.sections.length - 1}
                    onDelete={() => setDeleteSectionTarget(section)}
                    onOpenTab={() => openAdminTab(`/admin/survey/sections/${section.id}`)}
                    onSelectQuestion={selectQuestion}
                    onChangeQuestion={updateQuestionById}
                    onTypeChange={requestTypeChange}
                    onDuplicate={applyDuplicate}
                    onDeleteQuestion={(question) => setDeleteTarget(question)}
                    onOpenQuestionTab={(question) => openAdminTab(`/admin/survey/questions/${question.id}`)}
                    onMoveQuestion={moveQuestion}
                    onMoveToSection={(question) => {
                      setMoveTarget(question);
                      const loc = findQuestionLocation(draft, question.id);
                      setMoveDest(`${loc.section.id}::${loc.subsection.id}`);
                    }}
                    onAddMenu={(key) => setAddMenu(key)}
                    onAddQuestion={(bIndex, type) => addQuestion(sIndex, bIndex, type)}
                    onConditionOpen={setConditionOpen}
                    onDragOverSection={(event) => {
                      event.preventDefault();
                      setDropHint({ kind: "section", s: sIndex });
                    }}
                    onDropSection={(event) => onDropSection(event, sIndex)}
                    onDragOverQuestion={(bIndex, qIndex) => setDropHint({ kind: "question", s: sIndex, b: bIndex, q: qIndex })}
                    onDropQuestion={(event, bIndex, qIndex) => onDropQuestion(event, sIndex, bIndex, qIndex)}
                    onDragEnd={() => setDropHint(null)}
                  />
                </div>
              ))}

              <button type="button" className="gform-add-section" onClick={addNewSection}>
                <LayersIcon size={16} /> Add section
              </button>
            </div>

            <aside className="gform-float" aria-label="Quick actions">
              <div className="gform-type-menu">
                <button type="button" className="gform-float-btn" title="Add question" aria-label="Add question" onClick={() => addQuestionNearSelection("short_answer")}>
                  <PlusIcon size={18} />
                </button>
              </div>
              <button type="button" className="gform-float-btn" title="Add section" aria-label="Add section" onClick={addNewSection}>
                <LayersIcon size={18} />
              </button>
              <button
                type="button"
                className="gform-float-btn"
                title="Duplicate selected question"
                aria-label="Duplicate selected question"
                disabled={!selectedQuestion}
                onClick={() => selectedQuestion && applyDuplicate(selectedQuestion)}
              >
                <CopyIcon size={18} />
              </button>
              <button type="button" className="gform-float-btn" title="Preview" aria-label="Preview survey" onClick={() => setWorkspaceMode("preview")}>
                <EyeIcon size={18} />
              </button>
            </aside>
          </div>
        )}

        <div className="gform-mobile-bar">
          <button type="button" onClick={() => addQuestionNearSelection("short_answer")}><PlusIcon size={16} /> Question</button>
          <button type="button" onClick={addNewSection}><LayersIcon size={16} /> Section</button>
          <button type="button" className={workspaceMode === "preview" ? "on" : ""} onClick={() => setWorkspaceMode(workspaceMode === "preview" ? "edit" : "preview")}>
            <EyeIcon size={16} /> Preview
          </button>
        </div>
      </div>

      {deleteTarget ? (
        <Dialog
          title="Delete Question"
          description={`Are you sure you want to delete “${deleteTarget.label || "this question"}”? This removes it from the draft. Historical answers stay on existing tracer records.`}
          confirmLabel="Delete"
          danger
          compact
          busy={actionBusy === "delete"}
          onConfirm={applyDelete}
          onClose={() => { if (actionBusy !== "delete") setDeleteTarget(null); }}
        >
          {systemWarning(deleteTarget) ? <Alert type="error">{systemWarning(deleteTarget)}</Alert> : <p>This action cannot be undone from the draft except by restoring a previous version.</p>}
        </Dialog>
      ) : null}

      {deleteSectionTarget ? (
        <Dialog
          title="Delete Section"
          description={`Are you sure you want to delete “${deleteSectionTarget.name || "this section"}” and its questions from the draft? Historical answers stay on existing tracer records.`}
          confirmLabel="Delete"
          danger
          compact
          onConfirm={applyDeleteSection}
          onClose={() => setDeleteSectionTarget(null)}
        >
          {(deleteSectionTarget.subsections || []).some((sub) => (sub.questions || []).some(isSystemQuestion)) ? (
            <Alert type="error">This section contains system-critical questions used by registration, reporting, or career alignment.</Alert>
          ) : (
            <p>This action cannot be undone from the draft except by restoring a previous version.</p>
          )}
        </Dialog>
      ) : null}

      {moveTarget ? (
        <Dialog
          title="Move Question"
          description={`Choose where “${moveTarget.label || "this question"}” should appear.`}
          confirmLabel="Move"
          compact
          onConfirm={applyMove}
          onClose={() => setMoveTarget(null)}
        >
          <Field label="Destination">
            <select value={moveDest} onChange={(event) => setMoveDest(event.target.value)}>
              {(draft.sections || []).flatMap((section) => (section.subsections || []).map((sub) => (
                <option key={`${section.id}-${sub.id}`} value={`${section.id}::${sub.id}`}>
                  {section.name}{sub.name ? ` · ${sub.name}` : ""}
                </option>
              )))}
            </select>
          </Field>
        </Dialog>
      ) : null}

      {typeWarn ? (
        <Dialog
          title="Change System Field"
          description={typeWarn.warning}
          confirmLabel="Change type"
          danger
          compact
          onConfirm={() => { typeWarn.apply(); setTypeWarn(null); showToast("warning", "System field type changed in the draft."); }}
          onClose={() => setTypeWarn(null)}
        />
      ) : null}

      {publishWarnings ? (
        <Dialog
          title="Publish these changes?"
          description="These edits may affect Career Alignment, registration, reporting, or historical responses. Existing tracer answers will not be deleted."
          confirmLabel="Publish anyway"
          danger
          busy={busy}
          onConfirm={() => publish(true)}
          onClose={() => { if (!busy) setPublishWarnings(null); }}
        >
          <ul className="warn-list">
            {publishWarnings.map((item) => <li key={item.message}>{item.message}</li>)}
          </ul>
        </Dialog>
      ) : null}

      {settingsOpen ? (
        <Dialog
          title="Survey settings"
          description="Saved settings update the live Graduate Tracer Survey without requiring a rebuild. Question and section edits still need Publish."
          hideActions
          busy={busy}
          onClose={() => { if (!busy) setSettingsOpen(false); }}
          wide
          footer={(
            <>
              <button type="button" className="btn btn-outline" onClick={() => { if (!busy) setSettingsOpen(false); }} disabled={busy}>Cancel</button>
              <button type="submit" form="survey-settings-form" className="btn btn-navy" disabled={busy}>{busy ? "Saving..." : "Save Settings"}</button>
            </>
          )}
        >
          <form id="survey-settings-form" onSubmit={saveSettings} className="settings-form">
            <Field label="Survey title" required>
              <input name="title" defaultValue={draft.title || ""} required />
            </Field>
            <Field label="Survey description">
              <textarea name="description" defaultValue={draft.description || ""} />
            </Field>
            <Field label="Introductory instructions">
              <textarea name="intro" defaultValue={draft.intro || ""} />
            </Field>
            <Field label="Confirmation message">
              <textarea name="confirmation_message" defaultValue={draft.confirmation_message || ""} />
            </Field>
            <div className="inline-fields">
              <Field label="Start date"><input type="date" name="start_date" defaultValue={draft.start_date || ""} /></Field>
              <Field label="End date"><input type="date" name="end_date" defaultValue={draft.end_date || ""} /></Field>
            </div>
            <label className="check">
              <input type="checkbox" name="accepting_responses" defaultChecked={draft.accepting_responses !== false} />
              Accepting responses
            </label>
            <label className="check">
              <input type="checkbox" name="allow_alumni_edit" defaultChecked={draft.allow_alumni_edit !== false} />
              Allow alumni to edit responses
            </label>
          </form>
        </Dialog>
      ) : null}

      {versionsOpen ? (
        <Dialog
          title="Survey versions"
          description="Open a version in a new tab to review it as a full page. Restoring copies that version into the draft without changing historical responses."
          hideActions
          busy={busy}
          onClose={() => { if (!busy) setVersionsOpen(false); }}
          wide
          footer={(
            <button type="button" className="btn btn-outline" onClick={() => { if (!busy) setVersionsOpen(false); }} disabled={busy}>Close</button>
          )}
        >
          {!data?.versions?.length ? (
            <Empty title="No versions yet">Publish the survey to create version history.</Empty>
          ) : (
            <div className="table-wrap">
              <table className="data stack">
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Published</th>
                    <th>Published by</th>
                    <th>Questions</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {data.versions.map((row) => (
                    <tr key={row.version}>
                      <td data-label="Version">{row.version}</td>
                      <td data-label="Published">{formatDateTime(row.published_at)}</td>
                      <td data-label="Published by">{row.published_by || "—"}</td>
                      <td data-label="Questions">{row.question_count}</td>
                      <td data-label="Status"><Badge tone={row.status === "Published" ? "active" : "unknown"}>{row.status}</Badge></td>
                      <td className="cell-actions">
                        <button
                          className="btn btn-outline btn-sm"
                          type="button"
                          onClick={() => openAdminTab(`/admin/survey/versions/${row.version}`)}
                        >
                          <span className="label-full">Open in New Tab</span>
                          <span className="label-short">New Tab</span>
                          <ExternalLinkIcon size={14} />
                        </button>
                        <button className="btn btn-outline btn-sm" type="button" onClick={() => restoreVersion(row.version)} disabled={busy}>Restore to draft</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Dialog>
      ) : null}
    </PortalShell>
  );
}

function SurveyHeaderCard({ draft, selected, statusLabel, updatedAt, publisher, version, onSelect, onChange }) {
  return (
    <article className={`gform-card gform-header ${selected ? "is-active" : ""}`} onClick={onSelect}>
      <div className="gform-accent" aria-hidden="true" />
      <div className="gform-header-meta">
        <Badge tone={statusLabel === "Published" ? "active" : "pending"}>{statusLabel}</Badge>
        {version ? <span className="muted">Version {version}</span> : null}
      </div>
      {selected ? (
        <>
          <label className="gform-title-field">
            <span className="sr-only">Survey title</span>
            <input
              className="gform-title-input"
              value={draft.title || ""}
              onChange={(event) => onChange({ title: event.target.value })}
              onClick={(event) => event.stopPropagation()}
            />
          </label>
          <label>
            <span className="sr-only">Survey description</span>
            <textarea
              className="gform-desc-input"
              value={draft.description || ""}
              onChange={(event) => onChange({ description: event.target.value })}
              onClick={(event) => event.stopPropagation()}
              rows={3}
            />
          </label>
        </>
      ) : (
        <>
          <h2>{draft.title || "Graduate Tracer Survey"}</h2>
          <p className="muted">{draft.description || "Add a survey description."}</p>
        </>
      )}
      <p className="gform-updated">
        {updatedAt ? `Last updated ${formatDateTime(updatedAt)}` : "Not yet saved"}
        {publisher ? ` · Last published by ${publisher}` : ""}
      </p>
    </article>
  );
}

function SectionCard({
  section,
  sIndex,
  selected,
  expanded,
  selectedQuestionId,
  dropHint,
  byId,
  schema,
  types,
  addMenu,
  conditionOpen,
  onSelect,
  onToggle,
  onChange,
  onMove,
  disableUp,
  disableDown,
  onDelete,
  onOpenTab,
  onSelectQuestion,
  onChangeQuestion,
  onTypeChange,
  onDuplicate,
  onDeleteQuestion,
  onOpenQuestionTab,
  onMoveQuestion,
  onMoveToSection,
  onAddMenu,
  onAddQuestion,
  onConditionOpen,
  onDragOverSection,
  onDropSection,
  onDragOverQuestion,
  onDropQuestion,
  onDragEnd,
}) {
  const core = CORE_SECTION_KEYS.includes(section.key);
  const menuKey = `section-${section.id}`;

  return (
    <section
      className={`gform-section ${selected ? "is-active" : ""}`}
      onDragOver={onDragOverSection}
      onDrop={onDropSection}
      onDragLeave={(event) => {
        if (!event.currentTarget.contains(event.relatedTarget)) onDragEnd();
      }}
    >
      <article className={`gform-card gform-section-head ${selected ? "is-active" : ""}`}>
        <div className="gform-section-top">
          <button
            type="button"
            className="drag-handle"
            aria-label={`Reorder ${section.name}`}
            draggable
            onDragStart={(event) => {
              event.stopPropagation();
              event.dataTransfer.effectAllowed = "move";
              event.dataTransfer.setData("application/json", JSON.stringify({ kind: "section", s: sIndex }));
            }}
            onDragEnd={onDragEnd}
          >
            <GripIcon size={16} />
          </button>
          <button type="button" className="gform-section-select" onClick={onSelect}>
            <span className="gform-kicker">{core ? "Core GTS section" : "Section"}</span>
          </button>
          <button type="button" className="btn btn-ghost btn-sm icon-only" aria-label={expanded ? `Collapse ${section.name}` : `Expand ${section.name}`} onClick={onToggle}>
            {expanded ? "–" : "+"}
          </button>
        </div>
        {selected ? (
          <>
            <input
              className="gform-section-title-input"
              value={section.name || ""}
              onChange={(event) => onChange({ name: event.target.value })}
              aria-label="Section title"
            />
            <textarea
              className="gform-desc-input"
              value={section.description || ""}
              onChange={(event) => onChange({ description: event.target.value })}
              aria-label="Section description"
              rows={2}
            />
            <div className="gform-toolbar">
              <button type="button" className="gform-tool" onClick={() => onMove(-1)} disabled={disableUp} title="Move section up" aria-label="Move section up">
                <ChevronUpIcon size={16} />
              </button>
              <button type="button" className="gform-tool" onClick={() => onMove(1)} disabled={disableDown} title="Move section down" aria-label="Move section down">
                <ChevronDownIcon size={16} />
              </button>
              {core ? (
                <span className="muted gform-tool-note">This core section cannot be deleted.</span>
              ) : (
                <button type="button" className="gform-tool danger" onClick={onDelete} title="Delete section" aria-label="Delete section">
                  <TrashIcon size={16} />
                </button>
              )}
              <button
                type="button"
                className="gform-tool gform-tool-text"
                onClick={onOpenTab}
                title="Open section in new tab"
              >
                <span className="label-full">Open in New Tab</span>
                <span className="label-short">New Tab</span>
                <ExternalLinkIcon size={16} />
              </button>
            </div>
          </>
        ) : (
          <button type="button" className="gform-section-copy" onClick={onSelect}>
            <h3>{section.name}</h3>
            {section.description ? <p className="muted">{section.description}</p> : null}
          </button>
        )}
      </article>

      {expanded ? (section.subsections || []).map((sub, bIndex) => (
        <div key={sub.id} className="gform-sub">
          {sub.name ? <p className="gform-sub-name">{sub.name}</p> : null}
          {(sub.questions || []).map((question, qIndex) => (
            <div key={question.id}>
              {dropHint?.kind === "question" && dropHint.s === sIndex && dropHint.b === bIndex && dropHint.q === qIndex ? (
                <div className="gform-drop" aria-hidden="true" />
              ) : null}
              <QuestionCard
                question={question}
                sIndex={sIndex}
                bIndex={bIndex}
                qIndex={qIndex}
                selected={selectedQuestionId === question.id}
                last={qIndex === (sub.questions || []).length - 1}
                schema={schema}
                byId={byId}
                types={types}
                conditionOpen={conditionOpen === question.id}
                onSelect={() => onSelectQuestion(question.id)}
                onChange={(partial) => onChangeQuestion(question.id, partial)}
                onTypeChange={(type) => onTypeChange(question, type)}
                onDuplicate={() => onDuplicate(question)}
                onDelete={() => onDeleteQuestion(question)}
                onOpenTab={() => onOpenQuestionTab(question)}
                onMoveUp={() => onMoveQuestion(question.id, -1)}
                onMoveDown={() => onMoveQuestion(question.id, 1)}
                onMoveToSection={() => onMoveToSection(question)}
                onToggleCondition={() => onConditionOpen(conditionOpen === question.id ? null : question.id)}
                onDragOver={() => onDragOverQuestion(bIndex, qIndex)}
                onDrop={(event) => onDropQuestion(event, bIndex, qIndex)}
                onDragEnd={onDragEnd}
              />
            </div>
          ))}
          <div
            className="gform-drop-end"
            onDragOver={(event) => { event.preventDefault(); onDragOverQuestion(bIndex, (sub.questions || []).length); }}
            onDrop={(event) => onDropQuestion(event, bIndex, (sub.questions || []).length)}
          />
          <AddQuestionRow
            menuKey={menuKey}
            bIndex={bIndex}
            addMenu={addMenu}
            types={types}
            onAddMenu={onAddMenu}
            onAddQuestion={onAddQuestion}
          />
        </div>
      )) : null}
    </section>
  );
}

function QuestionCard({
  question,
  sIndex,
  bIndex,
  qIndex,
  selected,
  last,
  schema,
  byId,
  types,
  conditionOpen,
  onSelect,
  onChange,
  onTypeChange,
  onDuplicate,
  onDelete,
  onOpenTab,
  onMoveUp,
  onMoveDown,
  onMoveToSection,
  onToggleCondition,
  onDragOver,
  onDrop,
  onDragEnd,
}) {
  const typeLocked = question.type === "repeatable_group" || question.type === "skills";
  const condition = visibilitySummary(question, byId);

  return (
    <article
      className={`gform-card gform-question ${selected ? "is-active" : ""}`}
      onClick={onSelect}
      onDragOver={(event) => { event.preventDefault(); event.stopPropagation(); onDragOver(); }}
      onDrop={(event) => { event.stopPropagation(); onDrop(event); }}
    >
      <button
        type="button"
        className="drag-handle gform-q-grip"
        aria-label={`Reorder ${question.label}`}
        draggable
        onClick={(event) => event.stopPropagation()}
        onDragStart={(event) => {
          event.stopPropagation();
          event.dataTransfer.effectAllowed = "move";
          event.dataTransfer.setData("application/json", JSON.stringify({ kind: "question", s: sIndex, b: bIndex, q: qIndex }));
        }}
        onDragEnd={onDragEnd}
      >
        <GripIcon size={16} />
      </button>

      {selected ? (
        <div onClick={(event) => event.stopPropagation()}>
          <QuestionEditor
            question={question}
            schema={schema}
            byId={byId}
            types={types}
            typeLocked={typeLocked}
            conditionOpen={conditionOpen}
            onChange={onChange}
            onTypeChange={onTypeChange}
            onToggleCondition={onToggleCondition}
          />
          <div className="gform-toolbar">
            <button type="button" className="gform-tool" onClick={onDuplicate} title="Duplicate" aria-label="Duplicate question">
              <CopyIcon size={16} />
            </button>
            <button type="button" className="gform-tool" onClick={onMoveUp} disabled={qIndex === 0} title="Move up" aria-label="Move question up">
              <ChevronUpIcon size={16} />
            </button>
            <button type="button" className="gform-tool" onClick={onMoveDown} disabled={last} title="Move down" aria-label="Move question down">
              <ChevronDownIcon size={16} />
            </button>
            <button type="button" className="gform-tool" onClick={onMoveToSection} title="Move to section" aria-label="Move question to another section">
              <LayersIcon size={16} />
            </button>
            <button type="button" className="gform-tool danger" onClick={onDelete} title="Delete" aria-label="Delete question">
              <TrashIcon size={16} />
            </button>
            <button
              type="button"
              className="gform-tool gform-tool-text"
              onClick={onOpenTab}
              title="Open question in new tab"
            >
              <span className="label-full">Open in New Tab</span>
              <span className="label-short">New Tab</span>
              <ExternalLinkIcon size={16} />
            </button>
            <label className="gform-required">
              <input type="checkbox" checked={Boolean(question.required)} onChange={(event) => onChange({ required: event.target.checked })} />
              Required
            </label>
          </div>
        </div>
      ) : (
        <div className="gform-q-compact">
          <div className="gform-q-topline">
            <h4>{question.label || "Untitled question"}{question.required ? <span className="req"> *</span> : null}</h4>
            <span className="gform-type-chip">{questionTypeLabel(question.type)}</span>
          </div>
          <div className="gform-chips">
            {isSystemQuestion(question) ? <Badge tone="pending">System field</Badge> : null}
            {condition ? <Badge tone="info" title={condition}>Conditional</Badge> : null}
          </div>
          {condition ? <p className="gform-condition-note">{condition}</p> : null}
          <QuestionPreview question={question} />
        </div>
      )}
    </article>
  );
}

function QuestionPreview({ question }) {
  const type = question.type;
  if (type === "paragraph") return <div className="gform-fake-input tall" />;
  if (type === "yes_no") {
    return (
      <div className="gform-choice-preview">
        <span>○ Yes</span>
        <span>○ No</span>
      </div>
    );
  }
  if (type === "multiple_choice" || type === "scale") {
    const options = (question.options || []).length ? question.options : type === "scale" ? ["1", "2", "3", "4", "5"] : ["Option 1", "Option 2"];
    return (
      <div className="gform-choice-preview">
        {options.slice(0, 6).map((opt, index) => (
          <span key={`${optionKey(opt)}-${index}`}>○ {optionLabel(opt) || optionText(opt)}</span>
        ))}
      </div>
    );
  }
  if (type === "checkboxes") {
    return (
      <div className="gform-choice-preview">
        {(question.options || ["Option 1", "Option 2"]).slice(0, 6).map((opt, index) => (
          <span key={`${optionKey(opt)}-${index}`}>☐ {optionLabel(opt) || optionText(opt)}</span>
        ))}
      </div>
    );
  }
  if (type === "dropdown") return <div className="gform-fake-select">Select</div>;
  if (type === "repeatable_group") return <p className="muted">Alumni can add multiple study programs.</p>;
  if (type === "skills") return <div className="gform-fake-input">Python, JavaScript, SQL</div>;
  if (type === "date") return <div className="gform-fake-input">Date</div>;
  if (type === "number") return <div className="gform-fake-input">Number</div>;
  return <div className="gform-fake-input" />;
}

function QuestionEditor({ question, schema, byId, types, typeLocked, conditionOpen, onChange, onTypeChange, onToggleCondition }) {
  const needsOptions = CHOICE_TYPES.has(question.type);
  const scaleNumeric = question.type === "scale" && (question.options || []).every((item) => /^\d+$/.test(optionValue(item)));
  const otherQuestions = flattenQuestions(schema).map((item) => item.question).filter((item) => item.id !== question.id);
  const condition = question.visibility?.rules?.[0] || null;
  const [cycleError, setCycleError] = useState("");
  const [removeOption, setRemoveOption] = useState(null);
  const rules = question.validation || {};

  function setOptions(options) {
    onChange({ options });
  }

  function patchValidation(partial) {
    onChange({ validation: { ...rules, ...partial } });
  }

  return (
    <>
    <div className="gform-editor">
      <div className="gform-chips">
        {isSystemQuestion(question) ? <Badge tone="pending">System field</Badge> : <Badge>Custom question</Badge>}
        {visibilitySummary(question, byId) ? <Badge tone="info">Conditional</Badge> : null}
      </div>
      {ALIGNMENT_FIELD_KEYS.has(question.field_key || question.id) ? (
        <p className="muted">Used by Career Alignment. Edit wording freely; changing the type or removing it requires confirmation.</p>
      ) : null}
      <div className="gform-editor-row">
        <label className="gform-grow">
          <span className="sr-only">Question</span>
          <input
            className="gform-question-input"
            value={question.label || ""}
            autoFocus={question.label === "Untitled question"}
            onChange={(event) => onChange({ label: event.target.value })}
            placeholder="Question"
          />
        </label>
        <label className="gform-type-select">
          <span className="sr-only">Question type</span>
          <select value={question.type} disabled={typeLocked} onChange={(event) => onTypeChange(event.target.value)}>
            {(QUESTION_TYPES.filter(([id]) => types.includes(id) || id === question.type)).map(([id, label]) => (
              <option key={id} value={id}>{label}</option>
            ))}
            {typeLocked ? <option value={question.type}>{questionTypeLabel(question.type)}</option> : null}
          </select>
        </label>
      </div>
      <textarea
        className="gform-desc-input"
        value={question.description || ""}
        onChange={(event) => onChange({ description: event.target.value })}
        placeholder="Description / help text (optional)"
        rows={2}
      />

      {needsOptions && !scaleNumeric ? (
        <div className="gform-options">
          {(question.options || []).map((opt, index) => (
            <div
              key={`${optionKey(opt)}-${index}`}
              className="option-row"
              onDragOver={(event) => event.preventDefault()}
              onDrop={(event) => {
                const from = Number(event.dataTransfer.getData("text/plain"));
                if (Number.isNaN(from)) return;
                setOptions(moveItem(question.options || [], from, index));
              }}
            >
              <span className="gform-opt-mark" aria-hidden="true">{question.type === "checkboxes" ? "☐" : "○"}</span>
              <input
                value={optionText(opt)}
                onChange={(event) => {
                  const next = [...(question.options || [])];
                  next[index] = typeof opt === "object"
                    ? { ...opt, label: event.target.value, value: opt.value ?? event.target.value }
                    : event.target.value;
                  setOptions(next);
                }}
              />
              <button
                type="button"
                className="btn btn-ghost btn-sm icon-only"
                onClick={() => setRemoveOption({ index, label: optionText(opt) || `Option ${index + 1}` })}
                disabled={(question.options || []).length <= 2}
                aria-label="Remove option"
              >
                ×
              </button>
            </div>
          ))}
          <button type="button" className="gform-add-option" onClick={() => setOptions([...(question.options || []), `Option ${(question.options || []).length + 1}`])}>
            + Add option
          </button>
          {(question.options || []).filter((item) => optionValue(item).trim()).length < 2 ? (
            <p className="field-error">This question needs at least two choices before it can be saved.</p>
          ) : null}
        </div>
      ) : null}

      {question.type === "scale" && scaleNumeric ? (
        <div className="inline-fields">
          <Field label="Minimum">
            <input type="number" value={numericScaleBounds(question.options).min} onChange={(event) => setOptions(scaleOptions(event.target.value, numericScaleBounds(question.options).max))} />
          </Field>
          <Field label="Maximum">
            <input type="number" value={numericScaleBounds(question.options).max} onChange={(event) => setOptions(scaleOptions(numericScaleBounds(question.options).min, event.target.value))} />
          </Field>
        </div>
      ) : null}

      {TEXT_TYPES.has(question.type) ? (
        <details className="gform-more">
          <summary>Additional settings</summary>
          <div className="inline-fields">
            <Field label="Placeholder">
              <input value={question.placeholder || ""} onChange={(event) => onChange({ placeholder: event.target.value })} />
            </Field>
            <Field label="Default value">
              <input value={defaultValueText(question.default_value)} onChange={(event) => onChange({ default_value: event.target.value })} />
            </Field>
            <Field label="Minimum length">
              <input type="number" min="0" value={rules.min_length ?? ""} onChange={(event) => patchValidation({ min_length: event.target.value === "" ? "" : Number(event.target.value) })} />
            </Field>
            <Field label="Maximum length">
              <input type="number" min="0" value={rules.max_length ?? ""} onChange={(event) => patchValidation({ max_length: event.target.value === "" ? "" : Number(event.target.value) })} />
            </Field>
          </div>
        </details>
      ) : null}

      {question.type === "number" ? (
        <details className="gform-more">
          <summary>Additional settings</summary>
          <div className="inline-fields">
            <Field label="Placeholder">
              <input value={question.placeholder || ""} onChange={(event) => onChange({ placeholder: event.target.value })} />
            </Field>
            <Field label="Minimum">
              <input type="number" value={rules.min ?? ""} onChange={(event) => patchValidation({ min: event.target.value === "" ? "" : Number(event.target.value) })} />
            </Field>
            <Field label="Maximum">
              <input type="number" value={rules.max ?? ""} onChange={(event) => patchValidation({ max: event.target.value === "" ? "" : Number(event.target.value) })} />
            </Field>
          </div>
        </details>
      ) : null}

      {question.type === "repeatable_group" ? (
        <div className="gform-options">
          <p className="muted">Alumni can add multiple study programs. Labels below appear on each card.</p>
          {(question.repeatable?.fields || []).map((field, index) => (
            <Field key={field.id} label={`Field ${index + 1}`}>
              <input
                value={field.label}
                onChange={(event) => {
                  const fields = [...(question.repeatable.fields || [])];
                  fields[index] = { ...field, label: event.target.value };
                  onChange({ repeatable: { ...question.repeatable, fields } });
                }}
              />
            </Field>
          ))}
        </div>
      ) : null}

      <div className="gform-condition">
        {visibilitySummary(question, byId) ? (
          <p>{visibilitySummary(question, byId)}</p>
        ) : (
          <p className="muted">Always visible</p>
        )}
        <button type="button" className="btn btn-outline btn-sm" onClick={onToggleCondition}>
          {conditionOpen || condition ? "Edit condition" : "Add condition"}
        </button>
      </div>
      {conditionOpen ? (
        <div className="gform-condition-editor">
          {cycleError ? <Alert type="error">{cycleError}</Alert> : null}
          <Field label="Show this question when">
            <select
              value={condition?.field_id || ""}
              onChange={(event) => {
                const fieldId = event.target.value;
                setCycleError("");
                if (!fieldId) {
                  onChange({ visibility: null });
                  return;
                }
                if (wouldCreateCycle(schema, question.id, fieldId)) {
                  setCycleError("That condition would create a circular rule. Choose a different question.");
                  return;
                }
                const parent = byId[fieldId];
                const value = parent?.type === "yes_no" ? "Yes" : optionValue((parent?.options || [])[0]) || "";
                onChange({ visibility: { logic: "and", rules: [{ field_id: fieldId, op: "eq", value }] } });
              }}
            >
              <option value="">Always show</option>
              {otherQuestions.map((item) => (
                <option key={item.id} value={item.id}>{item.label}</option>
              ))}
            </select>
          </Field>
          {condition ? (
            <div className="inline-fields">
              <Field label="Condition">
                <select
                  value={condition.op || "eq"}
                  onChange={(event) => onChange({ visibility: { logic: "and", rules: [{ ...condition, op: event.target.value }] } })}
                >
                  <option value="eq">is</option>
                  <option value="neq">is not</option>
                  <option value="includes">includes</option>
                </select>
              </Field>
              <Field label="Value">
                {parentOptions(byId[condition.field_id]).length ? (
                  <select
                    value={condition.value || ""}
                    onChange={(event) => onChange({ visibility: { logic: "and", rules: [{ ...condition, value: event.target.value }] } })}
                  >
                    {parentOptions(byId[condition.field_id]).map((opt) => (
                      <option key={opt} value={opt}>{opt}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    value={condition.value || ""}
                    onChange={(event) => onChange({ visibility: { logic: "and", rules: [{ ...condition, value: event.target.value }] } })}
                  />
                )}
              </Field>
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
    {removeOption ? (
      <Dialog
        title="Remove Option"
        description={`Are you sure you want to remove “${removeOption.label}”?`}
        confirmLabel="Remove"
        danger
        compact
        onConfirm={() => {
          setOptions((question.options || []).filter((_, itemIndex) => itemIndex !== removeOption.index));
          setRemoveOption(null);
          showToast("info", "Option removed from the draft.");
        }}
        onClose={() => setRemoveOption(null)}
      >
        <p>This action cannot be undone except by re-adding the choice.</p>
      </Dialog>
    ) : null}
    </>
  );
}

function AddQuestionRow({ menuKey, bIndex, addMenu, types, onAddMenu, onAddQuestion }) {
  const wrapRef = useRef(null);
  const open = addMenu === `${menuKey}:${bIndex}`;
  return (
    <div className="gform-add-wrap gform-type-menu" ref={wrapRef}>
      <button type="button" className="gform-add-question" onClick={() => onAddQuestion(bIndex, "short_answer")}>
        <PlusIcon size={16} /> Add question
      </button>
      <button
        type="button"
        className="gform-add-type"
        aria-label="Choose question type"
        title="Choose question type"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => onAddMenu(open ? null : `${menuKey}:${bIndex}`)}
      >
        <ChevronDownIcon size={16} />
      </button>
      {open ? (
        <TypeMenu
          types={types}
          anchorRef={wrapRef}
          onPick={(type) => onAddQuestion(bIndex, type)}
        />
      ) : null}
    </div>
  );
}

function TypeMenu({ types, onPick, anchorRef }) {
  const menuRef = useRef(null);
  const [coords, setCoords] = useState(null);

  useLayoutEffect(() => {
    function place() {
      const anchor = anchorRef?.current;
      const menu = menuRef.current;
      if (!anchor || !menu) return;
      const rect = anchor.getBoundingClientRect();
      const gap = 8;
      const margin = 8;
      const top = rect.bottom + gap;
      let bottomLimit = window.innerHeight - margin;
      const bar = document.querySelector(".gform-mobile-bar");
      if (bar) {
        const style = window.getComputedStyle(bar);
        if (style.display !== "none" && style.visibility !== "hidden") {
          const barTop = bar.getBoundingClientRect().top;
          if (barTop > top) bottomLimit = Math.min(bottomLimit, barTop - gap);
        }
      }
      const minWidth = Math.min(Math.max(rect.width, 200), window.innerWidth - margin * 2);
      const menuWidth = Math.max(menu.offsetWidth, minWidth);
      let left = rect.left;
      left = Math.min(Math.max(margin, left), Math.max(margin, window.innerWidth - menuWidth - margin));
      const maxHeight = Math.max(72, Math.min(320, bottomLimit - top));
      setCoords({ top, left, minWidth, maxHeight });
    }

    place();
    window.addEventListener("resize", place);
    window.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      window.removeEventListener("scroll", place, true);
    };
  }, [anchorRef, types]);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      ref={menuRef}
      className="mini-menu gform-type-menu gform-type-popover"
      role="menu"
      style={coords
        ? { top: coords.top, left: coords.left, minWidth: coords.minWidth, maxHeight: coords.maxHeight }
        : { visibility: "hidden", pointerEvents: "none" }}
    >
      {QUESTION_TYPES.filter(([id]) => types.includes(id)).map(([id, label]) => (
        <button key={id} type="button" role="menuitem" onClick={() => onPick(id)}>{label}</button>
      ))}
    </div>,
    document.body
  );
}
