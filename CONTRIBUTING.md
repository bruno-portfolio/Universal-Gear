# Contributing

*[Leia em Portugues](CONTRIBUTING.pt-BR.md)*

1. Fork → branch (`feat/...`, `fix/...`) → PR.
2. All code must pass `ruff check`, `mypy --strict`, and `pytest` before the PR.
3. Commits follow Conventional Commits: `feat(scope): msg`, `fix(scope): msg`.
4. The toy example must remain 100% offline and deterministic — PRs that break this will be rejected.
5. New domain integrations go as plugins in `plugins/`, never modifying `core/`.
