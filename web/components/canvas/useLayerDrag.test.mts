import test from "node:test";
import assert from "node:assert/strict";
import { pointerMovedPastThreshold } from "./useLayerDrag.ts";

test("pointer movement must cross the click threshold before it becomes a drag", (): void => {
  assert.equal(pointerMovedPastThreshold(100, 100, 102, 102), false);
  assert.equal(pointerMovedPastThreshold(100, 100, 103, 100), true);
  assert.equal(pointerMovedPastThreshold(100, 100, 100, 97), true);
});
