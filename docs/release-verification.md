# Release Candidate Verification

## Candidate

- Package: `python-reliability-lab`
- Version: `1.0.0`
- Status: published as the latest public GitHub release
- Repository: https://github.com/darshakm/python-reliability-lab
- Release: https://github.com/darshakm/python-reliability-lab/releases/tag/v1.0.0
- Version and tag: `1.0.0` / `v1.0.0`
- Published: 2026-11-03
- Maintenance owner: `darshakm`
- Verified environment: Python 3.14.6, macOS arm64

## Source-tree checks

- 159 tests passed
- Ruff passed
- Strict mypy passed across 23 source/test files
- Both runnable examples produced their documented output
- Local Markdown links resolved
- Credential-pattern scan found no probable credentials
- Synthetic token strings in tests were reviewed as fixtures
- Local Git history was initialized and the working tree was clean

## Clean-clone check

A new local clone was created in a temporary directory with no ignored workspace
state. A new virtual environment installed `.[dev]` from that clone. The clone
then produced:

- 159 passing tests
- Passing Ruff and strict mypy
- Both documented example outputs
- Successful isolated wheel and source builds
- A clean Git working tree after verification

## Distribution checks

- Isolated source and wheel builds succeeded
- Wheel installed into an external temporary virtual environment
- Installed version reported `1.0.0`
- Installed module resolved from external `site-packages`, not the source tree
- `py.typed` was present
- `pip check` reported no broken requirements
- Both examples ran using the wheel-only environment
- Wheel and source archive contained no caches, `.DS_Store`, environments, or raw
  profile output
- MIT license was included in wheel metadata and the source archive

## Compatibility boundary

The project declares Python 3.12 or newer because it uses Python 3.12 type syntax.
Only Python 3.14.6 was available for this local verification. Test 3.12 and 3.13
before making a public multi-version compatibility claim.

## Publication boundary

After explicit approval of the destination, public visibility, package name,
version, tag scheme, and final publication action, the verified source was
published to GitHub with wheel and source-distribution assets. No PyPI package,
deployment, or separate announcement was created.
