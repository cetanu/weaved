# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0](https://github.com/cetanu/weaved/compare/v0.1.0...v0.2.0) - 2026-11-23

### Added

- [**breaking**] replace concat_lists with MergeFlag and add TYPESAFE
- support variadic dictionary inputs in merge()

### CI

- *(release)* add release-plz, GitHub releases, and conventional commit checks
- log result files in ASV history workflow
- focus ASV gate on high-signal workloads
- limit ASV gate to native timings

### Fixed

- preserve custom key hashing on bulk updates
- handle late containers in bulk merges

### Performance

- use shorter prefix for mixed medium merges
- use raw scan for smaller wide merges
- use raw scan for medium wide merges
- skip scalar update scan for tiny merges
- scan copied dictionaries without wrapping scalar entries
- scan copied lists without scalar wrapper values
- skip key checks for nested small merges
- scan bulk merge values with CPython dict iteration
- bulk update small scalar-only merges
- bulk update large scalar-only merges

### Styling

- *(bench)* format performance report generator
- format scan optimization and record subtree benchmarks
