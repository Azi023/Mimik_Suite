import type { JSX, ReactNode } from "react";

interface OnboardingFieldProps {
  label: string;
  hint?: string;
  required?: boolean;
  children: ReactNode;
}

/** Shared onboarding-style field used by create and edit surfaces. */
export function OnboardingField({
  label,
  hint,
  required,
  children,
}: OnboardingFieldProps): JSX.Element {
  return (
    <label className="wiz-field">
      <span className="wiz-field__label">
        {label}
        {required === true && <span className="wiz-field__req"> *</span>}
      </span>
      {hint !== undefined && <span className="wiz-field__hint">{hint}</span>}
      {children}
    </label>
  );
}

/** Shared section heading used by create and edit surfaces. */
export function OnboardingSectionTitle({ children }: { children: ReactNode }): JSX.Element {
  return <h2 className="wiz-section-title">{children}</h2>;
}
