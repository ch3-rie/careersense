import assert from "node:assert/strict";
import test from "node:test";
import { courseCodeFor, courseLabel, coursesForCollege, createProgramIndex, displayProgramName, programChoices } from "./academicFilters.js";

const catalog = {
  colleges: ["College of Computer Studies", "College of Nursing"],
  courses: [
    "Bachelor of Science in Information Technology",
    "Bachelor of Science in Nursing",
  ],
  pairs: [
    { college: "College of Computer Studies", course: "Bachelor of Science in Information Technology" },
    { college: "College of Nursing", course: "Bachelor of Science in Nursing" },
  ],
};

test("all colleges shows every course", () => {
  assert.deepEqual(coursesForCollege(catalog, ""), [
    "Bachelor of Science in Information Technology",
    "Bachelor of Science in Nursing",
  ]);
});

test("a college shows only its courses", () => {
  assert.deepEqual(coursesForCollege(catalog, "College of Nursing"), [
    "Bachelor of Science in Nursing",
  ]);
});

test("a selected course fills its course code", () => {
  const programs = {
    programs: [
      { college: "College of Nursing", course: "Bachelor of Science in Nursing", course_code: "BSN" },
      { college: "College of Computer Studies", course: "Bachelor of Science in Information Technology", course_code: "BSIT" },
    ],
  };
  assert.equal(courseCodeFor(programs, "College of Nursing", "Bachelor of Science in Nursing"), "BSN");
  assert.deepEqual(
    programChoices(programs, "College of Computer Studies").map((item) => item.course),
    ["Bachelor of Science in Information Technology"]
  );
  assert.equal(courseCodeFor(programs, "College of Nursing", "Bachelor of Science in Information Technology"), "");
  assert.equal(courseLabel({ course: "BS Business Administration — Marketing Management", kind: "specialization" }), "BS Business Administration — Marketing Management (specialization)");
  assert.equal(courseLabel({ course: "BS Nursing", kind: "undergraduate" }), "BS Nursing");
});

const searchCatalog = {
  programs: [
    { college: "College of Computer Studies", course: "BS Computer Science", course_code: "BSCS", kind: "undergraduate" },
    { college: "College of Computer Studies", course: "Bachelor of Science in Information Technology", course_code: "BSIT", kind: "undergraduate" },
    { college: "College of Engineering and Architecture", course: "BS Civil Engineering", course_code: "BSCE", kind: "undergraduate" },
    { college: "College of Engineering and Architecture", course: "BS Computer Engineering", course_code: "BSCPE", kind: "undergraduate" },
    { college: "College of Nursing", course: "BS Nursing", course_code: "BSN", kind: "undergraduate" },
  ],
};

test("abbreviations, partial names, and spacing resolve to the catalog program", () => {
  const index = createProgramIndex(searchCatalog.programs);
  const names = (term) => index.programsForTerm(term).map((item) => item.course).sort();
  assert.deepEqual(names("BS CS"), ["BS Computer Science"]);
  assert.deepEqual(names("  bscs "), ["BS Computer Science"]);
  assert.deepEqual(names("BS IT"), ["Bachelor of Science in Information Technology"]);
  assert.deepEqual(names("computer"), ["BS Computer Engineering", "BS Computer Science"]);
  assert.deepEqual(names("Comp Sci"), ["BS Computer Science"]);
  assert.deepEqual(names("BSC"), ["BS Civil Engineering", "BS Computer Engineering", "BS Computer Science"]);
  assert.deepEqual(names("BS CE"), ["BS Civil Engineering"]);
  assert.deepEqual(names("ZZZ"), []);
  assert.equal(
    index.displayName("BSCS", "BSCS", "College of Computer Studies"),
    "BS Computer Science",
  );
  assert.equal(
    displayProgramName(searchCatalog, "Bachelor of Science in Information Technology", "BSIT"),
    "Bachelor of Science in Information Technology",
  );
  assert.equal(index.matchesRecord("BS CS", { degree: "Bachelor of Science in Computer Science", courseCode: "BSCS" }), true);
  assert.equal(index.matchesRecord("BS CS", { degree: "BS Nursing", courseCode: "BSN" }), false);
});
