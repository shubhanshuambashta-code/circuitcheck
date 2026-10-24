# CircuitCheck 0.2.0

CircuitCheck now centres review around native engineering evidence and revision comparison. The public website and local application share the same responsive interface.

## Review a board

Upload the complete KiCad project. Select a finding to locate UUID-resolved tracks, component/pad envelopes or native reported positions. Select an affected object to isolate it, or highlight its stored net. Missing or ambiguous mappings stay explicitly unavailable. Schematic cross-probing requires unambiguous matching references/pads.

The inspector separates evidence, engineering review and optional explanation. Native checks establish the findings. AI explains selected evidence and cannot establish new violations or execute edits. Confirmed violations, review suggestions and potential concerns remain distinct. Native severity and native exclusions remain visible.

Coverage distinguishes checked with findings, checked with no findings, partial, failed and not checked. It shows missing dependencies, ignored rule categories and unevaluated ratings, thermal/current, simulation and physical assembly checks. There is no safety percentage. Provenance includes source/rules/profile hashes and engineering, adapter, normalization, geometry and explanation-engine identifiers.

## Compare revisions

Use **Upload revision B** in the existing project. Select revisions A and B to inspect resolved, remaining and new findings, changed components, physical routing and pad net assignments. Both board views use aligned coordinates for the selected change. Comments and accepted exceptions remain attached to stable findings; exceptions require re-review when evidence, engine, rules or profile changes.

Different rules, profile, engine, coverage or unstable source object IDs prevent a disappearance from becoming a verified fix. Physical geometry comparisons do not infer circuit intent or prove logical equivalence. Rewritten UUIDs appear as added/removed objects.

## Select fabrication constraints

The included `PCBWAY-STANDARD-BASELINE` is a dated, scoped snapshot linked to its published source. Other manufacturers can be represented by imported JSON, custom numeric limits, or native `.kicad_dru` code included in a complete project ZIP. Order references are metadata, not authenticated manufacturer lookups. Unknown codes without constraints remain not checked.

A second independent native DRC pass evaluates selected fabrication constraints in a disposable copy. Original project rules are checked independently, and originals are preserved. This is a constraint subset, not comprehensive fabrication approval.

## Apply a supported correction

For an eligible straight track-width finding: create a proposed copy, reopen it with KiCad, review the recheck and all new findings, explicitly approve the exact change, apply it as a revision, run fresh checks, and download the native project. Cancel returns without applying. Other findings provide a manual KiCad action and revision-upload path.

## Website and local application

The website offers a labelled interactive recording with real native results, object highlights, review history, revision comparisons, reports and native example downloads. It does not execute live checks or edits. The local application provides live uploads, native analysis, persistent reviews, fabrication profiles and approved changes.

Existing local data is retained. Older saved reports request a recheck before showing new evidence categories and detailed coverage. KiCad 10.0.7 on Windows was exercised; supplied Linux/macOS setup and live external AI calls were not newly verified.
