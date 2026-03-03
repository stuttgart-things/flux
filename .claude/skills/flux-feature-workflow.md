# Skill: flux-feature-workflow

End-to-end workflow for implementing features/fixes in this repo: branch, commit, push, PR.

## Trigger

When the user asks to work on a feature, fix, or issue — especially when referencing a GitHub issue number.

## Workflow

### 1. Create a feature branch

Branch naming convention based on commit type:
- `fix/<short-description>` for bug fixes
- `feat/<short-description>` for new features
- `chore/<short-description>` for maintenance
- `refactor/<short-description>` for refactoring

```bash
git checkout -b <type>/<short-description>
```

### 2. Make changes

Implement the fix/feature following repo conventions (see CLAUDE.md).

### 3. Commit with Angular convention

Use Angular commit convention (required for semantic-release):

```
<type>: <description>

<optional body>

Closes #<issue-number>
```

Types: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`

- `feat:` triggers a **minor** version bump
- `fix:` triggers a **patch** version bump
- `BREAKING CHANGE` in footer triggers a **major** bump

### 4. Push and create PR

```bash
git push -u origin <branch-name>
gh pr create --title "<type>: <description>" --body "..."
```

PR body format:
```markdown
## Summary
<1-3 bullet points>

Closes #<issue-number>

## Test plan
- [ ] Verify changes with `task get-variables` on affected components
- [ ] Run `pre-commit run --all-files`
```

### 5. After merge

The CI pipeline (once #44 is implemented) will:
- Run PR validation checks
- On merge to `main`, semantic-release creates a version tag automatically

## Rules

- **Always branch from `main`** — never commit directly to `main`
- **One logical change per PR** — multiple related issues can be combined if they touch the same files
- **Reference issue numbers** — use `Closes #N` in commit body to auto-close issues on merge
- **Run pre-commit before pushing** — `pre-commit run --all-files`
- **Keep commits atomic** — each commit should be a single logical change
