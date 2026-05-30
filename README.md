# pear-refurb-notifier

Generic encrypted notification sender.

This public repository is the notifier half of a two-repository monitoring setup:

- `pear-refurb-watcher`: fetches pages, detects changes, owns encrypted state.
- `pear-refurb-notifier`: receives encrypted dispatch payloads and sends email.

The notifier does not fetch websites, read the Secret Gist, or keep state.

## Secrets

Configure these GitHub Secrets:

```text
PAYLOAD_ENCRYPTION_KEY
RESEND_API_KEY
MAIL_FROM
MAIL_TO
```

`PAYLOAD_ENCRYPTION_KEY` must match the value configured in the watcher repository.

Generate a Fernet key with:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Do not commit keys, email addresses, API keys, or real notification examples.

## Dispatch Payload

The notifier expects `repository_dispatch` events with encrypted payload only. It is intentionally not manually runnable through `workflow_dispatch`.

```json
{
  "event_type": "notify",
  "client_payload": {
    "encrypted": true,
    "ciphertext": "..."
  }
}
```

The plaintext payload exists only in memory after decryption. It is not logged.

## Email Delivery

Email is sent through the Resend API. `MAIL_FROM` must be usable by the configured Resend account. A verified sending domain is recommended for stable operation.

Resend quota, rate limits, API key validity, and domain verification status can cause send failures. If sending fails, the workflow fails.

The decrypted `event_id` is sent as the Resend `Idempotency-Key` to reduce duplicate sends during retries or manual reruns.

On Resend errors, the workflow logs only a generic error and HTTP status code. It does not log recipients, message body, subject content, or Resend response body.

## Public Repository Rules

Do not commit:

- real notification content
- recipient addresses
- API keys or encryption keys
- monitored URLs
- site names
- HTML or page text fixtures from real targets

## License

MIT
