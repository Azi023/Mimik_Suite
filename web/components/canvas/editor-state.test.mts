import test from "node:test";
import assert from "node:assert/strict";
import {
  appendOp,
  applyState,
  canRedo,
  canUndo,
  dirtyLayerIds,
  fold,
  layerTransformAttr,
  redo,
  removeOp,
  toCanvasRevision,
  transformedBBox,
  undo,
  type DocOp,
  type EditHistory,
  type EditorBaseState,
} from "./editor-state.ts";

const EMPTY_HISTORY: EditHistory = { ops: [], redo: [] };

function op(overrides: Partial<DocOp>): DocOp {
  return {
    id: "op-1",
    layer: "layer-headline",
    kind: "text",
    text: "Original",
    label: "Headline text",
    ...overrides,
  };
}

class FakeDocument {
  createElementNS(): FakeElement {
    return new FakeElement(this);
  }
}

class FakeElement {
  readonly attributes = new Map<string, string>();
  readonly selectors = new Map<string, FakeElement>();
  readonly style = { display: "" };
  children: FakeElement[] = [];
  ownerDocument: FakeDocument;
  parent: FakeElement | null = null;
  textContent: string | null = "";
  private html = "";

  constructor(ownerDocument: FakeDocument) {
    this.ownerDocument = ownerDocument;
  }

  get namespaceURI(): string {
    return "http://www.w3.org/2000/svg";
  }

  get innerHTML(): string {
    return this.html;
  }

  set innerHTML(value: string) {
    this.html = value;
    this.children = [];
  }

  setAttribute(name: string, value: string): void {
    this.attributes.set(name, value);
    if (name === "style") {
      const display = /display\\s*:\\s*([^;]+)/.exec(value)?.[1] ?? "";
      this.style.display = display;
    }
  }

  getAttribute(name: string): string | null {
    return this.attributes.get(name) ?? null;
  }

  removeAttribute(name: string): void {
    this.attributes.delete(name);
    if (name === "style") this.style.display = "";
  }

  querySelector<T extends Element>(selector: string): T | null {
    return (this.selectors.get(selector) as unknown as T | undefined) ?? null;
  }

  appendChild<T extends FakeElement>(child: T): T {
    child.parent = this;
    this.children.push(child);
    return child;
  }

  remove(): void {
    if (this.parent === null) return;
    this.parent.children = this.parent.children.filter((child) => child !== this);
    this.parent = null;
  }

  getComputedTextLength(): number {
    return (this.textContent ?? "").length * 10;
  }
}

test("fold keeps discrete ops and applies last-write-wins per layer and kind", (): void => {
  const ops: DocOp[] = [
    op({ id: "text-1", text: "First" }),
    op({
      id: "fill-1",
      kind: "fill",
      text: undefined,
      fillRole: "primary",
      label: "Headline color",
    }),
    op({ id: "text-2", text: "Final" }),
    op({
      id: "visibility-1",
      layer: "layer-panel",
      kind: "visible",
      text: undefined,
      visible: false,
      label: "Hide Panel",
    }),
  ];

  const folded = fold(ops);

  assert.equal(ops.length, 4);
  assert.equal(folded.text["layer-headline"], "Final");
  assert.equal(folded.fill["layer-headline"], "primary");
  assert.equal(folded.visible["layer-panel"], false);
});

test("appendOp pushes one discrete op and clears redo", (): void => {
  const history: EditHistory = {
    ops: [op({ id: "existing" })],
    redo: [op({ id: "redo" })],
  };
  const nextOp = op({
    id: "transform-1",
    kind: "transform",
    text: undefined,
    transform: { dx: 24, dy: -8, scale: 1.1 },
    label: "Move Headline",
  });

  const next = appendOp(history, nextOp);

  assert.deepEqual(next.ops, [...history.ops, nextOp]);
  assert.deepEqual(next.redo, []);
  assert.notEqual(next, history);
});

