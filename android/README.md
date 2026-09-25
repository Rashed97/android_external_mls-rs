<!--
     SPDX-FileCopyrightText: The LineageOS Project
     SPDX-License-Identifier: Apache-2.0
-->

# Building mls-rs for Android

This repository is upstream [mls-rs](https://github.com/awslabs/mls-rs) at commit
`42131c9959efb1d3928428259bc89853027f730d`, from which the crates.io release of `mls-rs` 0.55.2
was cut. Changes to the upstream sources are separate commits on top of the Android build,
which is added alongside the upstream tree:

* `<crate>/cargo_embargo.json` and `<crate>/Android.bp` for the crates built from this
  repository: `mls-rs`, `mls-rs-core`, `mls-rs-crypto-hpke`, `mls-rs-crypto-traits` and
  `mls-rs-identity-x509`.
* `android/vendor/<crate>-<version>/`: crates.io releases, unmodified (each keeps its
  `.cargo-checksum.json`), with their own `cargo_embargo.json` and `Android.bp`.
* `android/patches/`: changes applied to the generated `Android.bp` files.
* `android/cargo/`: symlinks through which Cargo resolves the crates Soong builds (see below).
* `android/regen_android_bp.py`: regenerates every `Android.bp` and `android/cargo/`.
* `Android.bp`: the licence module shared by the mls-rs crates, which ship no licence text.

## Soong modules

| Crate | Source | Module |
|---|---|---|
| `mls-rs` 0.55.2 | `mls-rs/` | `libmls_rs_fork` |
| `mls-rs-core` 0.27.0 | `mls-rs-core/` | `libmls_rs_core_mls_rs` |
| `mls-rs-crypto-hpke` 0.21.0 | `mls-rs-crypto-hpke/` | `libmls_rs_crypto_hpke` |
| `mls-rs-crypto-traits` 0.22.0 | `mls-rs-crypto-traits/` | `libmls_rs_crypto_traits_mls_rs` |
| `mls-rs-identity-x509` 0.21.0 | `mls-rs-identity-x509/` | `libmls_rs_identity_x509` |
| `mls-rs-crypto-rustcrypto` 0.22.1 | `android/vendor/` | `libmls_rs_crypto_rustcrypto` |
| `mls-rs-codec` 0.7.0 | `android/vendor/` | `libmls_rs_codec_mls_rs` |

A module whose name is already used in the tree gets an `_mls_rs` suffix (`module_name_overrides`
in the crate's `cargo_embargo.json`), and `mls-rs` itself becomes `libmls_rs_fork`, since
`external/rust/android-crates-io` has mls-rs 0.39.4. Modules are built for the primary ABI only
(`android/module_block.bp`).

The repository's own `mls-rs-codec`, `mls-rs-codec-derive` and `mls-rs-crypto-rustcrypto` are
not what mls-rs 0.55.2 was released against, so the published releases are used instead:
`mls-rs-codec` 0.7.0 (the repository's copy has later changes under the same version),
`mls-rs-codec-derive` 0.2.0 (the repository's uses darling 0.23) and `mls-rs-crypto-rustcrypto`
0.22.1 (the repository has 0.22.0, without the X.509 certificate checks added in 0.22.1). `mls-rs` and
`mls-rs-core` name `../mls-rs-codec` by path; the generated `Android.bp` files refer to modules by
name, so they link the vendored release without any change to the upstream crates.

## Dependencies

Crates come from `external/rust/android-crates-io` where it has a Cargo-compatible version,
visible to `//external/mls-rs` and built with the features needed. Those used are `cfg-if`,
`debug_tree`, `der_derive`, `hex`, `itertools`, `libc`, `maybe-async`, `mls-rs-codec-derive`,
`proc-macro2`, `quote`, `spin`, `syn` and `thiserror`. Its `mls-rs-codec-derive` 0.2.0 has the
same sources as the release vendored here, which is kept only so that Cargo can resolve the graph.

The others are vendored in `android/vendor/`:

| Crate | Version | Why it is vendored |
|---|---|---|
| `aead` | 0.5.2 | not in android-crates-io |
| `aes` | 0.8.4 | not in android-crates-io |
| `aes-gcm` | 0.10.3 | not in android-crates-io |
| `base16ct` | 0.2.0 | not in android-crates-io |
| `base64ct` | 1.8.3 | not in android-crates-io |
| `block-buffer` | 0.10.4 | not in android-crates-io |
| `chacha20` | 0.9.1 | not in android-crates-io |
| `chacha20poly1305` | 0.10.1 | not in android-crates-io |
| `cipher` | 0.4.4 | not in android-crates-io |
| `const-oid` | 0.9.6 | android-crates-io has 0.10.1; its android-crates-io module is visibility-restricted |
| `cpufeatures` | 0.2.17 | not in android-crates-io |
| `crypto-bigint` | 0.5.5 | not in android-crates-io |
| `crypto-common` | 0.1.7 | not in android-crates-io |
| `ctr` | 0.9.2 | not in android-crates-io |
| `curve25519-dalek` | 4.1.3 | not in android-crates-io |
| `der` | 0.7.10 | its android-crates-io module is visibility-restricted |
| `digest` | 0.10.7 | not in android-crates-io |
| `ecdsa` | 0.16.9 | not in android-crates-io |
| `ed25519` | 2.2.3 | not in android-crates-io |
| `ed25519-dalek` | 2.2.0 | not in android-crates-io |
| `elliptic-curve` | 0.13.8 | not in android-crates-io |
| `ff` | 0.13.1 | not in android-crates-io |
| `flagset` | 0.4.7 | its android-crates-io module is visibility-restricted |
| `generic-array` | 0.14.7 | not in android-crates-io |
| `getrandom` | 0.2.17 | android-crates-io has 0.3.3 |
| `ghash` | 0.5.1 | not in android-crates-io |
| `group` | 0.13.0 | not in android-crates-io |
| `hkdf` | 0.12.4 | not in android-crates-io |
| `hmac` | 0.12.1 | not in android-crates-io |
| `inout` | 0.1.4 | not in android-crates-io |
| `mls-rs-codec` | 0.7.0 | android-crates-io has 0.6.0 |
| `mls-rs-crypto-rustcrypto` | 0.22.1 | not in android-crates-io |
| `opaque-debug` | 0.3.1 | not in android-crates-io |
| `p256` | 0.13.2 | not in android-crates-io |
| `p384` | 0.13.1 | not in android-crates-io |
| `pem-rfc7468` | 0.7.0 | not in android-crates-io |
| `pkcs8` | 0.10.2 | its android-crates-io module is visibility-restricted |
| `poly1305` | 0.8.0 | not in android-crates-io |
| `polyval` | 0.6.2 | not in android-crates-io |
| `primeorder` | 0.13.6 | not in android-crates-io |
| `rand_core` | 0.6.4 | android-crates-io has 0.9.3 |
| `rfc6979` | 0.4.0 | not in android-crates-io |
| `sec1` | 0.7.3 | its android-crates-io module is visibility-restricted |
| `sec1` | 0.8.1 | android-crates-io has 0.7.3; its android-crates-io module is visibility-restricted |
| `sha2` | 0.10.9 | not in android-crates-io |
| `signature` | 2.2.0 | not in android-crates-io |
| `spki` | 0.7.3 | its android-crates-io module is visibility-restricted |
| `subtle` | 2.6.1 | not in android-crates-io |
| `typenum` | 1.20.1 | not in android-crates-io |
| `universal-hash` | 0.5.1 | not in android-crates-io |
| `x25519-dalek` | 2.0.1 | not in android-crates-io |
| `x509-cert` | 0.2.5 | its android-crates-io module is visibility-restricted |
| `zeroize` | 1.9.0 | android-crates-io builds 1.8.1 without `std` |
| `zeroize_derive` | 1.5.0 | android-crates-io has 1.4.2; zeroize 1.9.0 needs ^1.5 |

## Regenerating the Android.bp files

    android/regen_android_bp.py

This needs `cargo`, and `cargo_embargo` and `bpfmt` (`m cargo_embargo bpfmt`). Crates the
platform provides are resolved from crates.io; pass `--offline --registry-dir <dir>` to use a
`cargo vendor` directory instead. `android/Cargo.lock` pins that resolution, so that a
regeneration does not depend on what crates.io or the local registry cache holds at the time;
the script updates it. It lies under the upstream `.gitignore`, so a new copy is added with
`git add -f`. `--check` fails if any `Android.bp`, `android/cargo/` or `android/Cargo.lock` would
change, resolving with `--locked`. With
`ANDROID_BUILD_TOP` set, the result is checked against the tree: no module may be defined
elsewhere, and every dependency must exist and be visible here.

`cargo_embargo` runs once per crate, in metadata mode, so everything a build script would decide
is stated in the crate's `cargo_embargo.json`: `curve25519-dalek` uses its `serial` backend on
every target, and `generic-array` has `relaxed_coherence`. The patches in `android/patches/`
cover what metadata mode cannot express:

* `use-shared-license.patch`, `mls-rs.patch`: point the mls-rs crates at the shared licence
  module; `mls-rs.patch` also drops the `hex` feature, which `cargo_embargo` infers from
  `hex/std` although Cargo does not enable it.
* `aes`, `chacha20`, `poly1305`, `polyval`, `sha2`: add `libcpufeatures`, a dependency Cargo
  enables only for particular target architectures.
* `p256`, `p384`: rename the `ecdsa` alias to `ecdsa_core`, which is how the crate names it.

## Building with Cargo

`mls-rs` and `mls-rs-core` name `../mls-rs-codec` by path, and `[patch]` cannot redirect a path
dependency, so a Cargo build that depends on `mls-rs/` directly compiles the repository's
`mls-rs-codec`, not the release Soong builds. `android/cargo/` holds one symlink per crate
directory of the upstream workspace, pointing at the repository directory, or at the vendored
release for `mls-rs-codec`, `mls-rs-codec-derive` and `mls-rs-crypto-rustcrypto`. Cargo resolves
relative paths lexically, so `../mls-rs-codec` from `android/cargo/mls-rs` reaches the vendored
copy. Soong does not follow symlinked directories, so it never reads an `Android.bp` through them.

A host build uses the Soong crate set by depending on the crates through `android/cargo/`, and by
patching crates.io to the same paths for the vendored crates' own dependencies on them:

    [dependencies]
    mls-rs = { path = "<external/mls-rs>/android/cargo/mls-rs", features = [...] }
    mls-rs-crypto-rustcrypto = { path = "<external/mls-rs>/android/cargo/mls-rs-crypto-rustcrypto" }

    [patch.crates-io]
    mls-rs-codec = { path = "<external/mls-rs>/android/cargo/mls-rs-codec" }
    mls-rs-codec-derive = { path = "<external/mls-rs>/android/cargo/mls-rs-codec-derive" }
    mls-rs-core = { path = "<external/mls-rs>/android/cargo/mls-rs-core" }
    mls-rs-crypto-hpke = { path = "<external/mls-rs>/android/cargo/mls-rs-crypto-hpke" }
    mls-rs-crypto-traits = { path = "<external/mls-rs>/android/cargo/mls-rs-crypto-traits" }
    mls-rs-identity-x509 = { path = "<external/mls-rs>/android/cargo/mls-rs-identity-x509" }

`cargo tree -d` then lists no mls-rs crate twice. Soong builds `mls-rs-codec-derive` from
android-crates-io, whose 0.2.0 has the same sources as the vendored copy Cargo uses.
`regen_android_bp.py` recreates `android/cargo/`, and `--check` fails if it is out of date.

## Licensing

mls-rs is dual-licensed Apache-2.0 OR MIT (`LICENSE-apache`, `LICENSE-mit`); the Soong licence
module declares Apache-2.0. Each vendored crate keeps its own licence files and declares its
licence in its `Android.bp`. Files added for the Android build are Apache-2.0.
