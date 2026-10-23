import assert from "node:assert/strict";
import test from "node:test";
import { courseCodeFor, courseLabel, coursesForCollege, programChoices } from "./academicFilters.js";

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