test("undo moves the newest applied op onto the redo stack", (): void => {
  const first = op({ id: "first", text: "First" });
  const second = op({ id: "second", text: "Second" });
  const history: EditHistory = {
    ops: [first, second],
    redo: [op({ id: "older-redo" })],
  };

  const next = undo(history);

  assert.deepEqual(next.ops, [first]);
  assert.deepEqual(next.redo, [...history.redo, second]);
  assert.deepEqual(history.ops, [first, second]);
});

test("redo restores the newest redo op to the applied stack", (): void => {
  const applied = op({ id: "applied" });
  const olderRedo = op({ id: "older-redo", text: "Older" });
  const newestRedo = op({ id: "newest-redo", text: "Newest" });
  const history: EditHistory = {
    ops: [applied],
    redo: [olderRedo, newestRedo],
  };

  const next = redo(history);

  assert.deepEqual(next.ops, [applied, newestRedo]);
  assert.deepEqual(next.redo, [olderRedo]);
  assert.deepEqual(history.redo, [olderRedo, newestRedo]);
});

test("canUndo and canRedo reflect their respective stacks", (): void => {
  assert.equal(canUndo(EMPTY_HISTORY), false);
  assert.equal(canRedo(EMPTY_HISTORY), false);
  assert.equal(canUndo({ ops: [op({ id: "applied" })], redo: [] }), true);
  assert.equal(canRedo({ ops: [], redo: [op({ id: "redo" })] }), true);
});

test("removeOp removes only the requested applied op and preserves redo", (): void => {
  const first = op({ id: "first", text: "First" });
  const removed = op({
    id: "remove-me",
    layer: "layer-panel",
    kind: "visible",
    text: undefined,
    visible: false,
    label: "Hide Panel",
  });
  const last = op({ id: "last", text: "Last" });
  const redoStack = [op({ id: "redo" })];
  const history: EditHistory = {
    ops: [first, removed, last],
    redo: redoStack,
  };

  const next = removeOp(history, removed.id);

  assert.deepEqual(next.ops, [first, last]);
  assert.equal(next.redo, redoStack);
  assert.deepEqual(history.ops, [first, removed, last]);
});

test("toCanvasRevision emits text plus one full folded layer op per touched layer", (): void => {
  const folded = fold([
    op({ id: "text", text: "Wrapped headline" }),
    op({
      id: "fill",
      kind: "fill",
      text: undefined,
      fillRole: "accent",
      label: "Headline color",
    }),
    op({
      id: "move",
      kind: "transform",
      text: undefined,
      transform: { dx: 10.126, dy: -4.555, scale: 1.23456 },
      label: "Move Headline",
    }),
    op({
      id: "hide",
      layer: "layer-panel",
      kind: "visible",
      text: undefined,
      visible: false,
      label: "Hide Panel",
    }),
  ]);

  assert.deepEqual(toCanvasRevision(folded), {
    text_edits: { headline: "Wrapped headline" },
    layer_ops: [
      {
        layer_id: "layer-panel",
        dx: 0,
        dy: 0,
        scale: 1,
        visible: false,
        fill_role: null,
      },
      {
        layer_id: "layer-headline",
        dx: 10.13,
        dy: -4.55,
        scale: 1.2346,
        visible: true,
        fill_role: "accent",
      },
    ],
  });
});

test("an explicit null fill remains a touched layer and restores the base fill", (): void => {
  const folded = fold([
    op({
      id: "clear-fill",
      kind: "fill",
      text: undefined,
      fillRole: null,
      label: "Headline color",
    }),
  ]);

  assert.deepEqual(toCanvasRevision(folded).layer_ops, [
    {
      layer_id: "layer-headline",
      dx: 0,
      dy: 0,
      scale: 1,
      visible: true,
      fill_role: null,
    },
  ]);
});

test("transformedBBox uses the same folded transform as hit-testing", (): void => {
  assert.deepEqual(
    transformedBBox(
      { x: 100, y: 200, w: 400, h: 100 },
      { dx: 20, dy: -10, scale: 0.5 },
    ),
    { x: 220, y: 215, w: 200, h: 50 },
  );
});

