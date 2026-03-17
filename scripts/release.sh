#!/usr/bin/env bash
#
# Release pio-ulp-cmake.
#
# Usage:
#   scripts/release.sh <version>        # e.g. scripts/release.sh 0.2.0
#   scripts/release.sh -n <version>     # dry run — print what would happen
#
# Prerequisites:
#   - Repo clean, on main, up to date with origin
#   - CHANGELOG.md [Unreleased] section has content
#   - gh CLI authenticated

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DRY_RUN=false
TODAY="$(date +%Y-%m-%d)"

# --- Helpers ----------------------------------------------------------------

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "==> $*"; }
step() { echo "  -> $*"; }

run() {
    if $DRY_RUN; then
        echo "  [dry-run] $*"
    else
        "$@"
    fi
}

# --- Argument parsing -------------------------------------------------------

if [[ "${1:-}" == "-n" ]]; then
    DRY_RUN=true
    shift
fi

VERSION="${1:-}"
[[ -n "$VERSION" ]] || die "Usage: scripts/release.sh [-n] <version>"
TAG="v${VERSION}"

# --- Preflight checks -------------------------------------------------------

info "Preflight checks"

# gh CLI
command -v gh >/dev/null 2>&1 || die "gh CLI not found"
gh auth status >/dev/null 2>&1 || die "gh CLI not authenticated — run 'gh auth login'"

step "Checking repo ($REPO_DIR)"

[[ -d "$REPO_DIR/.git" ]] || die "not a git repo"

branch="$(git -C "$REPO_DIR" branch --show-current)"
[[ "$branch" == "main" ]] || die "on branch '$branch', expected 'main'"

status="$(git -C "$REPO_DIR" diff --stat HEAD)"
[[ -z "$status" ]] || die "uncommitted changes:\n$status"

git -C "$REPO_DIR" fetch origin --quiet
behind="$(git -C "$REPO_DIR" rev-list HEAD..origin/main --count)"
[[ "$behind" == "0" ]] || die "$behind commits behind origin/main"

ahead="$(git -C "$REPO_DIR" rev-list origin/main..HEAD --count)"
[[ "$ahead" == "0" ]] || die "$ahead unpushed commits"

# Tag must not already exist
if git -C "$REPO_DIR" tag -l "$TAG" | grep -q "$TAG"; then
    die "tag $TAG already exists"
fi

# CHANGELOG.md must have content under [Unreleased]
[[ -f "$REPO_DIR/CHANGELOG.md" ]] || die "CHANGELOG.md not found"
unreleased_content="$(sed -n '/^## \[Unreleased\]/,/^## \[/{/^## \[/d;p;}' "$REPO_DIR/CHANGELOG.md" | grep -v '^$' || true)"
[[ -n "$unreleased_content" ]] || die "CHANGELOG.md [Unreleased] section is empty"

# library.json must exist
[[ -f "$REPO_DIR/library.json" ]] || die "library.json not found"

info "Preflight OK"

# --- Release ----------------------------------------------------------------

info "Releasing $TAG"

# 1. Update library.json version
step "Updating library.json version to $VERSION"
if ! $DRY_RUN; then
    python3 -c "
import json
path = '$REPO_DIR/library.json'
with open(path) as f:
    data = json.load(f)
data['version'] = '$VERSION'
with open(path, 'w') as f:
    json.dump(data, f, indent=4)
    f.write('\n')
"
fi

# 2. Update CHANGELOG.md — replace [Unreleased] header with versioned one
step "Updating CHANGELOG.md"
if ! $DRY_RUN; then
    sed -i '' "s/^## \[Unreleased\]/## [Unreleased]\n\n## [$VERSION] — $TODAY/" "$REPO_DIR/CHANGELOG.md"
fi

# 3. Extract release notes (content between version header and next ## heading)
notes_file="$(mktemp)"
sed -n "/^## \[$VERSION\]/,/^## \[/{/^## \[/d;p;}" "$REPO_DIR/CHANGELOG.md" \
    | sed '1{/^$/d;}' | sed '${/^$/d;}' > "$notes_file"

# 4. Commit
step "Committing version bump"
run git -C "$REPO_DIR" add CHANGELOG.md library.json
if ! $DRY_RUN; then
    git -C "$REPO_DIR" commit -m "release: $TAG"
fi

# 5. Tag
step "Creating tag $TAG"
run git -C "$REPO_DIR" tag -a "$TAG" -m "$TAG"

# 6. Push
step "Pushing to origin"
run git -C "$REPO_DIR" push origin main
run git -C "$REPO_DIR" push origin "$TAG"

# 7. GitHub release
step "Creating GitHub release"
run gh release create "$TAG" \
    --repo "$(git -C "$REPO_DIR" remote get-url origin | sed 's/\.git$//')" \
    --title "$TAG" \
    --notes-file "$notes_file"

rm -f "$notes_file"

info "Done! Released $TAG"
echo ""
echo "  https://github.com/m-mcgowan/pio-ulp-cmake/releases/tag/$TAG"
