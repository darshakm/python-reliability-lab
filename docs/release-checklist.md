# Release Checklist

This checklist prepares a release but does not authorize publication.

## Code and evidence

- [x] Full pytest suite passes from a clean checkout
- [x] Ruff and strict mypy pass
- [x] README examples execute successfully
- [x] Wheel and source distribution build in isolation
- [x] Installed wheel imports and examples run outside the source tree
- [x] Benchmark commands and reported results are reproducible
- [x] Performance claims state workload, environment, sample size, and limits

## Package and repository

- [x] Final package name and `1.0.0` version approved
- [x] Project URLs point to the approved public GitHub repository
- [x] License file and package metadata verified
- [x] Wheel and source archive contents inspected
- [x] Changelog and release notes match the shipped behavior
- [x] Generated caches, environments, build output, and irrelevant artifacts absent from distributions
- [x] Git history initialized and release-candidate commits reviewed

## Security, privacy, and attribution

- [x] Credential-pattern and staged-diff scans pass
- [x] Examples and fixtures contain only synthetic data
- [x] Logs and reports contain no credentials or sensitive payloads
- [x] Dependency licenses and attributions reviewed
- [x] Material AI assistance disclosed in the technical article

## External action gate

- [x] User approves destination, visibility, package name, version, and content
- [x] Approved public GitHub repository created
- [ ] Only after approval: tag, push, publish, deploy, upload, or announce
- [ ] Published URL, version, date, and maintenance owner recorded in progress
