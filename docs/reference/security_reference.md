# Security reference

The application is local and single-user, but it handles API keys, resume data, and application notes.

Pay particular attention to secret leakage, unsafe HTML rendering of job descriptions, malformed API payloads, unrestricted resume file access, SQL injection, dependency vulnerabilities, and accidental exposure if deployment moves beyond localhost.

For changed security-sensitive behavior, add validation and failure-path tests and document any intentional local-only assumption.
