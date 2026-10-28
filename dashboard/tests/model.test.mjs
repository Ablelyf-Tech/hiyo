import test from "node:test";
import assert from "node:assert/strict";
import { metrics, duration } from "../src/model.js";
test("empty queue has no invented progress", () =>
  assert.deepEqual(metrics([]), { completed: 0, remaining: 0, progress: 0 }));
test("blocked and running tasks are remaining", () =>
  assert.deepEqual(
    metrics([
      { status: "completed" },
      { status: "blocked" },
      { status: "running" },
    ]),
    { completed: 1, remaining: 2, progress: 33 },
  ));
test("runtime is hours and minutes", () =>
  assert.equal(duration(3665), "1h 1m"));
