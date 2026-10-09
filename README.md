# search

BM25 search over a sample of [FineWeb](https://huggingface.co/datasets/HuggingFaceFW/fineweb), indexed in Vespa Cloud, with a small Google-style web UI.

## Setup

```bash
source .venv/bin/activate          # or: uv sync
cp .env.example .env               # then fill in the values
```

`.env` (git-ignored) holds:

| Variable | Purpose |
| --- | --- |
| `HF_TOKEN` | Hugging Face token for streaming the dataset |
| `VESPA_ENDPOINT` | mTLS endpoint of your deployed Vespa Cloud app |
| `VESPA_CERT_DIR` | Folder with `data-plane-public-cert.pem` and `data-plane-private-key.pem` (created by `vespa auth cert`) |

## Notebook (`tutorial.ipynb`)

First time: run all cells to define the schema, deploy, and feed 1,000 documents.

After a kernel restart the app and data are still in Vespa Cloud, so skip the deploy and feed cells. Run the `.env` loader cell and the connection cell, which reconnects using `VESPA_ENDPOINT` and `VESPA_CERT_DIR`, then run the queries.

## Search UI

```bash
python ui.py
```

Open http://localhost:8000. The server proxies queries to Vespa, since the endpoint needs mTLS and the browser can't call it directly.

## Notes

- Never commit `.env` or the cert/key files.
- Vespa Cloud dev instances expire after about 14 days of inactivity. If the connection fails, redeploy and re-feed.
