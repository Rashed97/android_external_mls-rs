#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

"""Regenerate every Android.bp in this project from its cargo_embargo.json.

    android/regen_android_bp.py [--offline] [--registry-dir DIR] [--check]

Each crate built for Android has a cargo_embargo.json next to its Cargo.toml: the mls-rs
crates in this repository, and the crates under android/vendor/. cargo_embargo is run once per
crate in metadata mode ("run_cargo": false), exactly as for a standalone crate, but with the
`cargo metadata` output supplied by this script. That is needed for two reasons:

* The mls-rs crates are members of upstream's Cargo workspace, which also holds crates that are
  not built for Android (the aws-lc, OpenSSL, SQLite and uniffi crates). Resolving that workspace
  pulls in their dependencies.
* mls-rs names its sibling crates by path. For mls-rs-codec, mls-rs-codec-derive and
  mls-rs-crypto-rustcrypto the Android build uses the published releases in android/vendor/
  instead of the sources in this repository.

So the crates are resolved through android/cargo/, a tree in which each crate directory is a
symlink: the mls-rs crates point into this repository, except that a crate vendored under
android/vendor/ replaces the repository directory of the same name. The script (re)creates it,
and --check fails if it is out of date. A temporary root package depends on every configured
crate with the features its cargo_embargo.json lists, and patches crates.io to the same paths,
so the resolved graph is the one Soong builds. Cargo resolves relative paths lexically, so
"../mls-rs-codec" from android/cargo/mls-rs reaches the vendored copy, and cargo_embargo writes
each Android.bp through the symlink into the real directory. The tree is committed so that other
Cargo builds, such as a host build of a crate that uses mls-rs, can depend on the same crates.

Crates the platform provides (see android/README.md) come from crates.io, or from --registry-dir,
a `cargo vendor` directory, when working offline. Nothing is generated for them. The resolution
is pinned by android/Cargo.lock, which the script updates; --check resolves with --locked, so it
fails if the lock would change, and does not depend on what crates.io or the local registry cache
hold beyond the locked versions.

cargo_embargo and bpfmt are taken from $ANDROID_BUILD_TOP/out/host/linux-x86/bin, or from PATH.
With ANDROID_BUILD_TOP set, the result is also checked against the tree: no module name may be
defined elsewhere, and every dependency must exist and be visible to //external/mls-rs.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

ANDROID = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ANDROID)
VENDOR = os.path.join(ANDROID, "vendor")
CARGO_TREE = os.path.join(ANDROID, "cargo")
LOCK = os.path.join(ANDROID, "Cargo.lock")


def package_of(crate_dir):
    with open(os.path.join(crate_dir, "Cargo.toml"), "rb") as f:
        pkg = tomllib.load(f)["package"]
    return pkg["name"], pkg["version"]


def configured_crates():
    """Directories holding a cargo_embargo.json: this repository's crates, then android/vendor."""
    dirs = [os.path.join(REPO, d) for d in sorted(os.listdir(REPO))
            if os.path.isfile(os.path.join(REPO, d, "cargo_embargo.json"))]
    dirs += [os.path.join(VENDOR, d) for d in sorted(os.listdir(VENDOR))
             if os.path.isfile(os.path.join(VENDOR, d, "cargo_embargo.json"))]
    return dirs


def toml_str(s):
    return json.dumps(s)


def cargo_tree_links():
    """{name: symlink target} for android/cargo, targets relative to android/cargo."""
    links = {}
    # Every directory of the upstream workspace, so that any relative path resolves.
    for d in sorted(os.listdir(REPO)):
        if os.path.isfile(os.path.join(REPO, d, "Cargo.toml")) and d != "android":
            links[d] = os.path.join("..", "..", d)
    # A vendored release replaces the repository crate of the same name.
    for d in sorted(os.listdir(VENDOR)):
        name, _ = package_of(os.path.join(VENDOR, d))
        if name in links:
            links[name] = os.path.join("..", "vendor", d)
    return links


def sync_cargo_tree(check):
    """Make android/cargo match cargo_tree_links(); with check, only report whether it does."""
    want = cargo_tree_links()
    have = {}
    if os.path.isdir(CARGO_TREE):
        for d in os.listdir(CARGO_TREE):
            p = os.path.join(CARGO_TREE, d)
            have[d] = os.readlink(p) if os.path.islink(p) else None
    if have == want:
        return None
    if check:
        return "android/cargo is out of date"
    if None in have.values():
        sys.exit("android/cargo holds something other than symlinks")
    os.makedirs(CARGO_TREE, exist_ok=True)
    for d in have:
        os.unlink(os.path.join(CARGO_TREE, d))
    for d, target in want.items():
        os.symlink(target, os.path.join(CARGO_TREE, d))
    return None


