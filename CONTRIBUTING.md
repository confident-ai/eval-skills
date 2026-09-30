# Contributing

Keep the suite focused on decisions that change evaluation quality. Add instructions only when they prevent a demonstrated failure or enable a concrete workflow. Put conditional detail in a reference rather than making every session read it.

## Develop

Repository validation uses Python 3.10+ and the standard library. Node.js is required only to regenerate the banner wrapper. No model keys, paid runs, or platform account are needed.

```bash
python3 scripts/validate_repo.py
python3 -m unittest discover -s tests -v
python3 examples/offline_eval.py --output /tmp/eval-skills-example
python3 skills/eval-run/scripts/artifacts.py validate /tmp/eval-skills-example
```

Before publishing a change to a workflow, exercise the affected scenarios in `tests/scenarios.md`. Record actual observed behavior, not a claim that a file containing the right headings proves the agent follows it. Use isolated fixtures; do not upload real data or run paid calls merely to validate a contribution.

## Structure

`skills/` contains installable packages. Supporting references stay inside each package. Shared workflow and artifact references are generated into those packages by `scripts/sync_references.py`; edit the sources under `docs/` and run the sync script. CI rejects drift. The portable helper's canonical copy is under `skills/eval-run/scripts/`; repo tests import that same file.

`examples/` contains synthetic demonstration evidence, never customer exports. `tests/` verifies portable records, split isolation, resume behavior, and documented workflow scenarios. `assets/` contains final branding only.

## Editorial requirements

- Begin with user stage and evidence; do not lead with framework installation.
- Preserve existing tools and explicit platform preferences.
- Use confident-trace for managed tracing; keep DeepEval confined to local grading.
- Separate human-confirmed labels from agent suggestions, unknown values from zeros, and application failures from execution errors.
- Link current official integration sources and check actual installed versions before claiming API support.
- Keep instructions independent of a particular assistant's tool names. Offer a sequential fallback for optional delegation and a text fallback for question widgets.
- Do not promise unlimited free usage, automatic annotation accuracy, or lossless export of every hosted feature.

Changes to public interchange fields must increment their schema version or remain backwards compatible. Add behavioral tests for changes to helpers. Existing source formats remain valid through adapters.

## Artwork

Generate original romantic-pointillist artwork using the reference family described in `assets/README.md`. Do not replace raster art with a procedural approximation. Run `node scripts/create-banner.mjs` after updating the PNG, inspect the README banner, and verify reduced-motion behavior.

Contributions are licensed under Apache-2.0. Credit external material and preserve any required notices. Do not copy proprietary instructions or introduce customer content, credentials, or unlicensed assets.
