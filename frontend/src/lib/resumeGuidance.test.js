import assert from "node:assert/strict";
import test from "node:test";
import { resumeGuidance } from "./resumeGuidance.js";

const resume = {
  parser_source: "heuristic",
  is_currently_employed: "Yes",
  experiences: [
    { job_title: "Junior Developer", employer: "First Co", is_current: "No", related_to_degree: "Yes" },
    { job_title: "Software Developer", employer: "ABC Company", is_current: "Yes", related_to_degree: "Yes" },
  ],
  further_studies: [{ course_degree: "Master of Information Technology", school: "Angeles University Foundation" }],
  course_alignment: { related_to_degree: "Yes", confidence: 0.8, job_title: "Software Developer" },
  extraction_meta: { confidence: { current_employment: "high", job_title: "high" } },
};

test("current employment No cites the resume job and does not force Yes", () => {
  const note = resumeGuidance("is_currently_employed", "No", resume);
  assert.match(note, /Software Developer at ABC Company/);
  assert.match(note, /verify/i);
  assert.doesNotMatch(note, /wrong|incorrect answer/i);
});

test("current employment Yes that matches the resume has no note", () => {
  assert.equal(resumeGuidance("is_currently_employed", "Yes", resume), "");
});

test("missing resume evidence produces no note", () => {
  assert.equal(resumeGuidance("is_currently_employed", "No", null), "");
  assert.equal(resumeGuidance("is_currently_employed", "No", { parser_source: "failed", is_currently_employed: "Yes" }), "");
  assert.equal(resumeGuidance("ever_employed", "No", { parser_source: "heuristic", experiences: [] }), "");
});

test("a historical employer alone does not imply current employment", () => {
  const pastOnly = {
    parser_source: "heuristic",
    is_currently_employed: "No",
    experiences: [{ job_title: "Intern", employer: "Old Co", is_current: "No" }],
    extraction_meta: { confidence: { current_employment: "high" } },
  };
  assert.equal(resumeGuidance("is_currently_employed", "No", pastOnly), "");
  assert.match(resumeGuidance("is_currently_employed", "Yes", pastOnly), /does not appear to list a current job/i);
});

test("ever employed, studies, and alignment notes follow the conflicting answer", () => {
  assert.match(resumeGuidance("ever_employed", "No", resume), /Junior Developer/);
  assert.equal(resumeGuidance("ever_employed", "Yes", resume), "");
  assert.match(resumeGuidance("enroll_further_studies", "No", resume), /Master of Information Technology/);
  assert.match(resumeGuidance("enroll_further_studies", "No", resume), /before continuing/);
  assert.match(resumeGuidance("enroll_further_studies", "Yes", resume), /Suggested from your resume/);
  assert.match(resumeGuidance("enroll_further_studies", "Yes", resume), /not saved until you submit/);
  assert.match(resumeGuidance("present_related_degree", "No", resume), /related to your degree/i);
  assert.equal(resumeGuidance("present_related_degree", "Yes", resume), "");
  assert.match(resumeGuidance("first_related", "No", resume), /first job/i);
  assert.equal(resumeGuidance("first_related", "Yes", resume), "");
});

test("low alignment confidence stays uncertain", () => {
  const unsure = { ...resume, course_alignment: { related_to_degree: "Yes", confidence: 0.2 } };
  const note = resumeGuidance("present_related_degree", "No", unsure);
  assert.match(note, /may be relevant/i);
  assert.doesNotMatch(note, /related to your degree/i);
});

test("changing back to the resume suggestion removes the note", () => {
  assert.notEqual(resumeGuidance("present_job_is_first", "Yes", resume), "");
  assert.equal(resumeGuidance("present_job_is_first", "No", resume), "");
});

test("long extracted titles are shortened in the note", () => {
  const noisy = {
    ...resume,
    experiences: [{ job_title: "A".repeat(120), employer: "ABC Company", is_current: "Yes" }],
  };
  const note = resumeGuidance("is_currently_employed", "No", noisy);
  assert.match(note, /…/);
  assert.ok(note.length < 280);
});

test("unrelated questions never get resume notes", () => {
  assert.equal(resumeGuidance("mentoring_rating", "No", resume), "");
  assert.equal(resumeGuidance("skills", "Python", resume), "");
});

test("further studies guidance follows resume evidence and does not block an answer", () => {
  const detected = resumeGuidance("enroll_further_studies", "No", resume);
  assert.match(detected, /appears to include further studies/);
  assert.doesNotMatch(detected, /cannot submit|blocked|must select yes/i);

  const manual = resumeGuidance("enroll_further_studies", "Yes", {
    parser_source: "heuristic",
    further_studies_evidence: { status: "not_detected", entries: [] },
  });
  assert.match(manual, /did not find clear evidence/i);
  assert.doesNotMatch(manual, /appears to include further studies/);

  const unclear = resumeGuidance("enroll_further_studies", "No", {
    parser_source: "heuristic",
    further_studies_evidence: { status: "unclear", entries: [{ program: "Studies", confidence: "low" }] },
  });
  assert.match(unclear, /does not clearly show/);
  assert.doesNotMatch(unclear, /Studies/);

  assert.equal(resumeGuidance("enroll_further_studies", "No", { parser_source: "failed", further_studies: resume.further_studies }), "");
  assert.equal(resumeGuidance("enroll_further_studies", "Yes", { parser_source: "empty" }), "");
});
