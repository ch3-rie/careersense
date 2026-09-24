export function coursesForCollege(catalog, college) {
  const selected = String(college || "");
  const names = selected
    ? (catalog?.pairs || []).filter((item) => item.college === selected && item.course).map((item) => item.course)
    : (catalog?.courses || []);
  return [...new Set(names)].sort((left, right) => left.localeCompare(right));
}
