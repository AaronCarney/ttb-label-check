/** The shapes the API sends over the wire, hand-mirrored from
 *  app/schemas/wire/. Drift canary: tests/test_typescript_envelope_drift.py. */

export type Band = "high" | "medium" | "low";
export type Disposition = "pass" | "fail" | "needs_review";
export type RuleDisposition = "pass" | "fail" | "needs_review";

export interface ConfidenceBand {
  band: Band;
  numeric: number;
}

export interface FieldEvidenceWire {
  bbox: [number, number, number, number];
  crop_ref: string;
  extraction_confidence: number;
  // Which photograph the value was read from ("front", "back", …); empty when
  // the reading did not record one.
  face_tag: string;
}

export interface RuleFindingWire {
  rule_id: string;
  cfr_citation: string;
  disposition: RuleDisposition;
  reason_code: string;
  plain_language_explanation: string;
}

export type AISuggestionTask =
  | "brand_borderline"
  | "reasoning_enrichment"
  | "ocr_reconciliation";

export type AISuggestion =
  | { present: false; task: null; text: null; model_disposition: null }
  | {
      present: true;
      task: AISuggestionTask;
      text: string;
      model_disposition: "pass" | "needs_review" | null;
    };

export interface AISuggestionWire {
  present: boolean;
  task: AISuggestionTask | null;
  text: string | null;
  model_disposition: "pass" | "needs_review" | null;
}

export type FieldName =
  | "brand_name"
  | "class_type"
  | "alcohol_content"
  | "net_contents"
  | "warning"
  | "name_address"
  | "country_of_origin";

export interface FieldFindingWire {
  field_name: FieldName;
  extracted_value: string;
  expected_value: string;
  evidence: FieldEvidenceWire;
  rule_findings: RuleFindingWire[];
  ai_suggestion: AISuggestionWire;
  field_confidence: ConfidenceBand;
}

export interface PerRuleTraceEntry {
  rule_id: string;
  disposition: "pass" | "fail" | "needs_review" | "not_applicable";
  evidence_ref: string;
}

export interface OverrideEntry {
  field_name: string;
  original_disposition: "pass" | "fail" | "needs_review";
  applied_disposition: "pass" | "fail" | "needs_review";
  reason_code: string;
  justification_text: string | null;
  reviewer_id: string;
  timestamp: string;
}

export interface AuditRecord {
  evaluation_id: string;
  rule_set_version: string;
  model_version: string | null;
  prompt_version: string | null;
  input_hash: string;
  output_hash: string;
  started_at: string;
  completed_at: string;
  per_rule_trace: PerRuleTraceEntry[];
  overrides: OverrideEntry[];
}

export interface PerRuleDurationEntry {
  rule_id: string;
  duration_ms: number;
}

export interface Metrics {
  total_duration_ms: number;
  per_rule_durations_ms: PerRuleDurationEntry[];
  vision_duration_ms: number;
  /**
   * The answer came out of the result cache rather than being worked out
   * again. The durations beside it are then what serving this request cost,
   * not what the evaluation behind the verdict cost.
   */
  cache_hit: boolean;
}

export interface DispositionEnvelope {
  evaluation_id: string;
  label_ref: string;
  disposition: Disposition;
  disposition_confidence: ConfidenceBand;
  fields: FieldFindingWire[];
  audit_trail: AuditRecord;
  metrics: Metrics;
}

export interface BatchItemRef {
  label_ref: string;
  application_ref: string;
}

export interface BatchEnvelope {
  batch_id: string;
  agent_id: string;
  submitted_at: string;
  items: BatchItemRef[];
}
