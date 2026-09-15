# Releasing

Releases are cut by the **Prepare Release** workflow
(`.github/workflows/prepare-release.yml`), run manually from the Actions tab on the
default branch. Pick the bump you want:

| Bump | `0.1.4` becomes |
| --- | --- |
| `patch` | `0.1.5` |
| `minor` | `0.2.0` |
| `major` | `1.0.0` |

The workflow runs the full test suite, including the coverage gate, and stops there if
anything fails. Then it:

1. Bumps `version` in `custom_components/orisec/manifest.json`, the field HACS reads.
   Unlike a manual release, this bump is committed to the default branch, so `main` and
   the tag never drift.
2. Generates release notes from the commits since the previous tag and prepends them to
   `CHANGELOG.md`.
3. Commits, tags `vX.Y.Z`, and pushes.
4. Builds `orisec.zip` and publishes the GitHub release with the notes and that asset
   attached. It is attached here rather than by `release.yml`, because a release created
   with the default `GITHUB_TOKEN` does not trigger other workflows. `release.yml` still
   covers releases published by hand, and gates the asset on a green `ci.yml` run so a
   hand-published release with failing tests never becomes installable.

Tick **dry run** to see the resulting version and changelog in the workflow summary
without committing, tagging, or publishing anything.

## Beta releases

Tick **beta** to publish a [PEP 440](https://peps.python.org/pep-0440/) pre-release
instead. The bump you pick chooses the base version, and the beta number counts up from
there:

| From | Bump | Beta | Result |
| --- | --- | --- | --- |
| `0.1.0` | `minor` | yes | `0.2.0b1` |
| `0.2.0b1` | any | yes | `0.2.0b2` |
| `0.2.0b2` | any | no | `0.2.0` |

Once a beta line is open the base version is already decided, so `release_type` no longer
applies to it: a further beta increments the beta number, and an unticked run promotes
the same base to stable. Both ignore the bump you pick, so to change the base, finish or
abandon the line first.

Betas are marked as pre-releases on GitHub and are deliberately kept out of
`CHANGELOG.md`, which would otherwise carry an entry per beta and a near-empty one for
the stable release. The stable release that promotes them compares against the last
*stable* tag instead, so its notes cover everything the betas shipped.

Installing one is opt-in on the user's side; see [beta
versions](installation.md#beta-versions).

## Changelog entries

Notes are built from the non-merge commits since the previous tag.
[Conventional commit](https://www.conventionalcommits.org/) subjects are grouped into
sections (`feat:` → Features, `fix:` → Bug Fixes, and so on); a `!` marker or a
`BREAKING CHANGE:` footer moves a commit to Breaking Changes. Commits that do not follow
the convention are listed verbatim under Other Changes, so nothing is dropped.

The version in `manifest.json` is the starting point for the bump, so the first run of
the workflow moves the current `0.1.0` on to `0.1.1`, `0.2.0`, or `1.0.0`. To publish the
current version as-is instead, tag it by hand once.
