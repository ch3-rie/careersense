import assert from "node:assert/strict";
import test from "node:test";
import { coursesForCollege } from "./academicFilters.js";

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
