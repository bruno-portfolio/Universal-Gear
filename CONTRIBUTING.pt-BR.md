# Contribuindo

*[Read in English](CONTRIBUTING.md)*

1. Fork → branch (`feat/...`, `fix/...`) → PR.
2. Todo código passa `ruff check`, `mypy --strict` e `pytest` antes do PR.
3. Commits seguem Conventional Commits: `feat(scope): msg`, `fix(scope): msg`.
4. Toy example deve continuar 100% offline e determinístico — PRs que quebram isso serão rejeitados.
5. Novas integrações de domínio entram como plugin em `plugins/`, nunca alterando `core/`.
