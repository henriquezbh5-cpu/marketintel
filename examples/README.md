# Examples

Quick-start clients and recipes. Pick whichever matches your tooling.

| File | Use case |
|---|---|
| [`python_client.py`](python_client.py) | Minimal Python client: API key auth, pagination, news filters |
| [`curl_examples.sh`](curl_examples.sh) | Bash + cURL one-liners — good for smoke tests |
| [`postman_collection.json`](postman_collection.json) | Importable Postman / Insomnia collection |

## Issuing yourself an API key

After bootstrapping the stack:

```bash
docker compose exec web python manage.py createsuperuser
docker compose exec web python scripts/issue_api_key.py <username> --scope read
```

Save the printed key — it is shown once, only the SHA-256 digest is stored.

## Authentication

All requests carry `X-API-Key: <raw_key>`. The server resolves it to the
underlying user, scopes the throttle bucket per key, and updates `last_used_at`
asynchronously.
