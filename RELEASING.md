# Releasing

Releases are published to [PyPI](https://pypi.org/p/equasis-cli) by the
[Release workflow](.github/workflows/release.yml) using
[trusted publishing](https://docs.pypi.org/trusted-publishers/): PyPI trusts this
repository's workflow directly, so no API tokens are created or stored.

## One-time setup

Do these steps once, before the first release.

### 1. Create the accounts

1. Register at [pypi.org](https://pypi.org/account/register/) and at
   [test.pypi.org](https://test.pypi.org/account/register/). TestPyPI is a separate
   practice site with its own accounts.
2. Verify your e-mail address on both sites.
3. Enable two-factor authentication on both (Account settings, then "Add 2FA with
   authentication application"). PyPI requires it. Store the recovery codes somewhere safe.

### 2. Register the trusted publishers

The project does not exist on PyPI yet, so add a *pending* publisher; the first upload
creates the project.

On **test.pypi.org**, open [Account settings, Publishing](https://test.pypi.org/manage/account/publishing/)
and add a GitHub pending publisher with:

| Field | Value |
| --- | --- |
| PyPI project name | `equasis-cli` |
| Owner | `rhinonix` |
| Repository name | `equasis-cli` |
| Workflow name | `release.yml` |
| Environment name | `testpypi` |

Repeat on **pypi.org** at [Account settings, Publishing](https://pypi.org/manage/account/publishing/)
with the same values, except **Environment name** `pypi`.

### 3. Create the GitHub environments

In the repository, open **Settings, Environments**:

1. Create an environment named `testpypi`.
2. Create an environment named `pypi`. Under **Deployment protection rules**, enable
   **Required reviewers** and add yourself. Nothing is then published to PyPI until you
   approve it.

## Every release

1. **Prepare the release pull request.**
   - Set the version in `src/equasis_cli/_version.py` (for example `3.1.0`).
   - In `CHANGELOG.md`, rename "Unreleased" to the version and date, and add a new empty
     "Unreleased" section and comparison link.
   - Merge the pull request after CI passes.

2. **Dry run on TestPyPI.** In the **Actions** tab, open the Release workflow, choose
   **Run workflow** on `main`, and wait for it to finish. Then check the package in a clean
   environment:

   ```bash
   pipx install --index-url https://test.pypi.org/simple/ \
       --pip-args="--extra-index-url https://pypi.org/simple/" equasis-cli
   equasis --version
   equasis vessel 9811000
   pipx uninstall equasis-cli
   ```

   A version number can be uploaded to TestPyPI only once. To repeat a dry run for the
   same version, add a suffix such as `3.1.0rc1` to the version first.

3. **Publish.** Create a GitHub release:
   - Go to **Releases**, then **Draft a new release**.
   - Create a new tag named `v` plus the version (for example `v3.1.0`) on `main`. The
     workflow checks that the tag matches the package version.
   - Use the version as the title, and paste the changelog section as the description.
   - Choose **Publish release**.

4. **Approve.** Open the running Release workflow and approve the `pypi` deployment.

5. **Verify.**

   ```bash
   pipx install equasis-cli     # or: pipx upgrade equasis-cli
   equasis --version
   ```

Published versions cannot be replaced on PyPI. If something is wrong, fix it and release
a new version; a broken release can be yanked from the project's PyPI page.
