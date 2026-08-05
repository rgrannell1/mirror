"""Publish the website manifest to GitHub through a throwaway clone.

The main working copy is never touched by git, so a cancelled or failed
publish cannot leave it inconsistent.
"""

from __future__ import annotations

import glob
import io
import json
import os
import shutil
from datetime import date

from dulwich import porcelain
from dulwich.repo import Repo

from mirror.commons.config import GITHUB_TOKEN, OUTPUT_DIRECTORY, WEBSITE_DIRECTORY
from mirror.commons.constants import (
    ALBUM_SUBJECT_PREFIX,
    COMMIT_MESSAGE_NAME_LIMIT,
    MANIFEST_PATTERNS,
    WEBSITE_BRANCH,
)
from mirror.commons.exceptions import GithubPublishError
from mirror.services.github_types import AlbumChanges, AlbumFingerprints


def read_origin_url() -> str:
    """Read the origin URL from the website repository configuration."""
    with Repo(WEBSITE_DIRECTORY) as website_repo:
        url = website_repo.get_config().get(("remote", "origin"), "url")
    return url.decode()


def authenticate_url(url: str) -> str:
    """Embed the GitHub token into an https remote URL."""
    if not GITHUB_TOKEN:
        raise GithubPublishError("GITHUB_TOKEN is not set")
    if not url.startswith("https://"):
        raise GithubPublishError(f"origin URL must be https to authenticate: {url}")
    return url.replace("https://", f"https://x-access-token:{GITHUB_TOKEN}@", 1)


def conceal_token(text: str) -> str:
    """Strip the GitHub token from error text before it reaches the logs."""
    if GITHUB_TOKEN and GITHUB_TOKEN in text:
        return text.replace(GITHUB_TOKEN, "***")
    return text


def load_publication_triples(manifest_dir: str) -> list:
    """Load the triples file that env.json names in a manifest directory."""
    with open(os.path.join(manifest_dir, "env.json")) as env_handle:
        publication_id = json.load(env_handle)["publication_id"]

    with open(os.path.join(manifest_dir, f"triples.{publication_id}.json")) as triples_handle:
        return json.load(triples_handle)


def load_previous_triples(manifest_dir: str) -> list:
    """Load the already-published triples, or an empty list when unreadable.

    A missing or broken remote manifest must not block publication. The diff
    then reports every album as added.
    """
    try:
        return load_publication_triples(manifest_dir)
    except (KeyError, OSError, TypeError, ValueError):
        # ValueError also covers JSONDecodeError and UnicodeDecodeError
        return []


def map_photos_to_albums(triples: list) -> dict[str, str]:
    """Map each photo subject to its album id."""
    return {
        str(subject): str(target) for subject, relation, target in triples if relation == "albumId"
    }


def resolve_album_id(subject: object, photo_albums: dict[str, str]) -> str | None:
    """Resolve a triple subject to an album id, if it belongs to one."""
    text = str(subject)
    if text.startswith(ALBUM_SUBJECT_PREFIX):
        return text.removeprefix(ALBUM_SUBJECT_PREFIX).removesuffix("]")
    return photo_albums.get(text)


def group_triples_by_album(triples: list) -> AlbumFingerprints:
    """Fingerprint each album: its own triples plus those of its photos."""
    photo_albums = map_photos_to_albums(triples)
    grouped: AlbumFingerprints = {}

    for subject, relation, target in triples:
        album_id = resolve_album_id(subject, photo_albums)
        if album_id is None:
            continue
        fingerprint = json.dumps([subject, relation, target], ensure_ascii=False)
        grouped.setdefault(album_id, set()).add(fingerprint)

    return grouped


def read_album_names(triples: list) -> dict[str, str]:
    """Map album ids to their display names."""
    names = {}
    for subject, relation, target in triples:
        album_id = resolve_album_id(subject, {})
        if album_id is not None and relation == "name":
            names[album_id] = str(target)
    return names


def describe_albums(album_ids: list[str], names: dict[str, str]) -> str:
    """Name the first few albums, then count the rest."""
    labels = [names.get(album_id, album_id) for album_id in album_ids]
    shown = labels[:COMMIT_MESSAGE_NAME_LIMIT]
    hidden_count = len(labels) - len(shown)

    if hidden_count > 0:
        return ", ".join(shown) + f" and {hidden_count} more"
    return ", ".join(shown)


def diff_albums(old_albums: AlbumFingerprints, new_albums: AlbumFingerprints) -> AlbumChanges:
    """Split album ids into added, updated, and removed sets."""
    added = sorted(set(new_albums) - set(old_albums))
    removed = sorted(set(old_albums) - set(new_albums))
    shared = set(old_albums) & set(new_albums)
    changed = (album_id for album_id in shared if old_albums[album_id] != new_albums[album_id])
    updated = sorted(changed)
    return added, updated, removed


