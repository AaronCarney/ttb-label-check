# Manual accessibility smoke test — NVDA and VoiceOver

Run before each release, and before merging a change to the interface.

## NVDA (Windows, Firefox)

1. Load `https://<deployed-url>/` with a canned envelope (single-label demo).
2. Verify NVDA announces the page title, then the H1 ("TTB Label Verification").
3. Tab through the focusable elements; the first should be "Skip to main content".
4. Activate the skip link; focus lands on `#main`.
5. Tab to a citation chip; activate it (Enter); the evidence dialog opens with focus on the close button.
6. Press `O`; the override drawer opens; the reason-code picker is announced.
7. Type `W`; NVDA announces the picker filter narrowing to the WARNING.* codes; the first highlighted option is `WARNING.STYLE.HEADING_NOT_BOLD_CAPS`.
8. Press `Enter`; NVDA announces the LiveRegion message "Override saved: WARNING.STYLE.HEADING_NOT_BOLD_CAPS".
9. Press `Esc`; the drawer closes; focus returns to the trigger.
10. With `prefers-reduced-motion: reduce` set in OS settings, verify no fade/slide animations on dialogs or toasts.

## VoiceOver (macOS, Safari)

1. Load the page; VO+A reads the page from the top.
2. VO+→ steps through the navigation; the rotor (VO+U) shows landmarks (banner, main, contentinfo).
3. The disposition pill is announced as "Disposition: Pass / Fail / Needs review" (not just the icon).
4. Open the override drawer via `O`; VO announces the modal.
5. Tab order inside the drawer: close → reason-code combobox → justification textarea → cancel → submit.
6. After submit, VO reads the LiveRegion message.

## Failure handling

Any item failing a step is a **release blocker** unless an exception is filed under
`docs/exceptions/` and reviewed by the project owner. The axe-core CI gate should
catch most issues; this checklist catches what axe cannot (announcement quality,
VoiceOver-specific behaviors).
