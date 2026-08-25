"""Publish the website manifest and build artifacts by committing in the local repo.

The commit is built directly as git objects from the artifact patterns. The
working copy and index are only touched after the push succeeds, so a cancel
or failure at any point leaves the repo exactly as it was.
"""

from __future__ import annotations

import fnmatch
import glob
import io
import json
import os
import time
from datetime import date
from typing import cast

from dulwich import porcelain
from dulwich.index import index_entry_from_stat
from dulwich.object_store import commit_tree_changes, iter_tree_contents
from dulwich.objects import Blob, Commit, ObjectID, Tree
from dulwich.refs import Ref
from dulwich.repo import Repo, get_user_identity

from mirror.commons.config import GITHUB_TOKEN, OUTPUT_DIRECTORY, WEBSITE_DIRECTORY
from mirror.commons.constants import (
    ALBUM_SUBJECT_PREFIX,
    COMMIT_MESSAGE_NAME_LIMIT,
    MANIFEST_PATTERNS,
    WEBSITE_ARTIFACT_PATTERNS,
    WEBSITE_BRANCH,
)
from mirror.commons.exceptions import GithubPublishError
from mirror.services.github_types import AlbumChanges, AlbumFingerprints

# artifact sources: (directory on disk, path prefix in the repo, patterns)
ARTIFACT_SPECS = (
    (OUTPUT_DIRECTORY, "manifest", MANIFEST_PATTERNS),
    (WEBSITE_DIRECTORY, "", WEBSITE_ARTIFACT_PATTERNS),
)

# temporary ref the publish commit is pushed from; deleted afterwards
PUBLISH_REF = Ref(b"refs/mirror/publish")

# regular non-executable file mode for published artifacts
ARTIFACT_FILE_MODE = 0o100644

MAIN_REF = Ref(b"refs/heads/" + WEBSITE_BRANCH.encode())


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


def read_tree_blob(repo: Repo, tree_id: ObjectID, path: str) -> bytes | None:
    """Read a file's bytes from a git tree, or None when absent."""
    tree = cast(Tree, repo[tree_id])
    try:
        blob_id = tree.lookup_path(repo.object_store.__getitem__, path.encode())[1]
    except KeyError:
        return None
    return cast(Blob, repo[blob_id]).data


def load_tip_triples(repo: Repo, tree_id: ObjectID) -> list:
    """Load the published triples from the tip tree, or an empty list when unreadable.

    A missing or broken published manifest must not block publication. The
    diff then reports every album as added.
    """
    env_bytes = read_tree_blob(repo, tree_id, "manifest/env.json")
    if env_bytes is None:
        return []

    try:
        publication_id = json.loads(env_bytes)["publication_id"]
        triples_bytes = read_tree_blob(repo, tree_id, f"manifest/triples.{publication_id}.json")
        return [] if triples_bytes is None else json.loads(triples_bytes)
    except (KeyError, TypeError, ValueError):
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
        return f"publish artifacts {date.today().isoformat()}"
    return ", ".join(parts)


def list_pattern_files(directory: str, patterns: tuple[str, ...]) -> list[str]:
    """List the files in a directory that match the given artifact patterns."""
    paths = []
    for pattern in patterns:
        matches = glob.glob(os.path.join(directory, pattern))
        paths.extend(match for match in matches if os.path.isfile(match))
    return paths


def matches_artifact(repo_path: str) -> bool:
    """Report whether a repo path matches any artifact pattern."""
    for spec in ARTIFACT_SPECS:
        prefix, patterns = spec[1], spec[2]
        if prefix and not repo_path.startswith(prefix + "/"):
            continue
        relative = repo_path[len(prefix) + 1 :] if prefix else repo_path
        for pattern in patterns:
            # slash-count check keeps fnmatch from recursing into subdirectories
            if relative.count("/") == pattern.count("/") and fnmatch.fnmatch(relative, pattern):
                return True
    return False


def collect_local_artifacts() -> dict[str, str]:
    """Map repo paths to the local files that should be published there."""
    collected = {}
    for source_root, prefix, patterns in ARTIFACT_SPECS:
        for file_path in list_pattern_files(source_root, patterns):
            relative = os.path.relpath(file_path, source_root)
            repo_path = f"{prefix}/{relative}" if prefix else relative
            collected[repo_path] = file_path
    return collected


def find_tree_artifacts(repo: Repo, tree_id: ObjectID) -> set[str]:
    """List the repo paths in a tree that match the artifact patterns."""
    found = set()
    for entry in iter_tree_contents(repo.object_store, tree_id):
        path = entry.path.decode()
        if matches_artifact(path):
            found.add(path)
    return found


