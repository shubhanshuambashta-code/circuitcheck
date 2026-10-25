# Executed verification

Verified on **23 October 2026**, Windows x64. The final application build was tested using the delivered `scripts/start.py` supervisor with separate API and worker processes, serving production assets at loopback port 8001.

| Check | Executed result |
|---|---|
| `pytest -q` with native KiCad 10.0.7 configured | **41 passed**, zero skipped; 101.84 seconds |
| `npm run build` | TypeScript and Vite production build passed |
| `playwright test` against the production server | **7 passed**; 1.3 minutes |
| Native engine version | KiCad **10.0.7** executed |
| Official Windows binary | Valid Authenticode signature, KICAD SERVICES CORPORATION |
| Windows native process limits | Job Object assignment and limited real CLI execution passed |
| Rendered review | Desktop 1440×900 / 1440×1000 and narrow 390×844 layouts inspected; widths 320–1440 checked; screenshots included |

Backend tests exercise safe/unsafe archive paths, links, nesting and expansion limits, filename collisions, malformed/unsupported content, missing subsheets and libraries, external library rejection, root ambiguity, source preservation, stale jobs, global concurrency, cross-project file access, local request boundaries, SVG sanitization, AI schema/reference/numerical validation and fallback, plus native integration.

Native integration executes clean PCB DRC, deliberate track-width DRC, deliberate disconnected-pin ERC, clean schematic ERC, netlist export, multi-sheet hierarchical exports, schematic/PCB parity, custom-rule minimums, layer exports, and an independent known-coordinate-to-SVG geometry check. Repair tests reject apply before validation, change one width atom, reopen the candidate through KiCad, rerun checks, confirm the targeted finding is absent, inspect new findings, apply, force a fresh recheck, compare, download original/revised files and undo. Project settings and unrelated source bytes are preserved.

Browser tests exercise the empty state, unsupported upload, keyboard upload/close, actual upload/check/evidence, viewer zoom and fit, filter-empty results, no-key explanations, repair preview/apply/recheck, comparison, project download, undo, clean and partial coverage, actual engine failure, multiple findings, layer visibility, synchronized selection, mobile panel switching and long filenames without horizontal overflow.

The `/test-files/` download page was added afterward with three small native ZIPs. Each packaged ZIP was uploaded through the live API and checked by the running separate worker using KiCad 10.0.7: before = 1 error / 1 warning, corrected = 0 errors / 1 warning, empty outline = 0 errors / 0 warnings. ZIP downloads and native file contents were verified over HTTP. `public/test-files/verified-results.json` records that run; originals of the three native reports are supplied alongside the downloads. No generative AI was configured during this check.

The first browser pass exposed a dev-server reload during testing and an unsuitable failure fixture: KiCad accepted a minimal board and reported an invalid-outline violation instead of failing to load it. Those were corrected by ignoring generated test directories, testing the production build, and using unsupported native syntax for the execution-failure case. The earlier six-test run passed; the interface update adds a seventh workflow test.

One third-party Starlette/AnyIO deprecation warning was emitted by pytest; it did not affect execution. CLI logs contain host-sandbox warnings about the optional KiCad HKCU preference key. The actual engine reports and exports completed despite those warnings.

## Interface update verification

Applied ui-ux-pro-max guidance for unobscured focus, accessible controls, readable technical text, consistent semantic colors and responsive layout. Added a real detected-files dialog, a persistent repair footer, test-project navigation, skip navigation, pressed/expanded states and Escape focus restoration for layers. The native analysis and repair implementation is unchanged.

The new browser test checks the repair action stays entirely in the viewport and does not move when evidence scrolls, actual uploaded filenames appear in the dialog, the dialog centers, coverage navigation works, layer controls close and restore keyboard focus, and the mobile action remains visible. Computed-style sampling of visible review-workspace text found no foreground/background contrast candidates below 4.5:1 after adjustment; this focused check is not a full accessibility audit. Updated renders are `screenshots/interface-desktop.png`, `screenshots/interface-mobile.png` and `screenshots/project-files.png`. Browser QA used an isolated data directory; existing user projects were preserved. The 41 backend tests above were run before this interface-only update.

## Implemented and tested

