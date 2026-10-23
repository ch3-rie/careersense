import { useEffect, useMemo, useState } from "react";
import { Panel } from "../../components/RecordViews";
import { RowActions } from "../../components/RowActions";
import { PortalShell } from "../../components/Layout";
import { ChevronDownIcon, PencilIcon, PlusIcon, SearchIcon } from "../../components/icons";
import { Alert, Dialog, Empty, Field, LoadError, Pager, SortButton, TableSkeleton, TabList, sortBy, toggleSort } from "../../components/ui";
import { api } from "../../lib/api";

const PAGE_SIZE = 8;

const EMPTY_COLLEGE = { id: null, name: "", code: "" };
const EMPTY_COURSE = {
  id: null,
  college_id: "",
  parent_id: "",
  name: "",
  course_code: "",
  kind: "undergraduate",
  review_status: "needs_review",
};

function sameText(left, right) {
  return String(left || "").trim().toLowerCase() === String(right || "").trim().toLowerCase();
}

function hasProblems(problems) {
  return Object.keys(problems).length > 0;
}

function collegeProblems(form, colleges) {
  const problems = {};
  const name = form.name.trim();
  const code = form.code.trim();
  if (!name) problems.name = "Enter a college name.";
  else if (name.length > 160) problems.name = "College name must be 160 characters or fewer.";
  else if (colleges.some((row) => row.id !== form.id && sameText(row.name, name))) problems.name = "A college with this name already exists.";
  if (code.length > 40) problems.code = "College code must be 40 characters or fewer.";
  else if (code && colleges.some((row) => row.id !== form.id && sameText(row.code, code))) problems.code = "A college with this code already exists.";
  return problems;
}

function courseProblems(form, courses) {
  const problems = {};
  const name = form.name.trim();
  const code = form.course_code.trim();
  if (!form.college_id) problems.college_id = "Select the college this course belongs to.";
  if (!name) problems.name = "Enter a course name.";
  else if (name.length > 200) problems.name = "Course name must be 200 characters or fewer.";
  else if (form.college_id && courses.some((row) => row.id !== form.id && row.college_id === Number(form.college_id) && sameText(row.name, name))) {
    problems.name = "A course with this name already exists in the selected college.";
  }
  if (code.length > 40) problems.course_code = "Course code must be 40 characters or fewer.";
  else if (code && courses.some((row) => row.id !== form.id && sameText(row.course_code, code))) {
    problems.course_code = `Course code ${code} is already used by another course.`;
  }
  if (form.parent_id && Number(form.parent_id) === form.id) problems.parent_id = "A program cannot be its own parent.";
  return problems;
}

function removalBlock(kind, row, courses) {
  if (kind === "college") {
    if (row.course_count > 0) {
      const noun = row.course_count === 1 ? "course" : "courses";
      return `This college still has ${row.course_count} ${noun}. Edit those courses and move them to another college, or delete them, before removing this college. Graduate records were not changed.`;
    }
    if (row.graduate_count > 0) {
      const noun = row.graduate_count === 1 ? "graduate record uses" : "graduate records use";
      return `${row.graduate_count} ${noun} this college. Update those records to another college before deleting it.`;
    }
    return "";
  }
  const children = courses.filter((item) => item.parent_id === row.id).length;
  if (children) {
    const noun = children === 1 ? "program" : "programs";
    return `This program still has ${children} related ${noun}. Move or delete those majors, specializations, or pathways first. Graduate records were not changed.`;
  }
  if (row.graduate_count > 0) {
    const noun = row.graduate_count === 1 ? "graduate record uses" : "graduate records use";
    return `${row.graduate_count} ${noun} this course. Update those records before deleting it. Graduate records were not changed.`;
  }
  return "";
}

function confirmationDetail(error) {
  const detail = error?.payload?.detail;
  if (detail && typeof detail === "object" && detail.requires_confirmation) return detail;
  return null;
}

