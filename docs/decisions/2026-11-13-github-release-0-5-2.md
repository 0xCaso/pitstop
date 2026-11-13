# Do we make a GitHub release for pitstop 0.5.2?

Decided: 2026-11-13 · Case: c_081d550b-6b0b-47e2-b906-2573f7c990c4

## Question and choice
Do we make a GitHub release v0.5.2 (git tag and release notes)? Chosen: "I make the tag v0.5.2 on main 4ee140c and a
GitHub release. The notes list the 0.5.2 rules, the validate fix and the status warning. From now on, each npm
publish gets a release."

## Why
- Matteo asked whether a GitHub release is needed after `npm publish` of 0.5.2.
- It costs little, gives users a changelog, and links each npm version to a commit.

## Constraints
- Each `npm publish` gets a tag `v<version>` on the published commit and a GitHub release with notes.
- Releases are made as 0xCaso.

## Ruled out
- No release: no changelog that users can read; npm alone does not link a version to its code.

## Comments
none

## Open questions
none

## Sources
- Case c_081d550b-6b0b-47e2-b906-2573f7c990c4.
- `gh release list` and `git tag`: no releases or version tags before this one.
- Release: https://github.com/0xCaso/pitstop/releases/tag/v0.5.2
