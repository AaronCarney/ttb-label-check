import { describe, it, expect } from "vitest";
import { needsBetterPhotoFrom } from "./needsBetterPhoto";
import type { DispositionEnvelope } from "../types/envelopes";

/** An envelope shaped like the one the image-quality gate short-circuits into:
 *  no fields, the reason code carried only by a synthetic audit-trail entry.
 *  Mirrors build_short_circuit_envelope in app/services/envelope_builder.py. */
function shortCircuitEnvelope(reasonCode: string): DispositionEnvelope {
  return {
    evaluation_id: "ev-1",
    label_ref: "lbl.jpg",
    disposition: "needs_review",
    disposition_confidence: { band: "low", numeric: 0.0 },
    fields: [],
    audit_trail: {
      evaluation_id: "ev-1",
      rule_set_version: "0.1.0",
      model_version: null,
      prompt_version: null,
      input_hash: "x",
      output_hash: "y",
      started_at: "2026-09-16T00:00:00Z",
      completed_at: "2026-09-16T00:00:01Z",
      per_rule_trace: [
        {
          rule_id: reasonCode,
          disposition: "needs_review",
          evidence_ref: `engine_failure/${reasonCode}`,
        },
      ],
      overrides: [],
    },
    metrics: { total_duration_ms: 12, per_rule_durations_ms: [], vision_duration_ms: 12, cache_hit: false },
  };
}

describe("needsBetterPhotoFrom", () => {
  it.each([
    "WARNING.LEGIBILITY.LOW_RESOLUTION",
    "WARNING.LEGIBILITY.GLARE",
    "WARNING.LEGIBILITY.MOTION_BLUR",
  ])("finds %s on a fields-less short-circuit envelope", (code) => {
    const found = needsBetterPhotoFrom(shortCircuitEnvelope(code));
    expect(found?.reasonCode).toBe(code);
    expect(found?.applicantMessage.length).toBeGreaterThan(20);
  });

  it("gives each code its own message, so the reviewer is not told the wrong thing", () => {
    const messages = [
      "WARNING.LEGIBILITY.LOW_RESOLUTION",
      "WARNING.LEGIBILITY.GLARE",
      "WARNING.LEGIBILITY.MOTION_BLUR",
    ].map((c) => needsBetterPhotoFrom(shortCircuitEnvelope(c))!.applicantMessage);
    expect(new Set(messages).size).toBe(3);
  });

  it("stays silent on an envelope with no quality problem", () => {
    const envelope = shortCircuitEnvelope("WARNING.LEGIBILITY.GLARE");
    envelope.audit_trail.per_rule_trace = [];
    expect(needsBetterPhotoFrom(envelope)).toBeNull();
  });

  it("does not fire on the contrast codes, which are about the label, not the photo", () => {
    for (const code of [
      "WARNING.LEGIBILITY.NO_CONTRAST",
      "WARNING.LEGIBILITY.CONTRAST_NOT_MEASURED",
    ]) {
      expect(needsBetterPhotoFrom(shortCircuitEnvelope(code))).toBeNull();
    }
  });

  it("also finds a quality code carried on a field, not only in the audit trail", () => {
    const envelope = shortCircuitEnvelope("WARNING.LEGIBILITY.GLARE");
    envelope.audit_trail.per_rule_trace = [];
    envelope.fields = [
      {
        field_name: "warning",
        extracted_value: "",
        expected_value: "",
        evidence: { bbox: [0, 0, 0, 0], crop_ref: "", extraction_confidence: 0.1, face_tag: "" },
        rule_findings: [
          {
            rule_id: "r",
            cfr_citation: "27 CFR §16.21",
            disposition: "needs_review",
            reason_code: "WARNING.LEGIBILITY.GLARE",
            plain_language_explanation: "",
            matched_value: "",
          },
        ],
        ai_suggestion: { present: false, task: null, text: null, model_disposition: null },
        field_confidence: { band: "low", numeric: 0.1 },
      },
    ];
    expect(needsBetterPhotoFrom(envelope)?.reasonCode).toBe("WARNING.LEGIBILITY.GLARE");
  });
});
