/**
 * Centralized GSAP motion helpers.
 *
 * House rules (locked): restrained, fast, professional. No scroll-jacking,
 * no parallax. Every helper is a no-op (returns null) when the user has
 * `prefers-reduced-motion: reduce` set — content is then simply visible,
 * because all entrance animations are declared fromTo (never a CSS-hidden
 * initial state).
 */

import { gsap } from "gsap";

/** True when the user asks for reduced motion (or during SSR, where we never animate). */
export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return true;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export interface StaggerFadeUpOptions {
  /** Per-element duration in seconds. */
  duration?: number;
  /** Delay between successive elements in seconds. */
  stagger?: number;
  /** Initial downward offset in px. */
  y?: number;
  /** Delay before the first element starts, in seconds. */
  delay?: number;
}

/**
 * First-paint entrance: elements fade in and rise ~18px with a short stagger.
 * `clearProps` removes GSAP's inline transform on complete so CSS hover
 * transforms (card micro-scale) take over cleanly.
 */
export function staggerFadeUp(
  targets: Element[] | NodeListOf<Element>,
  options: StaggerFadeUpOptions = {},
): gsap.core.Tween | null {
  const elements = Array.from(targets);
  if (elements.length === 0 || prefersReducedMotion()) return null;

  const { duration = 0.4, stagger = 0.04, y = 18, delay = 0 } = options;
  return gsap.fromTo(
    elements,
    { autoAlpha: 0, y },
    {
      autoAlpha: 1,
      y: 0,
      duration,
      stagger,
      delay,
      ease: "power2.out",
      clearProps: "transform,opacity,visibility",
    },
  );
}

/** Slide-in for the right detail panel: short lateral travel + fade, power3.out. */
export function slideInPanel(
  target: Element | null,
  delay = 0.1,
): gsap.core.Tween | null {
  if (target === null || prefersReducedMotion()) return null;

  return gsap.fromTo(
    target,
    { autoAlpha: 0, x: 48 },
    {
      autoAlpha: 1,
      x: 0,
      duration: 0.5,
      delay,
      ease: "power3.out",
      clearProps: "transform,opacity,visibility",
    },
  );
}

/**
 * Smooth count-up for numeric badges (kanban column counts).
 * With reduced motion the final value is written immediately.
 */
export function animateCount(
  el: HTMLElement | null,
  to: number,
  duration = 0.7,
): gsap.core.Tween | null {
  if (el === null) return null;
  if (prefersReducedMotion()) {
    el.textContent = String(to);
    return null;
  }

  const state = { value: 0 };
  return gsap.to(state, {
    value: to,
    duration,
    ease: "power2.out",
    onUpdate: (): void => {
      el.textContent = String(Math.round(state.value));
    },
  });
}
