CircuitCheck: known-answer test files

These are original synthetic KiCad projects, not validated functional circuits.
Upload each ZIP as-is using Upload project. Do not unzip it first.

track-width-before.zip: 1 error, 1 warning. A track is 0.15 mm wide; the configured
minimum is 0.25 mm. The same track also has an intentionally unconnected end.

track-width-corrected.zip: 0 errors, 1 warning. Width is 0.25 mm. The unconnected
end warning remains. A width change must not claim to fix that separate problem.

empty-board-outline.zip: 0 errors, 0 warnings in the performed PCB checks.
This contains an empty board outline, so a clean DRC result is not a claim that
a functioning circuit was checked. No schematic ERC is performed on these files.

To test repair: upload the before ZIP, select the width error, preview the
0.15 to 0.25 mm change, apply, and wait for recheck. Expect the width error to
resolve and the unconnected-end warning to remain.

Compare Download original engine report in the finding details with these
literal results. verified-results.json records the actual live test run.
Testing known examples cannot prove every future result is correct.