def describe_changes(
    old_albums: AlbumFingerprints, new_albums: AlbumFingerprints, names: dict[str, str]
) -> list[str]:
    """List the album-level differences between two publications."""
    added, updated, removed = diff_albums(old_albums, new_albums)

    parts = []
    if added:
        parts.append(f"adds {describe_albums(added, names)}")
    if updated:
        parts.append(f"updates {describe_albums(updated, names)}")
    if removed:
        parts.append(f"removes {describe_albums(removed, names)}")
    return parts


def derive_commit_message(old_triples: list, new_triples: list) -> str:
    """Describe which albums the publication adds, updates, or removes."""
    names = read_album_names(old_triples) | read_album_names(new_triples)
    old_albums = group_triples_by_album(old_triples)
    new_albums = group_triples_by_album(new_triples)

    parts = describe_changes(old_albums, new_albums, names)
    if not parts:
        return f"publish manifest {date.today().isoformat()}"
    return ", ".join(parts)


def list_manifest_files(manifest_dir: str) -> list[str]:
    """List the files in a manifest directory that match the artifact patterns."""
    paths = []
    for pattern in MANIFEST_PATTERNS:
        matches = glob.glob(os.path.join(manifest_dir, pattern))
        paths.extend(match for match in matches if os.path.isfile(match))
    return paths


def sync_manifest(clone_dir: str) -> None:
    """Replace the clone's manifest artifacts with the freshly generated ones.

    Deletes and copies only files matching MANIFEST_PATTERNS, so a bad path
    can never wipe anything beyond the published artifacts.
    """
    target = os.path.join(clone_dir, "manifest")
    for stale_path in list_manifest_files(target):
        os.remove(stale_path)

    for source_path in list_manifest_files(OUTPUT_DIRECTORY):
        relative = os.path.relpath(source_path, OUTPUT_DIRECTORY)
        destination = os.path.join(target, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source_path, destination)


def stage_manifest(clone_dir: str) -> bool:
    """Stage manifest changes in the clone. Report whether anything changed."""
    # "all" lists files inside new directories; "normal" collapses them to the directory
    status = porcelain.status(clone_dir, untracked_files="all")
    new_paths = [os.path.join(clone_dir, os.fsdecode(path)) for path in status.untracked]
    if new_paths:
        porcelain.add(clone_dir, paths=new_paths)

    staged = any(paths for paths in status.staged.values())
    return bool(new_paths or staged or status.unstaged)


def push_clone(clone_dir: str, remote_url: str) -> None:
    """Push the clone to GitHub. Raise on any rejected ref."""
    result = None
    failure = ""
    try:
        result = porcelain.push(
            clone_dir,
            remote_url,
            WEBSITE_BRANCH,
            outstream=io.BytesIO(),
            errstream=io.BytesIO(),
        )
    except Exception as err:  # noqa: BLE001
        failure = conceal_token(str(err))

    # raised outside the except block so the original error, which can embed the
    # tokened URL, is not kept on the exception chain that reaches the zahir logs
    if result is None:
        raise GithubPublishError(f"push failed: {failure}")

    rejected = {
        ref.decode(): str(error)
        for ref, error in (result.ref_status or {}).items()
        if error is not None
    }
    if rejected:
        raise GithubPublishError(f"push rejected: {conceal_token(str(rejected))}")


def commit_and_push(clone_dir: str, origin_url: str, message: str) -> None:
    """Commit staged manifest changes and push them to GitHub."""
    porcelain.commit(clone_dir, message=message, all=True)
    push_clone(clone_dir, authenticate_url(origin_url))


def publish_manifest(scratch_dir: str) -> str | None:
    """Publish the manifest via a throwaway clone.

    Returns the commit message, or None when the manifest is unchanged.
    """
    if not GITHUB_TOKEN:
        raise GithubPublishError("GITHUB_TOKEN is not set")

    origin_url = read_origin_url()
    clone_dir = os.path.join(scratch_dir, "clone")
    porcelain.clone(origin_url, clone_dir, depth=1, branch=WEBSITE_BRANCH, errstream=io.BytesIO())

    old_triples = load_previous_triples(os.path.join(clone_dir, "manifest"))
    sync_manifest(clone_dir)

    if not stage_manifest(clone_dir):
        return None

    message = derive_commit_message(old_triples, load_publication_triples(OUTPUT_DIRECTORY))
    commit_and_push(clone_dir, origin_url, message)
    return message
