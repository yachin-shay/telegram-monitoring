# 02 — Foundation and Packaging

## FND-01: Establish the project skeleton

**Depends on:** none.

Create a `src/` Python package, `tests/` hierarchy, `docs/adr/`, migration
directory, example configuration, and command entry point. Configure a modern
build backend, locked dependencies, Python 3.12 minimum, formatting, linting,
static type checks, and pytest.

Keep runtime dependencies small. Likely categories are CLI rendering, typed
configuration, YAML round-trip editing, async utilities, and migration support.
Use Python's `sqlite3`, logging, hashing, and IPC primitives unless a measured
need justifies another dependency.

**Tests:** package imports; CLI `--help`; empty test suite runs; type/lint jobs.

**Done when:** a clean checkout can create an environment, install the package,
and run all checks from documented commands.

## FND-02: Make `libtdjson` reproducible

**Depends on:** FND-01.

Pin a TDLib version and record its source checksum. Provide:

- a developer build script using official TDLib build instructions;
- runtime discovery through explicit config, environment override, then
  platform library lookup;
- a startup check that reports TDLib version and ABI failure clearly;
- a container build stage compiling `tdjson`;
- a compatibility document mapping supported application and TDLib versions.

Do not silently download native binaries during application startup. Release
artifacts must record source, version, checksum, compiler, and target platform.

**Tests:** load a known library; helpful failure for missing/wrong architecture;
version interrogation; container smoke test.

**Done when:** CI can build or obtain the pinned library reproducibly and the
Python adapter loads it on the first supported platform.

## FND-03: Define stable domain contracts

**Depends on:** FND-01.

Define immutable domain objects for account, chat, target policy, message
identity, message revision, deletion, user observation, membership observation,
file reference, job, and collection event. Represent Telegram int64 identifiers
without lossy conversion. Include schema version and observed timestamps.

Model raw TDLib objects as an attached payload, not the domain interface itself.
Define canonical serialization and hashing used to detect changed observations.

**Tests:** round trips; int64 extremes; known/empty/unknown states; stable hashes;
forward-compatible unknown fields.

**Done when:** collection, storage, and plugins can agree on contracts without
importing TDLib-specific classes.

## FND-04: Continuous integration

**Depends on:** FND-01, FND-02.

Run formatting verification, linting, type checking, unit tests, migration
tests, and a native adapter smoke test. Cache native compilation safely. Add
dependency and secret scanning, but avoid checks that upload collected fixtures.

**Done when:** every merge receives deterministic pass/fail results and release
builds embed exact Python and TDLib versions.

