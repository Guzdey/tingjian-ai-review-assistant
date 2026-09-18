# Data pipeline

This directory contains the reproducible Tingjian review-data pipeline. It intentionally excludes the Amazon Reviews 2023 archive, full review exports, reviewer identifiers, private product mappings, embeddings, model responses, and credentials.

## Storage boundary

Keep large or regenerable files outside this repository:

```text
D:\CodexData\tingjian-ai\
|-- private\          # private alias-to-parent_asin mapping
|-- raw\              # optional source archives / JSONL
|-- work\             # bounded samples and cleaned reviews
|-- processed\        # private derived evidence and coverage reports
`-- cache\            # private model-response cache
```

Only deliberately public synthetic fallback data belongs in `data/`. `data/demo_derived.json` is fabricated fixture content for running the product without network/model access. It is not Amazon review data and must never be reported as user research, model evaluation, or evidence about a real product.

## Stable contract

Public APIs and derived files use exactly two aliases: `demo-tws-a` and `demo-tws-b`. Private `parent_asin` values never enter Git. Supported aspects are `noise_cancellation`, `call_quality`, `connection`, `comfort`, `battery`, and `sound_quality`; stance is `support`, `oppose`, or `mixed`.

## Lightweight network flow

1. Run `hf_range_discover.py` to discover likely earbud candidates from bounded byte ranges.
2. Manually verify product type, comparable positioning, review ownership, and usable volume.
3. Copy `selection.example.json` to `D:\CodexData\tingjian-ai\private\selection.json` and replace both placeholders.
4. Run `hf_range_sample.py` to retain only the two selected products.
5. Run `clean_reviews.py` to remove empty, duplicated, and low-information rows.
6. Run `build_rule_evidence.py` to create a deterministic six-aspect baseline.
7. Load `D:\CodexData\tingjian-ai\processed\private_derived.json` through `TINGJIAN_DEMO_DATA_PATH`.

`hf_range_discover.py` and `hf_range_sample.py` require valid HTTP 206 responses, cap a request at 2 MiB and a run at 50 MiB, and never persist raw chunks. See [RANGE_SAMPLING.md](RANGE_SAMPLING.md). Range sampling is not exhaustive or statistically representative.

Example after manually verifying exactly two products:

```powershell
python pipeline/hf_range_sample.py `
  --selection D:\CodexData\tingjian-ai\private\selection.json `
  --max-per-product 60 `
  --max-transfer-mb 50

python pipeline/clean_reviews.py `
  --input D:\CodexData\tingjian-ai\work\selected_reviews_range.jsonl

python pipeline/build_rule_evidence.py
```

## Full local-file flow

If source files were obtained separately under their current terms, `sample_products.py discover` scans metadata and reviews for candidates, and `sample_products.py extract` reservoir-samples the two manually selected products. This path never downloads data itself.

## Privacy and interpretation

- `user_id`, reviewer profiles, names, contact details, and image fields are not retained;
- English evidence is truncated to a necessary short excerpt;
- `verified_purchase` and `helpful_vote` are ranking inputs only, not authenticity proof;
- rule-derived aspect and stance labels require manual audit;
- sparse or conflicting evidence must remain “insufficient” or “uncertain”.

## Validate the public fixture and range safeguards

```powershell
python pipeline/validate_public_data.py
python -m unittest tests.test_public_demo_data
python -m pytest tests/test_range_sampler.py -q
```
