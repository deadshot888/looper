# Security Policy

## Supported Versions

Security fixes are provided for the latest published minor release.

## Command Trust Boundary

Looper executes mutator, evaluator, and gate commands supplied by the project. These commands are trusted local code and are not contained by an operating-system sandbox. Review configuration and scripts before running them.

Looper limits accidental exposure through isolated workspaces, path containment, environment allowlists, timeouts, output caps, artifact hashes, stale-state checks, and acceptance backups. These controls do not make hostile commands safe.

## Reporting a Vulnerability

Use GitHub's private vulnerability reporting for this repository. Do not open a public issue containing exploit details, credentials, or affected-user data.

Include the Looper version, operating system, minimal reproduction, impact, and whether a configured command must be malicious or the issue is reachable through normal configuration.
