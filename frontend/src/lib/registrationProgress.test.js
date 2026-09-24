import assert from "node:assert/strict";
import test from "node:test";
import { registrationHasProgress } from "./registrationProgress.js";

const empty = { email: "", password: "", confirm_password: "", resume: null, privacy_consent: false };

test("an empty registration can be left without treating it as progress", () => {
  assert.equal(registrationHasProgress(1, empty), false);
});

test("step 1 counts email, password, resume, and consent as progress", () => {
  assert.equal(registrationHasProgress(1, { ...empty, email: "  " }), false);
  assert.equal(registrationHasProgress(1, { ...empty, email: "a@b.co" }), true);
  assert.equal(registrationHasProgress(1, { ...empty, password: "secret" }), true);
  assert.equal(registrationHasProgress(1, { ...empty, confirm_password: "secret" }), true);
  assert.equal(registrationHasProgress(1, { ...empty, resume: {} }), true);
  assert.equal(registrationHasProgress(1, { ...empty, privacy_consent: true }), true);
});

test("step 2 is progress even before the graduate edits prefilled answers", () => {
  assert.equal(registrationHasProgress(2, empty), true);
});

test("a submitted registration is no longer unsaved progress", () => {
  assert.equal(registrationHasProgress(3, { ...empty, email: "a@b.co" }), false);
  assert.equal(registrationHasProgress(2, empty, { submitted: true }), false);
});
