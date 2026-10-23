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
