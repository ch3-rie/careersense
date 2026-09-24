import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { safeAlumniPath, safeHttpUrl } from "./safeUrl.js";

describe("safeHttpUrl", () => {
  it("allows http and https URLs", () => {
    assert.equal(safeHttpUrl("https://auf.edu.ph/perks"), "https://auf.edu.ph/perks");
    assert.match(safeHttpUrl("auf.edu.ph"), /^https:\/\/auf\.edu\.ph\/?$/);
  });

  it("rejects javascript and data URLs", () => {
    assert.equal(safeHttpUrl("javascript:alert(1)"), "");
    assert.equal(safeHttpUrl("data:text/html,hi"), "");
    assert.equal(safeHttpUrl(""), "");
  });
});

describe("safeAlumniPath", () => {
  it("allows alumni routes and hashes", () => {
    assert.equal(safeAlumniPath("/alumni/card"), "/alumni/card");
    assert.equal(safeAlumniPath("/alumni#contact"), "/alumni#contact");
  });

  it("rejects traversal and protocol-relative paths", () => {
    assert.equal(safeAlumniPath("/alumni/../admin"), "");
    assert.equal(safeAlumniPath("//evil.example"), "");
    assert.equal(safeAlumniPath("/admin"), "");
  });
});
