# Lightweight real-review sampling

`hf_range_sample.py` is an optional private-data helper for the approximately
22 GB `Electronics.jsonl` file in Amazon Reviews 2023. It does not download the
whole source file.

Before using it, manually confirm exactly two comparable wireless-earbud
`parent_asin` values and place the private mapping outside Git, for example at
`D:\CodexData\tingjian-ai\private\selection.json`. Use
`selection.example.json` as the schema reference.

```powershell
python pipeline/hf_range_sample.py `
  --selection D:\CodexData\tingjian-ai\private\selection.json `
  --max-per-product 24 `
  --max-transfer-mb 40
```

Safety boundaries:

- every request must return HTTP 206 and an exact `Content-Range`;
- one request is capped at 2 MiB and one run at 50 MiB;
- an oversized or non-range response is rejected before an unbounded read;
- raw chunks are never persisted;
- user/reviewer IDs and image fields are never retained;
- outputs and the private product mapping remain under the D-drive data root.

The method is deterministic but not statistically representative. The report
records bytes transferred, rows parsed, counts per product, and whether the
requested sample size was reached. A failed target must be reported as
insufficient data, not silently treated as a complete sample.

The source dataset's current terms still apply. Do not commit raw reviews,
private product mappings, model-response caches, or embeddings to this public
repository.