- React/Tailwind engineering workspace, safe upload, real queued worker, SQLite persistence and project-scoped storage.
- KiCad PCB/schematic read, project settings, hierarchical sheets, custom rules, missing-library detection, DRC/ERC/parity, SVG and XML netlist exports.
- Literal finding evidence, severity/exclusions handling, deterministic explanations, structured AI-output validation and provider-failure fallback.
- Selected straight-track width repair, immutable candidate, guarded apply, recheck, comparison, undo, native downloads and project cleanup.
- Desktop and narrow-screen workflow, focus/keyboard controls, explicit empty/loading/failure/partial/clean/filter states and exported screenshots.

## Supplied but not executed here

- Live AI-provider network call: no AI key was configured. There is a real configurable HTTP adapter, but no live model integration pass is claimed.
- Docker image build, Docker Compose, Linux process limits, Linux/macOS setup scripts: Docker was absent and this was a Windows host. The container recipe's exact KiCad package availability must be verified on the target host.
- A clean-machine invocation of the complete setup script. Its equivalent dependency installation and production build commands ran successfully; the running app reused the task-local installed environment.

## Incomplete or unsupported

- Public multi-user authentication, ownership checks and deployment. Keep this build on localhost.
- Non-KiCad adapters and format conversion, mechanical/thermal/current-capacity/simulation analyses, 3D views, schematic editing, routing, component replacement or deletion.
- Standalone library authoring, arbitrary CAD edits and automatic repair of any rule except the tested straight-track minimum-width case.
- Automatic preview-retention cleanup; previews remain in project history until deletion.
- Arbitrary external libraries or external hierarchy references. Bundle dependencies inside the project instead.
- All historical/future KiCad versions and every possible native project dependency. Missing custom rules cannot always be inferred from a file that was never uploaded; this uncertainty is stated in coverage.

Free-form AI prose is not mathematically verified; it remains labelled for review against engine evidence. DRC/ERC results do not guarantee functional or physical correctness.

## Upload connection recovery

The local API was not listening on port 8000 when the reported upload failure was investigated. Restarting the API and worker restored connectivity; `/api/health` reported `status: ok` and KiCad available. The frontend now replaces a rejected fetch with actionable local-server instructions and preserves the upload dialog for retry. `Start CircuitCheck.cmd` provides a Windows double-click entry point to the existing supervisor; keep its server window open.

Executed for this fix: `npm run build` passed; `playwright test e2e/connection.spec.ts` passed (1 test, 17.1 seconds). The browser test aborts the upload request, verifies the recovery message, retries the same native files against the running API, waits for actual KiCad findings, and deletes only its own completed test project. The earlier seven-test result above remains the full interface regression run; that entire suite was not rerun for this narrow error-message change.


## Board-only workspace

Removed the Schematic tab, sheet selector and automatic switching to schematic previews. Board layout is the sole design view. Findings from another file do not produce a location marker or locate action on the displayed board. TypeScript/Vite production build passed and the live workspace was visually checked with the Schematic tab absent. This small UI removal did not require another native-engine regression run. Render: `screenshots/board-only-workspace.png`.

## GitHub Pages deployment fix

Reproduced the blank published page: Pages served the source index from main directly, which referenced an unbuilt TypeScript entry point at the domain root. Added a separate `build:pages` mode with `/circuitcheck/` base, `dist-pages/` output and a pinned GitHub Actions build/deploy workflow. The local production build continues to use `/` and `dist/`. Static Pages displays a product preview, local startup instructions and test downloads; it does not claim to run the Python/KiCad backend or accept designs.

Executed: `npm run build:pages` and `npm run build` passed. Two dedicated Playwright checks passed at 1440px and 390px, covering rendering, image decoding, startup navigation, no horizontal overflow, all three native ZIP downloads, return navigation and zero API requests. New browser tests are in `pages-tests/`; run `npx playwright test --config=playwright.pages.config.ts` after building Pages. Native analysis and repair code did not change; the earlier engine-test results are not a new run.

## Version 0.2 engineering review update — 24 October 2026

Executed with native KiCad 10.0.7 on Windows:

