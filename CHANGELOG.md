# CHANGELOG


## v0.0.2 (2026-02-08)

### Bug Fixes

- Detect JSON responses by parsing body instead of content-type
  ([`11a1761`](https://github.com/ralph089/apick/commit/11a17613e35f4defe14ef342b2fd52542fb2ece2))

### Build System

- **deps**: Bump python-semantic-release/publish-action from 9 to 10
  ([`42c706a`](https://github.com/ralph089/apick/commit/42c706a8aca520899d68695d324c985e54d9d670))

Bumps
  [python-semantic-release/publish-action](https://github.com/python-semantic-release/publish-action)
  from 9 to 10. - [Release
  notes](https://github.com/python-semantic-release/publish-action/releases) -
  [Changelog](https://github.com/python-semantic-release/publish-action/blob/main/releaserc.toml) -
  [Commits](https://github.com/python-semantic-release/publish-action/compare/v9...v10)

--- updated-dependencies: - dependency-name: python-semantic-release/publish-action
  dependency-version: '10'

dependency-type: direct:production

update-type: version-update:semver-major ...

Signed-off-by: dependabot[bot] <support@github.com>


## v0.0.1 (2026-02-06)

### Bug Fixes

- Extract border label and fix formatting
  ([`ed68362`](https://github.com/ralph089/apick/commit/ed68362937393fe8b1a8251057b2b0ee6dbdee7e))

- Sync version to 0.0.1 and fix release workflow
  ([`fb42191`](https://github.com/ralph089/apick/commit/fb42191dc99970d41146750c895e749a659a0c21))

The semantic-release version-bump commit was lost because it wasn't in the local history when
  subsequent commits were pushed. Fix by passing token to checkout (so the push uses the right
  credentials), adding publish-action step for GitHub releases, and restoring __version__ to match
  the existing v0.0.1 tag.

### Build System

- Add Dependabot configuration file
  ([`8c74469`](https://github.com/ralph089/apick/commit/8c74469b22ff7306580324f0babd02e912dc245f))

Configured Dependabot for weekly updates.

### Code Style

- Polish fzf pickers with color scheme, ghost text, and separators
  ([`ce3325b`](https://github.com/ralph089/apick/commit/ce3325be533cae9aac0dc05af16eb8704d8611ca))

Add shared FZF_COLOR theme and _fzf_base_args helper to unify styling across endpoint and history
  pickers. Adds highlight-line, ghost text placeholders, inline-right info, preview labels, and dim
  separators between detail sections.

- Polish fzf UI with border, pointer, and cleaner search
  ([`cd571c0`](https://github.com/ralph089/apick/commit/cd571c00b5505bdc1005b5e5ff487de060357077))

- Add --nth/--with-nth to hide internal index from display and search - Add rounded border with
  labels for endpoint picker and history - Use ▶ pointer instead of default cursor - Regenerate demo
  GIF

### Continuous Integration

- Add workflow_dispatch trigger to release workflow
  ([`5310150`](https://github.com/ralph089/apick/commit/531015025f03d04aec065a9a08d3bec203f682b9))

### Documentation

- Add terminal demo GIF and VHS tape
  ([`e37b8da`](https://github.com/ralph089/apick/commit/e37b8dae722b15927f8b959b65625e980e84876a))

- Fix Python version requirement
  ([`6b808a0`](https://github.com/ralph089/apick/commit/6b808a0b52ebae92797b8ba05dd42c266c2b409c))

- Regenerate demo GIF with polished fzf layout
  ([`38e5790`](https://github.com/ralph089/apick/commit/38e57906562e20edc978d6cd6b706942fa1c3a2b))

### Refactoring

- Replace requests with httpx
  ([`3b5541c`](https://github.com/ralph089/apick/commit/3b5541c4d543bc4c47bc1d3a4ef8fbc88cf6c624))

Swap the HTTP client from requests to httpx for a lighter dependency footprint. Update README to
  highlight the lightweight design.
