import assert from "node:assert/strict";
import test from "node:test";
import {
  credentialIsPopulated,
  credentialReportChoice,
  isSuggestedCredential,
  isSuggestedProgram,
  programIsPopulated,
} from "./studiesSection.js";

const resume = {
  parser_source: "heuristic",
  further_studies: [{ course_degree: "Master of Information Technology", school: "Angeles University Foundation" }],
  certifications: [{ name: "Google Analytics Certificate", awarding_body: "Google", year: "2023" }],
  seminars: [{ name: "Career Readiness Seminar", location: "Angeles City", organizer: "OAAPS", year: "2022" }],
  awards: [{ name: "Dean's Lister", issuer: "AUF", description: "College honors" }],
};

test("an untouched program is empty and a filled program is kept for confirmation", () => {
  assert.equal(programIsPopulated({ school: "", course_degree: "", is_graduated: "No" }), false);
  assert.equal(programIsPopulated({ school: "AUF", course_degree: "", is_graduated: "No" }), true);
  assert.equal(programIsPopulated({ school: "", course_degree: "", is_graduated: "Yes" }), true);
});

test("resume programs are suggestions only when the parser produced a readable resume", () => {
  const row = { course_degree: "Master of Information Technology", school: "Angeles University Foundation" };
  assert.equal(isSuggestedProgram(row, resume), true);
  assert.equal(isSuggestedProgram({ ...row, course_degree: "Master of Education" }, resume), false);
  assert.equal(isSuggestedProgram(row, { ...resume, parser_source: "failed" }), false);
  assert.equal(isSuggestedProgram(row, { ...resume, parser_source: "empty" }), false);
});

test("credential suggestions follow the resume name and ignore a failed parse", () => {
  assert.equal(isSuggestedCredential({ name: "Google Analytics Certificate" }, resume, "certifications"), true);
  assert.equal(isSuggestedCredential({ name: "Page 1 of 1" }, resume, "certifications"), false);
  assert.equal(isSuggestedCredential({ name: "Career Readiness Seminar" }, resume, "seminars"), true);
  assert.equal(isSuggestedCredential({ name: "Dean's Lister" }, resume, "awards"), true);
  assert.equal(isSuggestedCredential({ name: "Dean's Lister" }, { parser_source: "failed", awards: resume.awards }, "awards"), false);
});

test("credential yes or no keeps a saved answer and opens when a resume already listed one", () => {
  assert.equal(credentialReportChoice("No", [{ name: "Google Analytics Certificate" }]), "No");
  assert.equal(credentialReportChoice("Yes", []), "Yes");
  assert.equal(credentialReportChoice("", [{ name: "Google Analytics Certificate" }]), "Yes");
  assert.equal(credentialReportChoice("", []), "No");
});

test("optional credential rows stay empty until a detail is entered", () => {
  assert.equal(credentialIsPopulated({ name: "", awarding_body: "", year: "" }, "certifications"), false);
  assert.equal(credentialIsPopulated({ name: "", location: "Angeles City", organizer: "" }, "seminars"), true);
  assert.equal(credentialIsPopulated({ name: "", issuer: "", description: "College honors" }, "awards"), true);
});
