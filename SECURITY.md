# Security Policy

## Scope

This repository holds the static website for Errand Desk (https://erranddesk.com): HTML, CSS, icons, and AWS deploy helpers (S3 + CloudFront). It has no server-side code, user accounts, or stored user data.

GitHub secret scanning (with push protection), Dependabot alerts, and CodeQL code scanning are enabled on this repository.

## Reporting a Vulnerability

**Please do not report security issues through public GitHub issues.**

Report privately through GitHub: https://github.com/gpu7/erranddesk/security/advisories/new

Please include a description, steps to reproduce, and the affected URL or file.

- We aim to acknowledge reports within **48 hours**.
- We aim to provide a full response within **7 business days**.

Please give us reasonable time to fix an issue before disclosing it publicly.

## Practices

- Never commit AWS credentials, account IDs, `.env` files, or private keys (see `.gitignore`).
- The S3 bucket is private and served only through CloudFront (Origin Access Control).
- Affiliate links are labeled and use `rel="sponsored nofollow noopener"`.
