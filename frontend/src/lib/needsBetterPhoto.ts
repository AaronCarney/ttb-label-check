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
 *  The match is against these codes by name, not against the
 *  `WARNING.LEGIBILITY.` prefix. Two other codes share that prefix —
 *  NO_CONTRAST and CONTRAST_NOT_MEASURED, emitted by
 *  rules/common/health_warning.yaml about the label's own printing — and a
 *  prefix match would put "send a better photo" in front of a reviewer whose
 *  photo is fine. Drift guard: tests/test_needs_better_photo_codes.py fails if
 *  app/vision/quality.py emits a code this file does not carry.
 */
import type { DispositionEnvelope } from "../types/envelopes";

/** What the applicant is asked to do, per reason code that stops a label for
 *  its photo. Each names what is wrong with the photo and what to change,
 *  because "needs better photo" alone tells the applicant nothing they can act
 *  on, and names the photo, where the result says which, because a label sent
 *  as two photos has two to choose from. `photo` is "the back photo" or, where
 *  no face is named, "the photo". */
const APPLICANT_MESSAGE: Record<string, (photo: string) => string> = {
  "WARNING.LEGIBILITY.LOW_RESOLUTION": (photo) =>
    `${_capitalised(photo)} is not sharp enough to read the label text. Please send a new one taken closer to the label, or at a higher resolution, so the smallest print is legible.`,
  "WARNING.LEGIBILITY.GLARE": (photo) =>
    `Reflections wash out part of ${photo}, so the text under them cannot be read. Please send a new photo taken without flash and out of direct light.`,
  "WARNING.LEGIBILITY.MOTION_BLUR": (photo) =>
    `${_capitalised(photo)} is blurred by camera movement. Please rest the camera on something steady and send a new one.`,
  "LEGIBILITY.PHOTO.NO_TEXT": (photo) =>
    `No text could be found on ${photo}. Please send a new one taken straight on, in even light, with the whole label in frame.`,
};

export interface NeedsBetterPhoto {
  reasonCode: string;
  applicantMessage: string;
}

function _capitalised(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function _isPhotoQualityCode(code: string): boolean {
  return Object.hasOwn(APPLICANT_MESSAGE, code);
}

/** The face an audit entry's `evidence_ref` names after the code, as
 *  `build_short_circuit_envelope` writes it: `engine_failure/<code>/<face>`. */
function _faceFromRef(ref: string, code: string): string | null {
  const prefix = `engine_failure/${code}/`;
  return ref.startsWith(prefix) && ref.length > prefix.length ? ref.slice(prefix.length) : null;
}

/** The image-quality problem this envelope reports, or null if it reports none. */
export function needsBetterPhotoFrom(
  envelope: DispositionEnvelope,
): NeedsBetterPhoto | null {
  let reasonCode: string | undefined;
  let face: string | null = null;
  for (const f of envelope.fields) {
    const finding = f.rule_findings.find((rf) => _isPhotoQualityCode(rf.reason_code));
    if (finding !== undefined) {
      reasonCode = finding.reason_code;
      face = f.evidence.face_tag || null;
      break;
    }
  }
  if (reasonCode === undefined) {
    const entry = envelope.audit_trail?.per_rule_trace?.find((e) => _isPhotoQualityCode(e.rule_id));
    if (entry !== undefined) {
      reasonCode = entry.rule_id;
      face = _faceFromRef(entry.evidence_ref, entry.rule_id);
    }
  }
  if (reasonCode === undefined) return null;
  const photo = face === null ? "the photo" : `the ${face} photo`;
  return { reasonCode, applicantMessage: APPLICANT_MESSAGE[reasonCode]!(photo) };
}
