export function coursesForCollege(catalog, college) {
  const selected = String(college || "");
  const names = selected
    ? (catalog?.pairs || []).filter((item) => item.college === selected && item.course).map((item) => item.course)
    : (catalog?.courses || []);
  return [...new Set(names)].sort((left, right) => left.localeCompare(right));
}

export function programChoices(catalog, college) {
  const selected = String(college || "");
  const programs = catalog?.programs?.length
    ? catalog.programs
    : (catalog?.pairs || []).map((item) => ({ college: item.college, course: item.course, course_code: "" }));
  const seen = new Set();
  return programs
    .filter((item) => item.course && (!selected || item.college === selected))
    .filter((item) => {
      if (seen.has(item.course)) return false;
      seen.add(item.course);
      return true;
    })
    .sort((left, right) => left.course.localeCompare(right.course));
}

export function courseLabel(program) {
  const course = typeof program === "string" ? program : (program?.course || program?.program || program?.name || "");
  const kind = typeof program === "string" ? "" : (program?.kind || "");
  const note = {
    graduate: "graduate",
    professional: "professional",
    diploma: "diploma",
    certificate: "certificate",
    combined: "combined pathway",
    pathway: "pathway",
    major: "major",
    specialization: "specialization",
  }[kind];
  return note ? `${course} (${note})` : course;
}

export function courseCodeFor(catalog, college, course) {
  return programChoices(catalog, college).find((item) => item.course === course)?.course_code || "";
}
