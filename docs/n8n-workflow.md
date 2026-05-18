# n8n workflow

## Files

- `n8n/workflows/procurement_flow.json` — main Gmail → PO flow  
- `docs/n8n-gmail-setup.md` — **Gmail App Password + credential setup + fire test**

## Quick start

```powershell
docker compose up -d
```

1. Import `procurement_flow.json` at http://localhost:5678  
2. Configure Gmail IMAP + SMTP credentials (see [n8n-gmail-setup.md](./n8n-gmail-setup.md))  
3. Activate workflow  
4. Send procurement email to the monitored inbox  

## Active path (2026)

```
IMAP → HTML-to-Text → Parse (include_external)
  → Budget? (only blocks if no marketplace snapshot)
  → Generate PO (full parse payload + external_market_snapshot)
  → Send PO Draft Email → Wait for Approval → Approve → Emails
```

Internal API hostnames: `http://fastapi:8000` (never `localhost` from n8n container).