export default function AdminAcademics() {
  const [tab, setTab] = useState("colleges");
  const [data, setData] = useState(null);
  const [query, setQuery] = useState("");
  const [collegeFilter, setCollegeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState({ key: "name", dir: "asc" });
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const [busy, setBusy] = useState(true);
  const [saving, setSaving] = useState(false);
  const [collegeForm, setCollegeForm] = useState(null);
  const [courseForm, setCourseForm] = useState(null);
  const [fieldErrors, setFieldErrors] = useState({});
  const [formError, setFormError] = useState("");
  const [confirm, setConfirm] = useState(null);
  const [removing, setRemoving] = useState(null);
  const [removeError, setRemoveError] = useState("");
  const [openCollegeId, setOpenCollegeId] = useState(null);
  const [collapsedSearchIds, setCollapsedSearchIds] = useState(() => new Set());

  async function load() {
    setError("");
    setBusy(true);
    try {
      setData(await api("/api/admin/academics"));
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  useEffect(() => {
    if (!ok) return undefined;
    const timer = window.setTimeout(() => setOk(""), 4500);
    return () => window.clearTimeout(timer);
  }, [ok]);

  const colleges = data?.colleges || [];
  const courses = data?.courses || [];
  const term = query.trim().toLowerCase();

  useEffect(() => {
    setCollapsedSearchIds(new Set());
  }, [term]);

  const collegeRows = useMemo(() => {
    const filtered = colleges.filter((row) => {
      if (!term) return true;
      if ([row.name, row.code].join(" ").toLowerCase().includes(term)) return true;
      return courses.some((course) => course.college_id === row.id && [course.name, course.course_code].join(" ").toLowerCase().includes(term));
    });
    return sortBy(filtered, sort, {
      name: (row) => row.name.toLowerCase(),
      code: (row) => (row.code || "").toLowerCase(),
      course_count: (row) => row.course_count || 0,
      graduate_count: (row) => row.graduate_count || 0,
    });
  }, [colleges, courses, term, sort]);

  const courseRows = useMemo(() => {
    const filtered = courses.filter((row) => {
      if (collegeFilter && String(row.college_id) !== collegeFilter) return false;
      if (!term) return true;
      return [row.name, row.course_code, row.college, row.kind_label, row.review_label, row.parent_name].join(" ").toLowerCase().includes(term);
    });
    return sortBy(filtered, sort, {
      name: (row) => row.name.toLowerCase(),
      course_code: (row) => (row.course_code || "").toLowerCase(),
      college: (row) => row.college.toLowerCase(),
      graduate_count: (row) => row.graduate_count || 0,
    });
  }, [courses, term, sort, collegeFilter]);

  const rows = tab === "colleges" ? collegeRows : courseRows;
  const pageCount = Math.max(1, Math.ceil(rows.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const visible = rows.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);
  const searchLabel = tab === "colleges" ? "Search colleges, codes, or courses" : "Search by course, course code, or college";

  function courseHit(course) {
    return Boolean(term) && [course.name, course.course_code].join(" ").toLowerCase().includes(term);
  }

  function coursesFor(college) {
    const list = courses.filter((course) => course.college_id === college.id);
    const hits = term ? list.filter(courseHit) : [];
    const shown = hits.length ? hits : list;
    return [...shown].sort((left, right) => left.name.localeCompare(right.name));
  }

  function revealedBySearch(college) {
    return Boolean(term) && courses.some((course) => course.college_id === college.id && courseHit(course));
  }

  function switchTab(next) {
    setTab(next);
    setQuery("");
    setCollegeFilter("");
    setPage(1);
    setSort({ key: "name", dir: "asc" });
    setOpenCollegeId(null);
    setOk("");
  }

  function clearCourseFilters() {
    setQuery("");
    setCollegeFilter("");
    setPage(1);
  }

  function openCollege(row = EMPTY_COLLEGE) {
    setFormError("");
    setFieldErrors({});
    setCollegeForm({ id: row.id, name: row.name || "", code: row.code || "" });
  }

  function openCourse(row = EMPTY_COURSE) {
    setFormError("");
    setFieldErrors({});
    if (row.college_id) setOpenCollegeId(Number(row.college_id));
    setCourseForm({
      id: row.id,
      college_id: row.college_id ? String(row.college_id) : "",
      parent_id: row.parent_id ? String(row.parent_id) : "",
      name: row.name || "",
      course_code: row.course_code || "",
      kind: row.kind || "undergraduate",
      review_status: row.review_status || "needs_review",
    });
  }

  function collegeIsOpen(college) {
    if (collapsedSearchIds.has(college.id)) return false;
    if (revealedBySearch(college)) return true;
    return openCollegeId === college.id;
  }

  function toggleCollege(college) {
    if (collegeIsOpen(college)) {
      setOpenCollegeId((current) => (current === college.id ? null : current));
      if (term) setCollapsedSearchIds((current) => new Set(current).add(college.id));
      return;
    }
    setCollapsedSearchIds((current) => {
      const next = new Set(current);
      next.delete(college.id);
      return next;
    });
    setOpenCollegeId(college.id);
  }

  function askRemove(kind, row) {
    const blocked = removalBlock(kind, row, courses);
    setRemoveError("");
    setRemoving({
      path: kind === "college" ? `/api/admin/academics/colleges/${row.id}` : `/api/admin/academics/courses/${row.id}`,
      title: blocked ? `This ${kind} cannot be deleted` : `Delete ${kind}?`,
      name: row.name,
      blocked,
      success: kind === "college" ? "College deleted." : "Course deleted.",
    });
  }

  async function saveCollege() {
    const problems = collegeProblems(collegeForm, colleges);
    setFieldErrors(problems);
    if (hasProblems(problems)) return;
    await persist(
      collegeForm.id ? `/api/admin/academics/colleges/${collegeForm.id}` : "/api/admin/academics/colleges",
      collegeForm.id ? "PATCH" : "POST",
      { name: collegeForm.name.trim(), code: collegeForm.code.trim(), confirm: false },
      collegeForm.id ? "College saved." : "College added.",
    );
  }

  async function saveCourse() {
    const problems = courseProblems(courseForm, courses);
    setFieldErrors(problems);
    if (hasProblems(problems)) return;
    await persist(
      courseForm.id ? `/api/admin/academics/courses/${courseForm.id}` : "/api/admin/academics/courses",
      courseForm.id ? "PATCH" : "POST",
      {
        college_id: Number(courseForm.college_id),
        parent_id: courseForm.parent_id ? Number(courseForm.parent_id) : null,
        name: courseForm.name.trim(),
        course_code: courseForm.course_code.trim(),
        kind: courseForm.kind,
        review_status: courseForm.review_status,
        confirm: false,
      },
      courseForm.id ? "Course saved." : "Course added.",
    );
  }

  async function persist(path, method, body, success) {
    setSaving(true);
    setFormError("");
    setError("");
    try {
      await api(path, { method, body, toast: false });
      setConfirm(null);
      setCollegeForm(null);
      setCourseForm(null);
      setFieldErrors({});
      setOk(success);
      await load();
    } catch (err) {
      const pending = confirmationDetail(err);
      if (pending) {
        setConfirm({ path, method, body, message: pending.message, success });
        return;
      }
      setFormError(err.message || "The change could not be saved.");
    } finally {
      setSaving(false);
    }
  }

  async function confirmSave() {
    if (!confirm) return;
    await persist(confirm.path, confirm.method, { ...confirm.body, confirm: true }, confirm.success);
  }

  async function confirmRemove() {
    if (!removing || removing.blocked) return;
    setSaving(true);
    setRemoveError("");
    try {
      await api(removing.path, { method: "DELETE", toast: false });
      setRemoving(null);
      setOk(removing.success);
      await load();
    } catch (err) {
      setRemoveError(err.message || "This record could not be deleted.");
    } finally {
      setSaving(false);
    }
  }

  const editorOpen = Boolean((collegeForm || courseForm) && !confirm);

  return (
    <PortalShell role="Admin">
      {ok ? <Alert type="ok" title="Saved">{ok}</Alert> : null}
      {data && error ? <Alert type="error">{error}</Alert> : null}
      <Panel
        title="Colleges and Courses"
        className="academics-catalog"
        description="Manage the colleges, academic programs, and course codes used throughout CareerSense."
      >
        <TabList
          label="Academic catalog"
          value={tab}
          onChange={switchTab}
          tabs={[["colleges", "Colleges"], ["courses", "Courses"]]}
        />
        <form className="academics-toolbar" onSubmit={(event) => event.preventDefault()}>
          <div className="search-field">
            <SearchIcon size={16} />
            <input
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
              placeholder={searchLabel}
              aria-label={searchLabel}
            />
          </div>
          {tab === "courses" ? (
            <select
              className="academics-college-filter"
              aria-label="Filter courses by college"
              value={collegeFilter}
              onChange={(event) => {
                setCollegeFilter(event.target.value);
                setPage(1);
              }}
            >
              <option value="">All colleges</option>
              {[...colleges].sort((left, right) => left.name.localeCompare(right.name)).map((college) => (
                <option key={college.id} value={String(college.id)}>{college.name}</option>
              ))}
            </select>
          ) : null}
          <button
            className="btn btn-navy"
            type="button"
            onClick={() => (tab === "colleges" ? openCollege() : openCourse())}
          >
            <PlusIcon size={16} />
            {tab === "colleges" ? "Add College" : "Add Course"}
          </button>
        </form>

        {error && !data ? (
          <LoadError onRetry={load}>{error}</LoadError>
        ) : busy && !data ? (
          <TableSkeleton rows={PAGE_SIZE} cols={5} />
        ) : !rows.length ? (
          <Empty
            title={term || collegeFilter ? "No matches" : tab === "colleges" ? "No colleges yet" : "No courses yet"}
            action={term || collegeFilter ? (
              <button className="btn btn-outline" type="button" onClick={clearCourseFilters}>Clear filters</button>
            ) : (
              <button className="btn btn-navy" type="button" onClick={() => (tab === "colleges" ? openCollege() : openCourse())}>
                <PlusIcon size={16} />
                {tab === "colleges" ? "Add College" : "Add Course"}
              </button>
            )}
          >
            {term || collegeFilter
              ? "Try a different name, code, or college."
              : tab === "colleges"
                ? "Add a college before assigning courses to it."
                : "Add the programs graduates can be assigned to."}
          </Empty>
        ) : (
          <>
            {term || (tab === "courses" && collegeFilter) ? (
              <p className="academics-match" role="status">
                {tab === "colleges"
                  ? `${rows.length} ${rows.length === 1 ? "college" : "colleges"}${rows.some(revealedBySearch) ? ". Matching courses are open below." : ""}`
                  : `${rows.length} ${rows.length === 1 ? "course" : "courses"}`}
              </p>
            ) : null}
            {tab === "colleges" ? (
              <div className="college-board">
                <div className="college-head">
                  <div className="college-head-main">
                    <span />
                    <SortButton column="name" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>College</SortButton>
                    <SortButton column="code" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Code</SortButton>
                    <span className="num"><SortButton column="course_count" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Courses</SortButton></span>
                    <span className="num"><SortButton column="graduate_count" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Graduates</SortButton></span>
                  </div>
                </div>
                {visible.map((row) => {
                  const open = collegeIsOpen(row);
                  const listed = open ? coursesFor(row) : [];
                  const panelId = `college-courses-${row.id}`;
                  return (
                    <section className={`college-item${open ? " is-open" : ""}`} key={row.id}>
                      <div className="college-row">
                        <button
                          type="button"
                          className="college-summary"
                          aria-expanded={open}
                          aria-controls={panelId}
                          onClick={() => toggleCollege(row)}
                        >
                          <span className="college-chev" aria-hidden="true"><ChevronDownIcon size={16} /></span>
                          <span className="college-name">{row.name}</span>
                          <span className={`college-code${row.code ? "" : " is-empty"}`}>{row.code || "—"}</span>
                          <span className="college-count">{row.course_count}</span>
                          <span className="college-count">{row.graduate_count}</span>
                          <span className="college-meta">
                            {row.code || "No code"} · {row.course_count} {row.course_count === 1 ? "course" : "courses"} · {row.graduate_count} {row.graduate_count === 1 ? "graduate" : "graduates"}
                          </span>
                        </button>
                        <div className="college-actions">
                          <RowActions
                            more={[
                              { id: "edit", label: "Edit College", icon: PencilIcon, onClick: () => openCollege(row) },
                              { id: "delete", label: "Delete College", danger: true, onClick: () => askRemove("college", row) },
                            ]}
                          />
                        </div>
                      </div>
                      {open ? (
                        <div className="college-courses" id={panelId}>
                          {listed.length ? listed.map((course) => (
                            <div className={`college-course${courseHit(course) ? " is-match" : ""}`} key={course.id}>
                              <span className="college-course-name">{course.name}</span>
                              <span className={`college-course-code${course.course_code ? "" : " is-empty"}`}>{course.course_code || "—"}</span>
                              <div className="college-course-actions">
                                <RowActions
                                  more={[
                                    { id: "edit", label: "Edit Course", icon: PencilIcon, onClick: () => openCourse(course) },
                                    { id: "delete", label: "Delete Course", danger: true, onClick: () => askRemove("course", course) },
                                  ]}
                                />
                              </div>
                            </div>
                          )) : (
                            <div className="college-empty">
                              <p>No courses in this college yet.</p>
                              <button className="btn btn-outline btn-sm" type="button" onClick={() => openCourse({ ...EMPTY_COURSE, college_id: row.id })}>
                                <PlusIcon size={14} />
                                Add Course
                              </button>
                            </div>
                          )}
                          {listed.length ? (
                            <div className="college-course-add">
                              <button className="btn btn-outline btn-sm" type="button" onClick={() => openCourse({ ...EMPTY_COURSE, college_id: row.id })}>
                                <PlusIcon size={14} />
                                Add Course
                              </button>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </section>
                  );
                })}
              </div>
            ) : (
              <div className="table-wrap">
                <table className="data stack">
                  <thead>
                    <tr>
                      <th><SortButton column="name" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Course</SortButton></th>
                      <th className="cell-code"><SortButton column="course_code" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>Course Code</SortButton></th>
                      <th><SortButton column="college" sort={sort} onSort={(key) => setSort((prev) => toggleSort(prev, key))}>College</SortButton></th>
                      <th className="cell-actions">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {visible.map((row) => (
                      <tr key={row.id}>
                        <td className="cell-title" data-label="Course">{row.name}</td>
                        <td className="cell-code" data-label="Course Code">{row.course_code || <span className="muted">—</span>}</td>
                        <td data-label="College">{row.college}</td>
                        <td className="cell-actions" data-label="Actions">
                          <RowActions
                            more={[
                              { id: "edit", label: "Edit Course", icon: PencilIcon, onClick: () => openCourse(row) },
                              { id: "delete", label: "Delete Course", danger: true, onClick: () => askRemove("course", row) },
                            ]}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}
        {rows.length > PAGE_SIZE ? (
          <Pager page={safePage} pageSize={PAGE_SIZE} total={rows.length} onPage={setPage} />
        ) : null}
      </Panel>

      {editorOpen && collegeForm ? (
        <Dialog
          title={collegeForm.id ? "Edit college" : "Add college"}
          description="This name is the official college used in dropdowns, imports, and reports."
          confirmLabel="Save"
          busy={saving}
          onConfirm={saveCollege}
          onClose={() => { if (!saving) setCollegeForm(null); }}
        >
          <Alert type="error">{formError}</Alert>
          <Field label="College name" required error={fieldErrors.name}>
            <input
              value={collegeForm.name}
              placeholder="College of Business and Accountancy"
              onChange={(event) => {
                setCollegeForm({ ...collegeForm, name: event.target.value });
                setFieldErrors((prev) => ({ ...prev, name: "" }));
              }}
            />
          </Field>
          <Field label="College code" hint="Optional. Graduate records keep the college name." error={fieldErrors.code}>
            <input
              value={collegeForm.code}
              placeholder="CBA"
              onChange={(event) => {
                setCollegeForm({ ...collegeForm, code: event.target.value });
                setFieldErrors((prev) => ({ ...prev, code: "" }));
              }}
            />
          </Field>
        </Dialog>
      ) : null}

      {editorOpen && courseForm ? (
        <Dialog
          title={courseForm.id ? "Edit course" : "Add course"}
          description="Enter the college, program name, and official course code used across CareerSense."
          confirmLabel="Save"
          busy={saving}
          onConfirm={saveCourse}
          onClose={() => { if (!saving) setCourseForm(null); }}
        >
          <Alert type="error">{formError}</Alert>
          <Field label="College" required error={fieldErrors.college_id}>
            <select
              value={colleges.some((row) => String(row.id) === courseForm.college_id) ? courseForm.college_id : ""}
              onChange={(event) => {
                const collegeId = event.target.value;
                const parentStillValid = courses.some((row) => String(row.id) === courseForm.parent_id && String(row.college_id) === collegeId);
                setCourseForm({
                  ...courseForm,
                  college_id: collegeId,
                  parent_id: parentStillValid ? courseForm.parent_id : "",
                });
                setFieldErrors((prev) => ({ ...prev, college_id: "" }));
              }}
            >
              <option value="">Select a college</option>
              {colleges.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </Field>
          <Field label="Course name" required error={fieldErrors.name}>
            <input
              value={courseForm.name}
              placeholder="Bachelor of Science in Accountancy"
              onChange={(event) => {
                setCourseForm({ ...courseForm, name: event.target.value });
                setFieldErrors((prev) => ({ ...prev, name: "" }));
              }}
            />
          </Field>
          <Field
            label="Official course code"
            hint="Leave this blank until the Registrar’s Office confirms it. Do not enter a guessed abbreviation."
            error={fieldErrors.course_code}
          >
            <input
              value={courseForm.course_code}
              placeholder="BSA"
              onChange={(event) => {
                setCourseForm({ ...courseForm, course_code: event.target.value });
                setFieldErrors((prev) => ({ ...prev, course_code: "" }));
              }}
            />
          </Field>
        </Dialog>
      ) : null}

      {confirm ? (
        <Dialog
          title="Update linked graduate records?"
          description={confirm.message}
          confirmLabel="Save changes"
          busy={saving}
          onConfirm={confirmSave}
          onClose={() => { if (!saving) setConfirm(null); }}
        >
          <p>Only the college, course name, or official course code on those records will change. Names, email addresses, and other graduate details stay the same.</p>
        </Dialog>
      ) : null}

      {removing ? (
        <Dialog
          title={removing.title}
          description={removing.name}
          confirmLabel="Delete"
          danger={!removing.blocked}
          busy={saving}
          onConfirm={removing.blocked ? undefined : confirmRemove}
          onClose={() => { if (!saving) { setRemoving(null); setRemoveError(""); } }}
          hideActions={Boolean(removing.blocked)}
          footer={removing.blocked ? (
            <button type="button" className="btn btn-navy" onClick={() => setRemoving(null)}>Close</button>
          ) : null}
        >
          <Alert type="error">{removeError}</Alert>
          <p>{removing.blocked || "This removes the catalog entry. No graduate record uses it, so existing graduate details stay unchanged."}</p>
        </Dialog>
      ) : null}
    </PortalShell>
  );
}