def store_file_blob(repo: Repo, file_path: str) -> ObjectID:
    """Store a file's content as a blob object. Returns the blob id."""
    with open(file_path, "rb") as handle:
        blob = Blob.from_string(handle.read())
    repo.object_store.add_object(blob)
    return blob.id


def build_artifact_changes(repo: Repo, tree_id: ObjectID) -> list:
    """Build the tree changes that replace the tip's artifacts with local ones."""
    local = collect_local_artifacts()
    existing = find_tree_artifacts(repo, tree_id)

    changes = []
    for repo_path, file_path in sorted(local.items()):
        blob_id = store_file_blob(repo, file_path)
        changes.append((repo_path.encode(), ARTIFACT_FILE_MODE, blob_id))
    for stale_path in sorted(existing - set(local)):
        changes.append((stale_path.encode(), None, None))
    return changes


def fetch_remote_tip(origin_url: str) -> ObjectID:
    """Read origin's main tip commit id without fetching objects."""
    result = porcelain.ls_remote(origin_url)
    remote_tip = result.refs.get(MAIN_REF)
    if remote_tip is None:
        raise GithubPublishError(f"origin has no {MAIN_REF.decode()} ref")
    return remote_tip


def read_ready_tip(repo: Repo, origin_url: str) -> ObjectID:
    """Check the repo is on main and level with origin. Returns the tip id."""
    if repo.refs.read_ref(Ref(b"HEAD")) != b"ref: " + MAIN_REF:
        raise GithubPublishError("website repo is not on main; check it out before publishing")

    remote_tip = fetch_remote_tip(origin_url)
    local_tip = repo.refs[MAIN_REF]
    if local_tip != remote_tip:
        raise GithubPublishError(
            f"local main ({local_tip.decode()[:10]}) does not match origin"
            f" ({remote_tip.decode()[:10]}); reconcile the website repo before publishing"
        )
    return local_tip


def create_publish_commit(
    repo: Repo, tree_id: ObjectID, parent: ObjectID, message: str
) -> ObjectID:
    """Create the publish commit object. Moves no refs."""
    commit = Commit()
    commit.tree = tree_id
    commit.parents = [parent]

    identity = get_user_identity(repo.get_config_stack())
    commit.author = commit.committer = identity
    commit.author_time = commit.commit_time = int(time.time())
    offset = -time.altzone if time.localtime().tm_isdst else -time.timezone
    commit.author_timezone = commit.commit_timezone = offset
    commit.message = message.encode()

    repo.object_store.add_object(commit)
    return commit.id


def push_ref(remote_url: str, refspec: bytes) -> None:
    """Push a refspec from the website repo. Raise on any rejected ref."""
    result = None
    failure = ""
    try:
        result = porcelain.push(
            WEBSITE_DIRECTORY,
            remote_url,
            refspec,
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


def refresh_artifact_index(repo: Repo, changes: list) -> None:
    """Update the index entries for published artifacts, leaving staged work alone."""
    index = repo.open_index()
    for path, mode, blob_id in changes:
        if mode is None:
            if path in index:
                del index[path]
            continue
        file_path = os.path.join(WEBSITE_DIRECTORY, os.fsdecode(path))
        index[path] = index_entry_from_stat(os.stat(file_path), blob_id, mode)
    index.write()


def push_publish_commit(
    repo: Repo, origin_url: str, commit_id: ObjectID, prior_tip: ObjectID
) -> None:
    """Push the publish commit, then advance local main."""
    repo.refs[PUBLISH_REF] = commit_id
    try:
        push_ref(authenticate_url(origin_url), PUBLISH_REF + b":" + MAIN_REF)
    finally:
        repo.refs.remove_if_equals(PUBLISH_REF, commit_id)

    repo.refs.set_if_equals(MAIN_REF, prior_tip, commit_id)


def publish_manifest() -> str | None:
    """Publish the manifest and build artifacts by committing in the local repo.

    Returns the commit message, or None when nothing changed.
    """
    if not GITHUB_TOKEN:
        raise GithubPublishError("GITHUB_TOKEN is not set")

    origin_url = read_origin_url()
    with Repo(WEBSITE_DIRECTORY) as repo:
        local_tip = read_ready_tip(repo, origin_url)
        tip_tree = cast(Commit, repo[local_tip]).tree

        changes = build_artifact_changes(repo, tip_tree)
        new_tree = commit_tree_changes(repo.object_store, tip_tree, changes)
        if new_tree == tip_tree:
            return None

        message = derive_commit_message(
            load_tip_triples(repo, tip_tree), load_publication_triples(OUTPUT_DIRECTORY)
        )
        commit_id = create_publish_commit(repo, new_tree, local_tip, message)
        push_publish_commit(repo, origin_url, commit_id, local_tip)
        refresh_artifact_index(repo, changes)

    return message
