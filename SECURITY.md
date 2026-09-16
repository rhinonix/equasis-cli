# Security policy

## Supported versions

Security fixes are released for the latest minor version of equasis-cli.

| Version | Supported |
| --- | --- |
| 3.x | Yes |
| 2.x and earlier | No |

## Reporting a vulnerability

Please report vulnerabilities privately, either through
[GitHub private vulnerability reporting](https://github.com/rhinonix/equasis-cli/security/advisories/new)
or by e-mail to
[rhinonix.github.exclaim769@slmail.me](mailto:rhinonix.github.exclaim769@slmail.me).

Include a description of the issue, the steps to reproduce it, the affected version, and
its potential impact. You can expect an acknowledgement within five working days. Please
allow time for a fix to be released before disclosing the issue publicly.

## Scope

Examples of issues to report:

- Exposure of Equasis credentials, for example through logs, error messages, file
  permissions, or saved output
- Writing files outside the location the user asked for
- Vulnerabilities in how equasis-cli handles content received from Equasis

Problems with the Equasis website itself should be reported to Equasis.

## Handling credentials safely

- Prefer `equasis configure --setup` or environment variables over `--password`, which is
  visible in shell history and process listings.
- The credentials file and page cache are created readable only by you. Keep it that way.
- Pages saved with `--save-html` and the page cache contain your Equasis account name.
  Remove it before sharing a page.
