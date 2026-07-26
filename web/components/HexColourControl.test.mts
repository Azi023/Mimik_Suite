import assert from "node:assert/strict";
import test from "node:test";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";

import {
  HexColourControl,
  hexColourState,
  parseHexColour,
} from "./HexColourControl.ts";

test("parseHexColour accepts three- and six-digit hex with or without a hash", (): void => {
  const cases = [
    ["#abc", "#AABBCC"],
    ["abc", "#AABBCC"],
    ["#AABBCC", "#AABBCC"],
    ["aabbcc", "#AABBCC"],
  ] as const;

  for (const [input, expected] of cases) {
    assert.equal(parseHexColour(input), expected);
  }
});

test("parseHexColour rejects malformed and empty values", (): void => {
  for (const input of ["xyz", "#12", "#1234567", ""]) {
    assert.equal(parseHexColour(input), null);
  }
});

test("hexColourState retains rejected text and marks it invalid", (): void => {
  assert.deepEqual(hexColourState("xyz"), {
    value: "xyz",
    normalized: null,
    invalid: true,
  });
});

test("HexColourControl renders a named text input for direct hex entry", (): void => {
  const html = renderToStaticMarkup(
    createElement(HexColourControl, {
      value: "xyz",
      onChange: (): void => undefined,
      label: "Primary colour",
      name: "color_hex",
      "data-api-field": "hex",
    }),
  );

  assert.match(html, /type="text"/);
  assert.match(html, /name="color_hex"/);
  assert.match(html, /data-api-field="hex"/);
  assert.match(html, /aria-invalid="true"/);
  assert.match(html, />Enter a 3- or 6-digit hex value\.</);
});
