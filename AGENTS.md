# Repository Guidelines

## Project Structure & Module Organization
Core application code lives in `src/pi_inventory_system`, with managers for audio, display, motion sensing, and the main orchestration in `main.py`. Tests reside under `tests` mirroring module names, with shared fixtures in `tests/conftest.py`. Hardware driver shims are kept in `waveshare_drivers`, while SQL migrations live in `migrations`. Runtime assets (fonts, mocked images) sit in `assets`. Deployment automation and configuration defaults are defined in `deploy.sh` and `config.yaml`.

## Build, Test, and Development Commands
- `python3 -m venv .venv && source .venv/bin/activate`: create and enter an isolated environment.
- `pip install -e .` or `pip install -e ".[test]"`: install runtime or runtime+test dependencies.
- `python -m pi_inventory_system.main`: run the application in simulation or Raspberry Pi mode.
- `python -m pytest -v`: execute the full test suite.
- `python -m pytest --cov=pi_inventory_system --cov-report=html`: generate coverage HTML at `htmlcov/index.html`.

## Coding Style & Naming Conventions
Follow PEP 8 with 4-space indentation and keep lines under 100 characters to match existing files. Keep modules and functions in `snake_case`, classes in `PascalCase`, and constants uppercase. Add type hints and docstrings for public methods, mirroring current code patterns, and prefer dependency injection via constructors when extending managers.

## Testing Guidelines
Write tests beside the module they cover (`tests/test_<module>.py`). Mock GPIO, audio, and display dependencies to keep tests hardware-agnostic. Tag slow or hardware-required tests with `@pytest.mark.skip` or a custom marker and note overrides in the PR description.

## Commit & Pull Request Guidelines
Use concise, imperative commit messages (for example, “Add motion debounce logic”) similar to existing history. Rebase before opening a PR and squash fixups unless troubleshooting. In PRs, describe the change, list manual or automated test results, and include screenshots or log excerpts when the display or audio behavior changes. Link related issues or deployment notes.

## Hardware & Configuration Tips
Replicate Raspberry Pi settings by updating `config.yaml`; avoid hard-coded GPIO numbers. When adding drivers, keep mirrored copies inside `waveshare_drivers` and document required packages in `deploy.sh`. For local simulation, set environment flags in `config.yaml` rather than editing code paths.
