import {
  createElement,
  useId,
  type ChangeEvent,
  type FocusEvent,
  type InputHTMLAttributes,
  type JSX,
} from "react";

export interface HexColourState {
  value: string;
  normalized: string | null;
  invalid: boolean;
}

export interface HexColourControlProps {
  value: string;
  onChange: (value: string) => void;
  label: string;
  name?: string;
  className?: string;
  "data-api-field"?: string;
  "aria-invalid"?: InputHTMLAttributes<HTMLInputElement>["aria-invalid"];
}

/** Normalize a user-entered 3- or 6-digit colour to an API-safe six-digit hex. */
export function parseHexColour(value: string): string | null {
  const match = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(value.trim());
  if (match === null) return null;

  const digits = match[1].toUpperCase();
  const expanded =
    digits.length === 3
      ? digits
          .split("")
          .map((digit) => `${digit}${digit}`)
          .join("")
      : digits;
  return `#${expanded}`;
}

/** Preserve the operator's draft while exposing validation separately. */
export function hexColourState(value: string): HexColourState {
  const normalized = parseHexColour(value);
  return {
    value,
    normalized,
    invalid: normalized === null,
  };
}

/** In-app hex entry with a live swatch; invalid drafts stay visible until corrected. */
export function HexColourControl({
  value,
  onChange,
  label,
  name,
  className,
  "data-api-field": dataApiField,
  "aria-invalid": externalInvalid,
}: HexColourControlProps): JSX.Element {
  const errorId = useId();
  const state = hexColourState(value);
  const invalid = state.invalid || externalInvalid === true || externalInvalid === "true";
  const rootClass =
    `hex-colour-control${invalid ? " hex-colour-control--invalid" : ""}${
      className === undefined ? "" : ` ${className}`
    }`;

  function handleChange(event: ChangeEvent<HTMLInputElement>): void {
    onChange(event.target.value);
  }

  function handleBlur(event: FocusEvent<HTMLInputElement>): void {
    const normalized = parseHexColour(event.target.value);
    if (normalized !== null) onChange(normalized);
  }

  return createElement(
    "div",
    { className: rootClass },
    createElement("span", {
      className: "hex-colour-control__swatch",
      style: state.normalized === null ? undefined : { backgroundColor: state.normalized },
      "aria-hidden": true,
    }),
    createElement(
      "div",
      { className: "hex-colour-control__entry" },
      createElement("input", {
        className: "input hex-colour-control__input",
        type: "text",
        inputMode: "text",
        autoComplete: "off",
        spellCheck: false,
        value,
        name,
        pattern: "#?[0-9a-fA-F]{3}|#?[0-9a-fA-F]{6}",
        required: true,
        maxLength: 7,
        "aria-label": `${label} hex value`,
        "aria-invalid": invalid,
        "aria-describedby": invalid ? errorId : undefined,
        "data-api-field": dataApiField,
        onChange: handleChange,
        onBlur: handleBlur,
      }),
      invalid
        ? createElement(
            "span",
            { className: "hex-colour-control__error", id: errorId, role: "alert" },
            "Enter a 3- or 6-digit hex value.",
          )
        : null,
    ),
  );
}
