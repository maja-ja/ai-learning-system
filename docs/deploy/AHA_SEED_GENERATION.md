# Aha Seed Generation (10k)

Use the batch generator:

`kadusella/scripts/generate_aha_seed_batch.py`

## 1) Prepare profile UUID list

Create a text file with one existing `profiles.id` UUID per line, for example:

`tmp/profile_ids.txt`

## 2) Run first 10,000 rows

```bash
python3 kadusella/scripts/generate_aha_seed_batch.py \
  --api-base http://127.0.0.1:8000 \
  --tenant-id <tenant-uuid> \
  --profile-ids-file tmp/profile_ids.txt \
  --count 10000 \
  --batch-size 200 \
  --retry 3 \
  --delay-sec 0.1 \
  --checkpoint .tmp/aha_seed_checkpoint.json
```

## 3) Resume after interruption

Run the same command again. It resumes from checkpoint cursor.

## 4) Notes

- Use real profile UUIDs for FK-safe inserts.
- Start with `--count 200` for a smoke test.
- If API has high latency, reduce `--batch-size` to 100.
