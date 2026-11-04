# Dependency and License Review

## Runtime

The package has no third-party runtime dependencies. It uses the Python standard
library. The project itself is licensed under MIT; the license is included in the
wheel metadata and source distribution.

## Development and build tools

| Tool | Declared role | License reviewed |
|---|---|---|
| build | Isolated wheel/source builds | MIT |
| Hatchling | PEP 517 build backend | MIT |
| mypy | Static type checking | MIT |
| pytest | Test execution | MIT |
| Ruff | Linting and code-quality checks | MIT |

No tool is bundled as a runtime dependency. Versions are bounded in
`pyproject.toml` where they are installed directly; Hatchling is resolved in the
isolated build environment.

This is a package-level license review, not legal advice. Repeat it if dependencies
or distribution contents change.
