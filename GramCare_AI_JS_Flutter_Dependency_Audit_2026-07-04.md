# GramCare AI — JS & Flutter Dependency Audit
**Date:** 2026-07-04
**Scope:** `apps/web_portal`, `apps/react_dashboard`, `backend/node_api`, `apps/mobile_app`

This follows the backend Python dependency audit performed earlier the same day. Each `package.json` was checked for unused packages (via grep of actual import sites, not assumption), each `package-lock.json` was verified for reproducibility via a clean `npm ci`, and `npm audit` was run and re-run after fixes. The Flutter/`pubspec.yaml` work is static-analysis-only — see the "Flutter/mobile_app" section for why.

---

## 1. apps/web_portal

**Unused packages:** none. Every entry in `dependencies` and `devDependencies` has a confirmed usage site — including config-only tools like `@tailwindcss/postcss` (used in `postcss.config.mjs`) and `tailwindcss` (used via `@import "tailwindcss"` in `globals.css`), which a naive `grep src/` pass would miss.

**Lockfile:** `package-lock.json` verified reproducible — a clean `npm ci` against the committed lockfile succeeds with no errors (388 packages).

**npm audit — before:** 2 moderate (0 critical, 0 high).
- `next` (moderate, via bundled `postcss`) and `postcss` (moderate, `<8.5.10` — XSS via unescaped `</style>` in CSS stringify output, [GHSA-qx2v-qp2m-jg93](https://github.com/advisories/GHSA-qx2v-qp2m-jg93)).
- Root cause: Next.js 16.2.9 vendors its **own nested copy** of `postcss@8.4.31` for its internal build pipeline (`node_modules/next/node_modules/postcss`), separate from our top-level `postcss` (pulled in by `@tailwindcss/postcss`, already on a safe `8.5.15`). No stable Next.js release (checked up through `16.3.0-preview.5`, the newest available) has re-vendored a patched `postcss` yet, and npm's suggested "fix" was a nonsensical downgrade to `next@9.3.3` (pre-App-Router).
- **Fix applied:** added an `overrides` block forcing every `postcss` resolution (including Next's nested copy) to `^8.5.15`:
  ```json
  "overrides": { "postcss": "^8.5.15" }
  ```
  This is the standard, low-risk mechanism for silencing a vulnerable version vendored by an otherwise-un-upgradeable dependency — postcss 8.4.31 → 8.5.15 is a same-major, same-API bump.

**npm audit — after:** 0 vulnerabilities (critical/high/moderate/low/info all 0). Verified against the regenerated `package-lock.json`.

**Re-verification after the fix:** `npm ci` succeeds; `tsc --noEmit` passes with zero errors on the full source tree.

---

## 2. apps/react_dashboard

**Unused packages:** none. All of `axios`, `lucide-react`, `react`, `react-dom`, `@vitejs/plugin-react` (used in `vite.config.ts`), `oxlint` (config-driven via `.oxlintrc.json` + the `lint` script), `typescript`, and `vite` have confirmed usage.

**Lockfile:** verified reproducible via `npm ci` (58 packages).

**npm audit:** 0 vulnerabilities, both before and after the other fixes — nothing to do here.

**Re-verification:** the real `npm run build` (`tsc -b && vite build`) succeeds, producing a 253.72 kB bundle.

---

## 3. backend/node_api

**Unused packages:** none. `cors`, `dotenv`, `express`, `firebase-admin`, `jsonwebtoken`, `socket.io` are all imported in `server.js`; `nodemon` is invoked via the `dev` script (not imported in code, but that's the normal usage pattern for a CLI dev-runner).

**Lockfile:** verified reproducible via `npm ci` (318 packages, prod+dev).

**npm audit — before:** 6 moderate (0 critical, 0 high): `@google-cloud/storage`, `firebase-admin`, `gaxios`, `retry-request`, `teeny-request`, `uuid`.
- Investigated each individually rather than trusting the count at face value. Only **one** of the six had an actual titled advisory: `uuid <11.1.1` — "Missing buffer bounds check in v3/v5/v6 when `buf` is provided" ([GHSA-w5hq-g745-h8pq](https://github.com/advisories/GHSA-w5hq-g745-h8pq)). The other five entries had no independent advisory — they were npm audit's *effect propagation* of that single `uuid` finding rippling up one real dependency chain: `uuid` (vulnerable) → `gaxios@6.7.1` / `teeny-request@9.0.0` (embed it) → `@google-cloud/storage@7.21.0` (embeds those) → `firebase-admin@14.1.0` (embeds storage). It was never six separate bugs.
- That whole chain lives inside firebase-admin's **Storage** submodule, which `server.js` never imports (only `firebase-admin/app` and `firebase-admin/messaging` for FCM push) — so even before any fix, the vulnerable code path was present in `node_modules` but not reachable at runtime.
- **Fix applied:** a single override, since `uuid` has a stable, narrow API and a version bump this size (9.x → 11.x) carries very low regression risk even overridden across a dependency's internals:
  ```json
  "overrides": { "uuid": "^11.1.1" }
  ```
  I deliberately did **not** force `gaxios`/`retry-request`/`teeny-request`/`@google-cloud/storage` to newer majors via overrides — each would require jumping outside the semver range `@google-cloud/storage@7.21.0` itself declares (e.g. `gaxios: "^6.0.2"` vs. the fix needing `7.x`), which risks destabilizing internals shared with the FCM push code path we actually depend on, for a moderate-severity issue in a code path we don't use. Not worth the risk.

**npm audit — after:** 0 vulnerabilities. The single `uuid` override resolved the entire chain, confirming it was one root cause, not six.

**Re-verification:** server boots cleanly, and the unauthenticated `POST /api/sos/trigger` still correctly returns 401 — the auth-gating fix from the earlier session is unaffected by this change.

**Minor, non-blocking note:** `npm ci` surfaces three deprecation warnings from transitive packages (`node-domexception@1.0.0`, `uuid@9.0.1` — now overridden — and `glob@10.5.0`, pulled in by `nodemon`'s dev-only chain). None are currently flagged by `npm audit`; noting them here for future cleanup rather than acting now, since dev-only tooling deprecations don't affect the production image.

---

## 4. Flutter / apps/mobile_app

**Important limitation, stated up front:** this sandbox's network egress is allowlisted, and the *entire* Dart/Flutter toolchain distribution surface is outside that allowlist — confirmed directly, not assumed:

| Host | Purpose | Result |
|---|---|---|
| `storage.googleapis.com` | Flutter engine + Dart SDK download | `403 blocked-by-allowlist` |
| `dl.google.com` | Alternate Google SDK mirror | `403 blocked-by-allowlist` |
| `pub.dev` | Package registry / metadata API | `403 blocked-by-allowlist` |
| `pub.dartlang.org` | Legacy pub.dev alias | `403 blocked-by-allowlist` |

`git clone`ing the `flutter/flutter` tool wrapper from GitHub (which *is* reachable) still fails at `flutter --version`, because the tool immediately needs to fetch the prebuilt Dart SDK from `storage.googleapis.com`. There is no local apt/snap package for Flutter or the Dart SDK either. Per the standing policy on blocked domains, I did not attempt to tunnel around this.

**Practical consequence:** `flutter pub get`, `flutter pub outdated`/`upgrade`, `flutter analyze`, and `flutter test` **could not be executed in this environment**, and `pubspec.lock` **could not be regenerated** here — regenerating it safely requires actually resolving the graph against pub.dev, not hand-editing YAML/hashes.

**What I did instead — static analysis, same technique as the npm audits:**
- Grepped every package name against `lib/` and `test/` for real usage sites.
- Confirmed all dev-only tooling is genuinely wired up: `hive_generator`/`build_runner` (via `@HiveType`/`@HiveField` annotations and the generated `lib/models/health_record.g.dart`), `flutter_lints` (via `analysis_options.yaml`), `flutter_launcher_icons` (via `assets/icon.png` + its pubspec config block).
- Found two dependencies with **zero** usage anywhere in the codebase:
  - **`cupertino_icons`** — no `CupertinoIcons.*` reference exists anywhere in `lib/`. This is the default Flutter-template stub dependency that's almost never removed; here it's genuinely dead weight.
  - **`path_provider`** — no direct call to any `path_provider` API (`getApplicationDocumentsDirectory()`, etc.) anywhere in `lib/`. The only Hive setup call is `Hive.initFlutter()` in `main.dart`, which is `hive_flutter`'s own wrapper — `hive_flutter` resolves the storage directory internally via its own transitive `path_provider` dependency. This is corroborated by `pubspec.lock` itself already listing `path_provider_android`, `path_provider_foundation`, `path_provider_linux`, `path_provider_platform_interface`, and `path_provider_windows` as separate entries, meaning the platform-specific implementations are being pulled in regardless of our direct top-level declaration.
- **Removed both** from `pubspec.yaml`.
- All thirteen remaining dependencies (`hive`, `hive_flutter`, `dio`, `shared_preferences`, `go_router`, `provider`, `flutter_secure_storage`, `image_picker`, `uuid`, `geolocator`, `url_launcher`, `speech_to_text`, `flutter_tts`) have confirmed real usage — several with in-line comments in `pubspec.yaml` explaining *why* they exist (e.g. `flutter_secure_storage` replacing plaintext `shared_preferences` for JWT/encryption keys — a prior compliance fix), which I left untouched.

**What is NOT done, and needs to happen on a machine with real Flutter/pub.dev access** (this is a to-do for you, not a claim that it's already been verified):
```bash
cd apps/mobile_app
flutter pub get        # will reconcile pubspec.lock: drop cupertino_icons,
                        # and drop path_provider* if nothing else needs it transitively
flutter pub outdated    # review for "update compatible packages" — not checked here,
                        # since pub.dev metadata was unreachable
flutter analyze
flutter test
```
I have not claimed these pass — they have not been run. Please run them and let me know if `flutter analyze` flags anything from the `cupertino_icons`/`path_provider` removal (I'd be surprised, given the grep evidence, but it's unverified).

---

## Summary of file changes

| File | Change |
|---|---|
| `apps/web_portal/package.json` | added `overrides.postcss = ^8.5.15` |
| `apps/web_portal/package-lock.json` | regenerated (verified via clean `npm ci` + `npm audit`) |
| `backend/node_api/package.json` | added `overrides.uuid = ^11.1.1` |
| `backend/node_api/package-lock.json` | regenerated (verified via clean `npm ci` + `npm audit`) |
| `apps/mobile_app/pubspec.yaml` | removed unused `cupertino_icons`, `path_provider` |
| `apps/mobile_app/pubspec.lock` | **not touched** — needs `flutter pub get` on a machine with pub.dev access |
| `apps/react_dashboard/*` | no changes — audit was already clean |

## Vulnerability totals

| Project | Critical/High before | Critical/High after | Moderate before | Moderate after |
|---|---|---|---|---|
| web_portal | 0 | 0 | 2 | **0** |
| react_dashboard | 0 | 0 | 0 | 0 |
| node_api | 0 | 0 | 6 | **0** |

No Critical or High severity findings existed in any of the three npm projects at any point — the audit's "resolve Critical/High" instruction had nothing to act on there, but both existing Moderate findings were tracked down to root cause and closed anyway rather than left as "not required."

Two housekeeping leftovers I could not clean up due to this sandbox's network-mount permissions (harmless, cosmetic only): `apps/web_portal/package-lock.json.old` and `backend/node_api/package-lock.json.old` — stray backup copies from the lockfile regeneration that the mount refused to let me delete from the Linux side. Safe to delete manually from Windows Explorer whenever convenient.