def canonical_paths():
    """{real crate dir: path cargo should use for it}."""
    canonical = {}
    for d, target in cargo_tree_links().items():
        canonical[os.path.normpath(os.path.join(CARGO_TREE, target))] = os.path.join(CARGO_TREE, d)
    for d in sorted(os.listdir(VENDOR)):
        canonical.setdefault(os.path.join(VENDOR, d), os.path.join(VENDOR, d))
    return canonical


def write_root(tmp, canonical, crates):
    deps, patches, seen = [], [], {}
    for crate_dir in crates + [os.path.join(VENDOR, d) for d in sorted(os.listdir(VENDOR))]:
        name, version = package_of(crate_dir)
        if (name, version) in seen.values():
            continue
        key = name if name not in seen else f"{name}-{version.replace('.', '_')}"
        seen[key] = (name, version)
        path = canonical[crate_dir]
        patches.append(f"{toml_str(key)} = {{ package = {toml_str(name)}, path = {toml_str(path)} }}")
        cfg_path = os.path.join(crate_dir, "cargo_embargo.json")
        if not os.path.exists(cfg_path):
            continue
        with open(cfg_path) as f:
            features = json.load(f).get("features")
        spec = f"package = {toml_str(name)}, path = {toml_str(path)}"
        if features is not None:
            spec += f", default-features = false, features = {json.dumps(features)}"
        deps.append(f"{toml_str(key)} = {{ {spec} }}")
    root = os.path.join(tmp, "android-root")
    os.mkdir(root)
    with open(os.path.join(root, "lib.rs"), "w"):
        pass
    with open(os.path.join(root, "Cargo.toml"), "w") as f:
        f.write('[package]\nname = "android-root"\nversion = "0.0.0"\nedition = "2021"\n'
                'publish = false\n\n[lib]\npath = "lib.rs"\n\n[dependencies]\n'
                + "\n".join(deps) + "\n\n[patch.crates-io]\n" + "\n".join(patches)
                + "\n\n[workspace]\n")
    return root


def tool(name):
    top = os.environ.get("ANDROID_BUILD_TOP")
    if top:
        p = os.path.join(top, "out", "host", "linux-x86", "bin", name)
        if os.access(p, os.X_OK):
            return p
    p = shutil.which(name)
    if not p:
        sys.exit(f"{name} not found: build it (m {name}) or put it on PATH")
    return p


MODULE_RE = re.compile(r"^([a-z_]+) \{\n(.*?)^\}", re.S | re.M)
DEP_KEYS = ("rustlibs", "rlibs", "proc_macros", "static_libs", "shared_libs", "whole_static_libs")


