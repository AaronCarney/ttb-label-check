import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { useKeyboardShortcuts } from "./useKeyboardShortcuts";

const fireKey = (key: string, target: EventTarget = document) => {
  target.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
};

describe("useKeyboardShortcuts", () => {
  it("invokes onOverride when 'O' is pressed", () => {
    const onOverride = vi.fn();
    renderHook(() => useKeyboardShortcuts({ onOverride }));
    fireKey("o");
    expect(onOverride).toHaveBeenCalledTimes(1);
  });

  it("invokes onNext on 'J' and onPrev on 'K'", () => {
    const onNext = vi.fn();
    const onPrev = vi.fn();
    renderHook(() => useKeyboardShortcuts({ onNext, onPrev }));
    fireKey("j");
    fireKey("k");
    expect(onNext).toHaveBeenCalledTimes(1);
    expect(onPrev).toHaveBeenCalledTimes(1);
  });

  it("invokes onEscape on 'Escape'", () => {
    const onEscape = vi.fn();
    renderHook(() => useKeyboardShortcuts({ onEscape }));
    fireKey("Escape");
    expect(onEscape).toHaveBeenCalledTimes(1);
  });

  it("ignores keys when typing in <input> / <textarea> (preserves 'O' for typing)", () => {
    const onOverride = vi.fn();
    renderHook(() => useKeyboardShortcuts({ onOverride }));
    const input = document.createElement("input");
    document.body.appendChild(input);
    input.focus();
    fireKey("o", input);
    expect(onOverride).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it("ignores O/J/K when focus is inside a [role=dialog]", () => {
    const onOverride = vi.fn();
    const onNext = vi.fn();
    const onPrev = vi.fn();
    renderHook(() => useKeyboardShortcuts({ onOverride, onNext, onPrev }));
    const dialog = document.createElement("div");
    dialog.setAttribute("role", "dialog");
    const closeBtn = document.createElement("button");
    dialog.appendChild(closeBtn);
    document.body.appendChild(dialog);
    closeBtn.focus();
    fireKey("o", closeBtn);
    fireKey("j", closeBtn);
    fireKey("k", closeBtn);
    expect(onOverride).not.toHaveBeenCalled();
    expect(onNext).not.toHaveBeenCalled();
    expect(onPrev).not.toHaveBeenCalled();
    document.body.removeChild(dialog);
  });

  it("cleans up listeners on unmount (StrictMode survival)", () => {
    const onOverride = vi.fn();
    const { unmount } = renderHook(() => useKeyboardShortcuts({ onOverride }));
    unmount();
    fireKey("o");
    expect(onOverride).not.toHaveBeenCalled();
  });
});
