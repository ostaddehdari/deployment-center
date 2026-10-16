# Deployment Center

Central release and deployment conventions for projects across multiple servers.

> STATUS: Bootstrap only. No live deployment, server credential, or release installer has been configured.

## Boundaries

- Source repositories can live on GitHub **or GitLab**. No migration is required.
- GitHub Releases are the delivery channel for immutable archives and install scripts.
- Every project gets a versioned artifact, project-specific installer, checksum and changelog.
- Production secrets, `.env`, databases, user uploads and SSH credentials **must never be committed**.
- This repository is currently **public**. Do not add private inventory or deployment credentials.
- Installing or updating any application requires its own verified runbook and backup/rollback strategy.
- Do not run arbitrary online installer scripts as root before reviewing and verifying them.

## Inventory: first collect, then review

On EACH host, run the read-only inventory script and inspect the output:

```bash
bash scripts/inventory-readonly.sh > inventory-$(hostname).txt
```

Review/redact private hostnames, domains, keys and internal paths before sharing. Inventory collection never sends data to GitHub and does not change the server.

Initial assessment (from user-provided server listings, not live server verification):
- Host A: Zoha (web/API/MCP), Edu Admin, PostgreSQL, MongoDB, Redis.
- Host B: CryptoSniper, Ensha, StagePilot, Vianoor and other services; multiple historical worktrees and containers.
- Paths or project names are not sufficient to infer authoritative deploy roots or ownership. Distinguish live systems from backups, test systems and old releases.

## Release contract

For each project, publish one immutable tag `vX.Y.Z` and GitHub Release assets:

```text
<project>-vX.Y.Z.zip
install.sh
SHA256SUMS
release-manifest.json
```

Installer must bind to the SAME exact release tag, verify SHA256, preflight dependencies, backup state, migrate safely, perform health check, log results and fail closed. A `latest` wrapper must first resolve and pin one immutable tag. Avoid executing unverified downloaded shell scripts.

## Source code on GitLab

A GitLab source repository can build artifacts in GitLab CI, then a narrowly-scoped credential or GitHub App publishes them to a separate **GitHub release repository**. Alternatively a controlled build job can publish from a vetted local checkout. Do not change GitLab `origin` or mirror proprietary source code to public GitHub by default.

## Onboarding workflow

1. Gather read-only inventory and confirm services, ports and deployment directories.
2. Choose a stable source repository and an artifact repository for each deployable project.
3. Implement & test a project-specific build, installer and rollback on staging.
4. Publish checksummed release assets; independently verify the downloaded bytes.
5. Introduce a restricted per-host `deployctl` after project installers pass testing.
6. Roll out incrementally; never run a blanket upgrade across all applications untested.

See `docs/project-manifest.example.yaml` for a non-secret project manifest example.
