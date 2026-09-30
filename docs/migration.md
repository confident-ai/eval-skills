# Runnable toolkit migration

The ten public `eval-` skill names and Descent remain unchanged. The suite now includes reusable local infrastructure rather than asking an agent to generate every runner and review server from scratch.

New work defaults to `.eval/<flow>/`, with `workflow.json` holding decisions and completed milestones. Use `setup_workspace.py --root` to retain an existing location. The installer never overwrites customized scripts. Native review and run records are implementation formats; export with `export_bundle.py` for portable contract v1. Existing v1 bundles remain valid.

Split names are `development`, `validation`, and `test`. When importing older `train`/`dev` artifacts, map names to development/validation without moving case IDs or redrawing splits. The legacy source workspace `evals/` can remain in place by passing it as `--root`. Rebaseline if the actual grader, runner semantics, or application changes.

The review server now requires a real reviewer identifier and the record's current revision on writes. Old notes remain readable with revision zero; new saves add stable IDs and provenance. A confirmed mode does not confirm its assignments. Review JSON exports retain prior taxonomy revisions.

Managed operations are documented with verification status. SDK smoke tests and offline fixtures do not establish that a user's hosted project is configured or that a paid judge has been validated.
