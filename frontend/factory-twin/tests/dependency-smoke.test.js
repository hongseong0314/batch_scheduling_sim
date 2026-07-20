import assert from "node:assert/strict";
import test from "node:test";

import { REVISION } from "three";

test("Three.js is available to the factory twin bundle", () => {
  assert.match(REVISION, /^\d+$/);
});