test("layerTransformAttr prepends the folded transform to the pristine transform", (): void => {
  assert.equal(
    layerTransformAttr(
      { dx: 12, dy: -6, scale: 1.25 },
      { x: 100, y: 200, w: 400, h: 100 },
      "rotate(2)",
    ),
    "translate(12,-6) translate(300,250) scale(1.25) translate(-300,-250) rotate(2)",
  );
  assert.equal(
    layerTransformAttr(
      { dx: 0, dy: 0, scale: 1 },
      { x: 100, y: 200, w: 400, h: 100 },
      "rotate(2)",
    ),
    "rotate(2)",
  );
});

test("dirtyLayerIds distinguishes an absent fold entry from an explicit reset", (): void => {
  const previous = fold([]);
  const next = fold([
    op({
      id: "clear-fill",
      kind: "fill",
      text: undefined,
      fillRole: null,
      label: "Headline color",
    }),
  ]);

  assert.deepEqual(dirtyLayerIds(previous, next), ["layer-headline"]);
  assert.deepEqual(dirtyLayerIds(next, next), []);
  assert.deepEqual(dirtyLayerIds(null, next), [
    "layer-background",
    "layer-panel",
    "layer-headline",
    "layer-subhead",
    "layer-cta",
    "layer-badge",
  ]);
});

test("applyState targets the child fill, wraps text, and resets dirty state to base", (): void => {
  const document = new FakeDocument();
  const host = new FakeElement(document);
  const group = new FakeElement(document);
  const text = new FakeElement(document);
  group.selectors.set("text", text);
  host.selectors.set('g[data-layer="layer-headline"]', group);
  group.setAttribute("transform", "rotate(2)");
  text.setAttribute("fill", "#111111");
  text.innerHTML = "<tspan>Original</tspan>";

  const base: EditorBaseState = {
    layers: {
      "layer-headline": {
        id: "layer-headline",
        bbox: { x: 10, y: 10, w: 50, h: 30 },
        baseTransform: "rotate(2)",
        baseStyle: null,
        baseTextHTML: "<tspan>Original</tspan>",
        baseFill: "#111111",
        initialText: "Original",
        textLayout: {
          x: "10",
          y: 20,
          lineHeight: 12,
          fontSize: 10,
          textAnchor: "start",
        },
      },
    },
    brandColors: [{ name: "primary", hex: "#abcdef", usage: null }],
    lastApplied: null,
    overflow: {},
  };
  const edited = fold([
    op({ id: "copy", text: "Alpha beta gamma" }),
    op({
      id: "color",
      kind: "fill",
      text: undefined,
      fillRole: "primary",
      label: "Headline color",
    }),
    op({
      id: "move",
      kind: "transform",
      text: undefined,
      transform: { dx: 5, dy: 6, scale: 1.2 },
      label: "Move Headline",
    }),
    op({
      id: "hide",
      kind: "visible",
      text: undefined,
      visible: false,
      label: "Hide Headline",
    }),
  ]);

  const editedResult = applyState(
    host as unknown as HTMLElement,
    base,
    edited,
  );

  assert.equal(text.getAttribute("fill"), "#abcdef");
  assert.equal(group.style.display, "none");
  assert.equal(
    group.getAttribute("transform"),
    "translate(5,6) translate(35,25) scale(1.2) translate(-35,-25) rotate(2)",
  );
  assert.deepEqual(
    text.children.map((child) => child.textContent),
    ["Alpha", "beta", "gamma"],
  );
  assert.equal(editedResult.overflow["layer-headline"], true);

  applyState(host as unknown as HTMLElement, base, fold([]));

  assert.equal(text.getAttribute("fill"), "#111111");
  assert.equal(group.style.display, "");
  assert.equal(group.getAttribute("transform"), "rotate(2)");
  assert.equal(text.innerHTML, "<tspan>Original</tspan>");
});

test("empty history folds to an empty payload", (): void => {
  assert.deepEqual(toCanvasRevision(fold(EMPTY_HISTORY.ops)), { layer_ops: [] });
});
