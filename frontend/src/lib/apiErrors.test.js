import assert from "node:assert/strict";
import test from "node:test";
import { messageForStatus, networkErrorNotice, usableDetail } from "./apiErrors.js";

test("400 keeps a readable validation detail", () => {
  const notice = messageForStatus(400, "Please answer: Given name.");
  assert.equal(notice.type, "error");
  assert.equal(notice.message, "Please answer: Given name.");
});

test("400 hides technical details", () => {
  const notice = messageForStatus(400, "Traceback (most recent call last): ValueError");
  assert.equal(notice.message, "Please review your information and try again.");
  assert.equal(usableDetail("Traceback (most recent call last): ValueError"), "");
});

test("401 uses a session message", () => {
  const notice = messageForStatus(401, "Could not validate credentials");
  assert.match(notice.message, /session has expired/i);
});

test("403, 404, 409, and 422 have plain messages", () => {
  assert.match(messageForStatus(403, "").message, /permission/i);
  assert.match(messageForStatus(404, "").message, /could not be found/i);
  assert.match(messageForStatus(409, "").message, /conflicts/i);
  assert.match(messageForStatus(422, "Please answer: Institution.").message, /Institution/);
  assert.match(messageForStatus(422, "").message, /highlighted fields/i);
});

test("429 and 500 stay generic", () => {
  assert.match(messageForStatus(429, "slow down").message, /too many attempts/i);
  const server = messageForStatus(500, "sqlalchemy.exc.OperationalError: password");
  assert.match(server.message, /something went wrong on our side/i);
  assert.doesNotMatch(server.message, /sqlalchemy|password/i);
});

test("network failures do not mention the client library", () => {
  const notice = networkErrorNotice();
  assert.match(notice.message, /connection/i);
  assert.doesNotMatch(notice.message, /fetch|axios/i);
});