- Full backend suite: **56 passed**, no skipped tests, in 65.75 seconds. One third-party Starlette/AnyIO deprecation warning remains.
- Local and Pages production builds: TypeScript and Vite passed for both modes.
- Local browser suite: **6 passed**, covering connection recovery, responsive board/object highlighting, evidence/review/explanation, guarded repair and recheck, linked revision upload, coverage states and fabrication profiles.
- Pages browser check: **1 passed**, including widths 360, 390, 768, 1024 and 1440 pixels, recorded-evidence navigation, downloads, zero browser errors and explicit local-app requirements.
- After the final compact workspace and comparison alignment changes, the interface and complete native repair/review workflows passed again. The Pages check also passed again and verified identical SVG view boxes for both sides of a selected changed component.
- Final manufacturer-profile browser rerun: **1 passed** in 23.0 seconds. An earlier rerun could not connect because its temporary QA server had stopped; restarting the test supervisor resolved this environment failure.
- Final linked-upload backend check: **1 passed**, confirming original-file preservation and review history after the root-selection improvement.

New native regression checks cover exact UUID geometry, physical object/net changes, coverage distinctions, rule changes preventing a false resolved claim, exception-scope validity, unknown order codes, numeric profile validation and independent fabrication-rule evaluation. In particular, a supplier minimum below the original project's global minimum is checked independently, so the stricter project rule cannot hide a supplier violation. Original project rules and uploads remain unchanged.

The public recorded Fieldnode example was regenerated using actual native checks on two synthetic revisions. It includes 4 resolved, 32 remaining and 6 new findings, one changed component and four changed routing/pad-net objects, with both a valid and a stale accepted exception. Native identity and comparable rule/engine/profile scope are recorded. This example is not a functional or manufacturing approval. Website uploads, live edits and remote native execution are not simulated.

Desktop, mobile, coverage, repair and comparison renders are included under `screenshots/review-v2-*`. Browser QA used an isolated project directory. Existing local user projects were preserved. No live external AI-provider call, clean-machine installation, Linux/container run or exhaustive CAD-format compatibility claim is made by this release.


## Version 0.2.1 schematic restoration — 24 October 2026

Restored native schematic viewing in both local and recorded website modes, including native sheet numbers/UUID hierarchy, sheet selection, source-wire/symbol anchors, exact engine-reported pin coordinates and electrical finding navigation. Native per-page export prevents a child-sheet finding from being placed on a root sheet. Board cross-probing remains available for matching references/pads. Revision comparison can display both schematic revisions and locate a resolved ERC pin. General schematic editing and logical net tracing remain in KiCad.

Executed: full backend suite **56 passed** in 66.61 seconds with one third-party deprecation warning, including assertions for the exact native pin at (75.08, 70.0) mm and distinct root/child file and UUID paths. After adding native object evidence to accepted-exception scope and exposing ignored ERC checks, all **15 review tests passed** again in 20.30 seconds. The final local browser suite **7 passed** in 1.4 minutes, including native schematic upload, source pin highlighting, zoom, board switching and mobile layout. The expanded Pages browser check **1 passed** in 6.8 seconds, including native A/B schematic views and the resolved R1 pin at (50.8, 116.84) mm. Both production builds passed.

The website fixture now contains an original matching schematic and bundled symbol library. Revision A intentionally leaves R1 pin 1 unconnected; revision B adds the actual GND label and native ERC no longer reports that pin violation. Library footprint-reference advisories are classified as review suggestions. Disabled native ERC checks are explicitly listed as partial coverage. Report adapter/version is circuitcheck-0.2.1, evidence normalizer is evidence-2.1 and schematic geometry is schematic-index-1.0. The symbol/pin scope and source hashes remain reproducible.


## Local startup and white-page diagnosis — 25 October 2026

Reproduced the extracted-copy startup failure: Windows PowerShell threw `Run scripts\setup.ps1 first.` because the original relative Python path did not exist after extraction. Added private runtime bindings, a first-time Setup launcher and safe reuse of an existing matching local server. Bundled production builds skip unnecessary Node dependency installation during setup. Configured this extracted installation to retain all existing projects and reuse the already installed Python/KiCad runtime. The configured launcher and a second startup both succeeded, and health reported KiCad available.

Reproduced the published blank page in Chrome: the repository URL returned HTTP 200 with an empty body view while `/src/main.tsx` and the unresolved favicon placeholder returned HTTP 404. The source HTML was being served directly. Added a committed production `site/` build, a source-entry redirect that is removed by Vite in normal builds, and a `.nojekyll` marker. Both normal Actions output and branch-served source use compiled JavaScript and static native evidence. Browser regression checks cover both publishing modes, including schematic views and revision comparison.