def guard(top, crates):
    """Check the generated modules against the rest of the tree, as Soong would.

    Fails on a module name we define that is also defined elsewhere, and on a dependency that is
    not defined, or not visible to //external/mls-rs, which is where this project lives in the
    tree. Its copy at that path, if any, is not "elsewhere" and is skipped.
    """
    ours, refs = {}, {}
    for c in crates:
        text = open(os.path.join(c, "Android.bp")).read()
        for _, body in MODULE_RE.findall(text):
            m = re.search(r'^    name: "([^"]+)"', body, re.M)
            if not m:
                continue
            ours[m.group(1)] = c
            for key in DEP_KEYS:
                m = re.search(r"^    %s: \[(.*?)\]" % key, body, re.S | re.M)
                for dep in re.findall(r'"([^"]+)"', m.group(1)) if m else []:
                    refs.setdefault(dep, set()).add(os.path.relpath(c, REPO))
    ours["external_mls_rs_license"] = REPO
    skip = {os.path.join(top, "out"), os.path.join(top, ".repo"),
            os.path.join(top, "external", "mls-rs"), REPO}
    elsewhere = {}
    for d, dirs, files in os.walk(top):
        dirs[:] = [x for x in dirs if os.path.join(d, x) not in skip and not x.startswith(".")]
        if "Android.bp" not in files:
            continue
        try:
            text = open(os.path.join(d, "Android.bp"), encoding="utf8", errors="replace").read()
        except OSError:
            continue
        for _, body in MODULE_RE.findall(text):
            m = re.search(r'^    name: "([^"]+)"', body, re.M)
            if not m:
                continue
            vis = re.search(r"^    visibility: \[(.*?)\]", body, re.S | re.M)
            elsewhere.setdefault(m.group(1), (os.path.relpath(d, top),
                                 re.findall(r'"([^"]+)"', vis.group(1)) if vis else None))
    problems = []
    for name in sorted(ours):
        if name in elsewhere:
            problems.append(f"{name} is also defined in {elsewhere[name][0]}")
    for dep, users in sorted(refs.items()):
        if dep in ours:
            continue
        if dep not in elsewhere:
            problems.append(f"{dep} is not defined (used by {', '.join(sorted(users))})")
            continue
        where, vis = elsewhere[dep]
        if vis is not None and not any(v == "//visibility:public"
                                       or v.startswith("//external/mls-rs") for v in vis):
            problems.append(f"{dep} ({where}) is not visible to //external/mls-rs "
                            f"(used by {', '.join(sorted(users))})")
    return problems


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--offline", action="store_true", help="do not access the network")
    ap.add_argument("--registry-dir", help="a `cargo vendor` directory to use for crates.io")
    ap.add_argument("--check", action="store_true",
                    help="regenerate into a copy and fail if any Android.bp, android/cargo or "
                    "android/Cargo.lock would change")
    args = ap.parse_args()

    cargo = shutil.which("cargo")
    if not cargo:
        sys.exit("cargo not found on PATH")
    cargo_embargo = tool("cargo_embargo")
    bpfmt = tool("bpfmt")
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(bpfmt) + os.pathsep + env["PATH"]

    tree_problem = sync_cargo_tree(args.check)
    if tree_problem:
        sys.exit(f"FAILED: {tree_problem}: run android/regen_android_bp.py")
    crates = configured_crates()
    before = {c: open(os.path.join(c, "Android.bp")).read()
              if os.path.exists(os.path.join(c, "Android.bp")) else None for c in crates}

    with tempfile.TemporaryDirectory(prefix="mls-rs-embargo-") as tmp:
        canonical = canonical_paths()
        root = write_root(tmp, canonical, crates)

        if os.path.exists(LOCK):
            shutil.copyfile(LOCK, os.path.join(root, "Cargo.lock"))
        cmd = [cargo, "metadata", "--format-version", "1"]
        if args.offline:
            cmd.append("--offline")
        if args.check:
            cmd.append("--locked")
        if args.registry_dir:
            cmd += ["--config", 'source.crates-io.replace-with="android-registry-dir"',
                    "--config", "source.android-registry-dir.directory="
                    + toml_str(os.path.abspath(args.registry_dir))]
        r = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(r.stderr + "FAILED: cargo metadata"
                     + (" (android/Cargo.lock is missing or out of date: run "
                        "android/regen_android_bp.py)" if args.check else ""))
        meta = json.loads(r.stdout)
        with open(os.path.join(root, "Cargo.lock")) as f:
            lock = f.read()
        lock_changed = lock != (open(LOCK).read() if os.path.exists(LOCK) else None)
        if lock_changed and not args.check:
            with open(LOCK, "w") as f:
                f.write(lock)
        by_manifest = {p["manifest_path"]: p for p in meta["packages"]}

        failed = []
        for crate_dir in crates:
            pkg = by_manifest.get(os.path.join(canonical[crate_dir], "Cargo.toml"))
            if pkg is None:
                failed.append(f"{os.path.relpath(crate_dir, REPO)}: not in the resolved graph")
                continue
            work = os.path.join(tmp, "intermediates", pkg["name"] + "-" + pkg["version"])
            os.makedirs(work)
            one = dict(meta, workspace_members=[pkg["id"]])
            with open(os.path.join(work, "cargo.metadata"), "w") as f:
                json.dump(one, f)
            open(os.path.join(work, "cargo.out"), "w").close()
            if os.path.exists(os.path.join(crate_dir, "Android.bp")):
                os.unlink(os.path.join(crate_dir, "Android.bp"))
            r = subprocess.run([cargo_embargo, "--cargo-bin", os.path.dirname(cargo),
                                "--cargo-out-dir", work, "--reuse-cargo-out",
                                "generate", "cargo_embargo.json"],
                               cwd=crate_dir, env=env, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(os.path.join(crate_dir, "Android.bp")):
                failed.append(f"{os.path.relpath(crate_dir, REPO)}:\n{r.stdout}{r.stderr}")

    changed = [os.path.relpath(c, REPO) for c in crates
               if before[c] != (open(os.path.join(c, "Android.bp")).read()
                                if os.path.exists(os.path.join(c, "Android.bp")) else None)]
    if args.check:
        for c in crates:
            p = os.path.join(c, "Android.bp")
            if before[c] is None:
                if os.path.exists(p):
                    os.unlink(p)
            else:
                with open(p, "w") as f:
                    f.write(before[c])
    top = os.environ.get("ANDROID_BUILD_TOP")
    if top and not failed:
        failed += [f"Soong would reject: {p}" for p in guard(top, crates)]
    elif not top:
        print("ANDROID_BUILD_TOP is not set: not checking against the tree", file=sys.stderr)
    for f in failed:
        print("FAILED: " + f, file=sys.stderr)
    if lock_changed and not args.check:
        print("android/Cargo.lock updated")
    print(f"{len(crates)} crates, {len(changed)} Android.bp changed"
          + ("".join(f"\n  {c}" for c in changed) if changed else ""))
    if failed or (args.check and changed):
        sys.exit(1)


if __name__ == "__main__":
    main()
