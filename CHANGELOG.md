# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-02-08

### Added

- 6-stage async pipeline: Observation, Compression, Hypothesis, Simulation, Decision, Feedback
- Pydantic v2 typed contracts at every stage boundary
- Plugin registry with decorator registration (`@register_collector`, `@register_processor`, etc.)
- Setuptools `entry_points` support for external plugins
- Built-in `toy` pipeline with synthetic data (fully offline, deterministic)
- Built-in `agro` pipeline for Brazilian agricultural market intelligence via agrobr
- CLI commands: `ugear run toy`, `ugear run agro`, `ugear plugins list`
- structlog observability across the full pipeline
- Rich terminal output with progress display
- Transition validation between pipeline stages
- fail-fast and continue-on-error pipeline modes
- 118 tests with full coverage across all stages
- Bilingual documentation (English and Portuguese)

[0.1.0]: https://github.com/bruno-portfolio/Universal-Gear/releases/tag/v0.1.0
