# Releasing

This repository uses [semantic-release](https://semantic-release.gitbook.io/) with the Angular commit convention to automate versioning and changelog generation.

## How It Works

1. Commits on `main` are analyzed by `@semantic-release/commit-analyzer`
2. Version is determined by commit type (`feat:` = minor, `fix:` = patch)
3. Release notes are generated from commit messages
4. `CHANGELOG.md` is updated
5. A GitHub release is created
6. A Git tag is pushed in `v${version}` format

## Release Process

Using go-task:

```bash
task release
```

This runs:

1. Pre-commit checks
2. Creates/updates a PR
3. `npx semantic-release --dry-run` to preview the version
4. `npx semantic-release --debug --no-ci` to publish

## Manual Release

```bash
npx semantic-release --dry-run    # Preview
npx semantic-release --debug --no-ci  # Publish
```

## Commit Message Format

```
type: subject

body (optional)

footer (optional)
```

| Type | Version Bump | Example |
|---|---|---|
| `feat` | Minor (0.x.0) | `feat: add prometheus component` |
| `fix` | Patch (0.0.x) | `fix: correct metallb IP range variable` |
| `chore` | None | `chore: update renovate config` |
| `docs` | None | `docs: add vault README` |
| `refactor` | None | `refactor: simplify cert-manager kustomization` |

For a major version bump, add `BREAKING CHANGE:` in the commit footer.

## Configuration

Defined in `.releaserc`:

- **Branch**: `main`
- **Tag format**: `v${version}`
- **Plugins**: commit-analyzer, release-notes-generator, changelog, github, git

## Pre-commit Hooks

Run before pushing:

```bash
pre-commit run --all-files
```

Active checks: trailing whitespace, end-of-file-fixer, large files, merge conflicts, symlinks, private key detection, shellcheck, hadolint, GitHub Actions schema validation, and high-entropy secret detection.

## Dependency Management

[Renovate](https://docs.renovatebot.com/) is configured (`renovate.json`) with Flux-specific YAML file matching to automatically propose version updates for Helm charts and OCI artifacts.
