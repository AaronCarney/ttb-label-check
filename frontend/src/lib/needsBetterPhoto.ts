/** Whether an envelope is telling the reviewer the photo could not be read,
 *  and what to say to the applicant about it.
 *
 *  The image-quality gate fires before any field is extracted, so the envelope
 *  it produces carries no fields at all — `build_short_circuit_envelope` in
 *  app/services/envelope_builder.py sets `fields=()`. The reason code survives
 *  only as a synthetic entry in the audit trail, whose `rule_id` IS the code.
 *  Looking for the code inside `fields`, as this once did, therefore never
 *  found it on exactly the envelopes that have one, and the card never rendered.
 *  Both places are read here.
 *
 *  The match is against these three codes by name, not against the
 *  `WARNING.LEGIBILITY.` prefix. Two other codes share that prefix —
 *  NO_CONTRAST and CONTRAST_NOT_MEASURED, emitted by
 *  rules/common/health_warning.yaml about the label's own printing — and a
 *  prefix match would put "send a better photo" in front of a reviewer whose
 *  photo is fine. Drift guard: tests/test_needs_better_photo_codes.py fails if
 *  app/vision/quality.py emits a code this file does not carry.
 */
import type { DispositionEnvelope } from "../types/envelopes";

/** What the applicant is asked to do, per reason code the image-quality gate
 *  emits. Each names what is wrong with the photo and what to change, because
 *  "needs better photo" alone tells the applicant nothing they can act on. */
const APPLICANT_MESSAGE: Record<string, string> = {
  "WARNING.LEGIBILITY.LOW_RESOLUTION":
    "The photo is not sharp enough to read the label text. Please send a new one taken closer to the label, or at a higher resolution, so the smallest print is legible.",
  "WARNING.LEGIBILITY.GLARE":
    "Reflections wash out part of the label, so the text under them cannot be read. Please send a new photo taken without flash and out of direct light.",
  "WARNING.LEGIBILITY.MOTION_BLUR":
    "The photo is blurred by camera movement. Please rest the camera on something steady and send a new one.",
};

export interface NeedsBetterPhoto {
  reasonCode: string;
  applicantMessage: string;
}

function _isPhotoQualityCode(code: string): boolean {
  return Object.hasOwn(APPLICANT_MESSAGE, code);
}

/** The image-quality problem this envelope reports, or null if it reports none. */
export function needsBetterPhotoFrom(
  envelope: DispositionEnvelope,
): NeedsBetterPhoto | null {
  const fromFields = envelope.fields
    .flatMap((f) => f.rule_findings)
    .find((rf) => _isPhotoQualityCode(rf.reason_code))?.reason_code;
  const fromAudit = envelope.audit_trail?.per_rule_trace
    ?.find((e) => _isPhotoQualityCode(e.rule_id))?.rule_id;
  const reasonCode = fromFields ?? fromAudit;
  if (reasonCode === undefined) return null;
  return { reasonCode, applicantMessage: APPLICANT_MESSAGE[reasonCode]! };
}
