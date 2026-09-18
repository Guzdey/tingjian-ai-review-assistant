# Public data directory

This directory contains no raw Amazon Reviews 2023 export.

- `demo_derived.json` is a small, **fully synthetic** offline fixture. Every
  quote and Chinese summary was written for interface and API testing; none is
  a customer statement or a claim about a real earphone.
- `manifest.json` describes the public fixture and its coverage.

Real source files, cleaned review text, private `parent_asin` mappings,
embeddings, and model caches belong under `D:\CodexData\tingjian-ai` and are
excluded from Git. Replace the fixture only with a separately generated file
whose provenance and redistribution rights have been checked, and use
`source_kind: "derived_dataset"` for such evidence.
