# search

BM25 search over a sample of [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb), indexed in Vespa (local Docker or Vespa Cloud), with a small Google-style web UI.

## Setup

```bash
source .venv/bin/activate          # or: uv sync
cp .env.example .env               # then fill in the values
```

`.env` (git-ignored) holds all settings. `config.py` has the shared helpers: `load_env()` and `connect_vespa()`.

| Variable | Purpose |
| --- | --- |
| `HF_TOKEN` | Hugging Face token for streaming the dataset |
| `NUM_DOCS` | How many FineWeb documents to feed (default 100000) |
| `VESPA_MODE` | `local` (Docker) or `cloud` (Vespa Cloud) |
| `VESPA_LOCAL_URL`, `VESPA_LOCAL_PORT` | Local Vespa address (default `http://localhost`, `8080`) |
| `VESPA_CONTAINER_MEMORY_GB` | Memory limit for the local container |
| `VESPA_CLOUD_ENDPOINT` | mTLS endpoint of your Vespa Cloud app |
| `VESPA_CERT_DIR` | Folder with `data-plane-public-cert.pem` and `data-plane-private-key.pem` (created by `vespa auth cert`) |

## Local mode (Docker)

1. Start Docker Desktop. Under Settings > Resources, give it at least 8 GB of memory.
2. Set `VESPA_MODE=local` in `.env`.
3. In `tutorial.ipynb`, run the cells in order: dataset, schema, deploy, connect, feed.

The deploy cell starts the `vespaengine/vespa` container and mounts named volumes (`vespa-var`, `vespa-logs`), so the index survives container restarts. The first start takes a minute or two. Stop and start it with `docker stop fineweb` and `docker start fineweb`.

Safe size on a 16 GB laptop: 100k to 300k documents comfortably, about 1M at most.

## Vespa Cloud mode

Set `VESPA_MODE=cloud` and fill in `VESPA_CLOUD_ENDPOINT` and `VESPA_CERT_DIR`. The deploy cell then deploys to Vespa Cloud instead. Dev instances expire after about 14 days of inactivity; redeploy and re-feed if the connection fails.

## Notebook (`tutorial.ipynb`)

- First time: run all cells. The feed cell streams `NUM_DOCS` documents from Hugging Face straight into Vespa without holding them in memory. Feeding is idempotent, so re-running overwrites rather than duplicates.
- After a restart the app and data are still there. Skip the deploy and feed cells, run the first cell (it loads `.env`) and the connect cell, then run the queries.

## Search UI

```bash
python ui.py
```

Open http://localhost:8000. It connects to Vespa according to `VESPA_MODE`. Hovering a result shows its full text on the right (windows at least 1250px wide), and clicking the logo goes back to the home page.

## SafeSearch

Each document gets an `adult` flag when it is fed, computed by `safety.py` (a weighted keyword score plus URL hints; tune `THRESHOLD` and the term lists there). The UI has a SafeSearch toggle, on by default, that adds `and adult = false` to the query. It is remembered in the URL and in the browser.

It is a heuristic: it catches blatant pages but will miss some and occasionally flag health or news pages. Changing the rules means recomputing the flag, which needs a re-feed or a partial update of the `adult` field. The `adult` field must exist in the deployed schema before feeding.

## Notes

- Never commit `.env` or the cert/key files.
