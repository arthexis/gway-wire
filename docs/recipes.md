# GWAY RX recipes in gway-wire

`recipes/` contains checked-in GWAY `.rx` programs that express trusted gateway integration policy. They are ordinary GWAY recipes: one GWAY statement per logical line, no shell evaluation, and normal context/chaining/reload semantics.

## Live gateway recipe

The default live recipe is `recipes/ubuntu22-live.rx`. Run it on a trusted gateway with explicit invocation parameters:

```bash
sudo gway recipe recipes/ubuntu22-live.rx \
  --fqdn register.arthexis.com \
  --cert-email tecnologia@gelectriic.com
```

The recipe upgrades GWAY, executes `reload` so execution resumes under the newly installed runtime, refreshes Wire and Web through GWAY, exercises the managed Web surface, and deploys the public enrollment endpoint. Deployment is the final recipe result so the CI workflow can explicitly assert its `success` mapping while the Wire Python API retains its existing return contract.

## Self-hosted CI execution

`.github/workflows/ubuntu22-live.yml` is intentionally restricted to trusted executions:

- it runs only for `main` pushes or manual `workflow_dispatch`;
- the job is additionally restricted to the repository owner;
- it targets the dedicated `[self-hosted, Linux, X64]` gateway runner;
- it verifies Ubuntu 22.04 and passwordless `sudo` before executing privileged GWAY work;
- only one live run is allowed at a time.

The workflow checks out this repository, validates the selected recipe path, bootstraps GWAY for compatibility with the current recipe interface, and then invokes the selected `.rx` file directly with `gway recipe`.

Manual runs expose a `recipe` input. The value is not a command string: `.github/scripts/validate-recipe-path.sh` requires it to resolve to an existing Git-tracked `.rx` file under `recipes/`. Traversal, files outside that directory, untracked files, and non-`.rx` files are rejected.

The default is:

```text
recipes/ubuntu22-live.rx
```

This makes the runner contract simple: **GitHub selects a trusted checked-in recipe; GWAY executes it.**

## What stays outside `.rx`

Recipes contain GWAY operations. Runner and external-environment assertions remain in GitHub Actions when there is no GWAY operation for them. In particular, the live workflow still owns:

- host OS and sudo validation;
- trusted recipe-path validation;
- the one-time compatibility bootstrap for gateways that may have a pre-recipe-parameter GWAY;
- the final raw HTTPS health request.

Do not add shell escapes, loops, branches, or arbitrary command execution to the recipe language to absorb these checks. If a reusable operation belongs in GWAY, implement it as a GWAY command and then call that command from the recipe.
