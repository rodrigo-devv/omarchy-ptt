#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")/.."
version=$(/usr/bin/python3 -c 'import sys; sys.path.insert(0,"src"); from omarchy_ptt import __version__; print(__version__)')
repository="s3xz/omarchy-ptt"
tag="v$version"
gh auth status --hostname github.com
login=$(gh api user --jq .login)
[[ "$login" == s3xz ]] || { echo 'Entre na conta s3xz para publicar.' >&2; exit 1; }
[[ -z $(git status --porcelain) ]] || { echo 'Commit alterações antes de publicar.' >&2; exit 1; }
/usr/bin/python3 tools/build-release.py
if ! gh repo view "$repository" >/dev/null 2>&1; then
  gh repo create "$repository" --public --description 'Discord push-to-talk across Omarchy/Hyprland workspaces with configurable mouse buttons'
fi
visibility=$(gh repo view "$repository" --json visibility --jq .visibility)
[[ "$visibility" == PUBLIC ]] || { echo 'Repositório existente não é público; revise antes de publicar.' >&2; exit 1; }
if git remote get-url origin >/dev/null 2>&1; then
  remote=$(git remote get-url origin)
  [[ "$remote" == "https://github.com/$repository.git" || "$remote" == "git@github.com:$repository.git" ]] || { echo 'origin aponta para outro destino.' >&2; exit 1; }
else
  git remote add origin "https://github.com/$repository.git"
fi
if git rev-parse "$tag" >/dev/null 2>&1; then
  [[ $(git rev-parse "$tag^{commit}") == $(git rev-parse HEAD) ]] || { echo 'Tag já aponta para outro commit.' >&2; exit 1; }
else
  git tag "$tag"
fi
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin main
git -c credential.helper= -c 'credential.helper=!gh auth git-credential' push origin "$tag"
if ! gh release view "$tag" --repo "$repository" >/dev/null 2>&1; then
  gh release create "$tag" --repo "$repository" --prerelease --title "Omarchy PTT $version" \
    --notes-file docs/RELEASE-NOTES.md \
    "dist/omarchy-ptt-$version.tar.gz" "dist/omarchy-ptt-$version.tar.gz.sha256"
else
  echo 'Release já existe; não será substituída automaticamente.'
fi
gh release view "$tag" --repo "$repository" --json url --jq .url
