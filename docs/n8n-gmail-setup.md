# Gmail + n8n — live procurement test

End-to-end: **Gmail (IMAP)** → n8n → **FastAPI** (Ollama + ScraperAPI) → **PO PDF** → approval email.

## 1. Prerequisites

```powershell
docker compose up -d
docker compose ps   # postgres, ollama, fastapi, n8n healthy
curl http://localhost:8000/health
```

In `.env`:

- `SCRAPERAPI_API_KEY=...`
- `IMAP_USER=` your Gmail address
- `IMAP_PASSWORD=` [App Password](https://myaccount.google.com/apppasswords) (16 chars, not your normal password)
- `N8N_ENCRYPTION_KEY=` random 32+ chars (in `docker-compose.yml` or `.env` if you wire it)

Enable marketplace sources (once):

```powershell
docker exec fastapi python -m db.seed_catalog_sources
# PATCH each ScraperAPI source is_enabled: true (UI http://localhost:3000/sources or API)
```

## 2. Gmail App Password

1. Google Account → **Security** → **2-Step Verification** ON  
2. **App passwords** → Mail → Other → name `supplier-agent`  
3. Copy the 16-character password into `.env` as `IMAP_PASSWORD`  
4. Use the **same** Gmail address for `IMAP_USER` and for n8n SMTP credentials below  

## 3. n8n credentials (UI)

Open **http://localhost:5678**

### IMAP (trigger)

1. **Credentials** → **Add credential** → **IMAP**  
2. User: your Gmail  
3. Password: App Password  
4. Host: `imap.gmail.com`  
5. Port: `993`  
6. SSL/TLS: ON  

### SMTP (send)

1. **Add credential** → **SMTP**  
2. User / Password: same Gmail + App Password  
3. Host: `smtp.gmail.com`  
4. Port: `465` (SSL) or `587` (STARTTLS — match what n8n offers)  
5. From address: your Gmail  

## 4. Import workflow

1. **Workflows** → **Import from file**  
2. Select `n8n/workflows/procurement_flow.json`  
3. Open **Procurement Flow**  
4. On each node with a warning, assign credentials:  
   - **Email Trigger (IMAP)** → Gmail IMAP  
   - **Admin Alert Parse Error**, **Budget Alert Email**, **Send PO Draft Email**, **Send PO Approved Email**, etc. → Gmail SMTP  
5. Replace placeholder `compras@mype.com.pe` in email nodes with your Gmail if needed  

## 5. Activate

Toggle **Active** (top right). The IMAP trigger polls **UNSEEN** mail in INBOX.

## 6. Fire test

Send an email **to the same Gmail inbox** you configured (or from another account):

```
Subject: Pedido REQ-2026-N8N-001

Buenos días,

Necesitamos 10 PlayStation 5 para la oficina antes del lunes.
Presupuesto máximo: 30000 soles.
Prioridad alta.

Saludos,
Compras MYPE
```

Use a **new** `request_id` in the body if you re-test (Ollama may reuse `REQ-2026-001` otherwise). The workflow uses Ollama’s extracted `request_id` for the PO.

### What should happen

| Step | Node | Result |
|------|------|--------|
| 1 | Email Trigger | Picks up UNSEEN message |
| 2 | HTML-to-Text | Plain text for LLM |
| 3 | Parse Procurement | `include_external: true` → ScraperAPI snapshot |
| 4 | Budget Exceeded? | **False** if marketplace snapshot exists (even when local seed has no match) |
| 5 | Generate PO | Same as terminal: WLC + Ollama + PDF + appendix |
| 6 | Send PO Draft Email | Summary + `pdf_path` |
| 7 | Wait for Approval | Pauses — open execution in n8n |

### Approve

1. **Executions** → running workflow → **Wait for Approval**  
2. Copy **resume URL** (or use links in node output JSON)  
3. Open in browser: append `?decision=Approve&approved_by=you@gmail.com`  
4. Flow continues → **Update PO Status** → **Send PO Approved Email**

### Get the PDF

```powershell
docker cp fastapi:/app/generated_pos ./po-out
```

Path is in **Generate PO** output (`pdf_path`).

## 7. Troubleshooting

| Issue | Fix |
|-------|-----|
| IMAP not triggering | Mail must be **unread**; trigger uses `UNSEEN`. Mark unread or send a new mail. |
| Parse error | `docker compose logs -f ollama fastapi` — wait for model pull / Ollama healthy |
| Stops at budget alert | Re-import updated workflow; backend now allows continue when `external_market_snapshot` is non-empty |
| Generate 409 | Duplicate `request_id` — use new email wording or delete PO row |
| Generate 422 no suppliers | Enable ScraperAPI sources; check `SCRAPERAPI_API_KEY` |
| SMTP failed | App Password, port 465/587, “less secure” not used — App Password required |
| n8n can’t reach API | URLs must be `http://fastapi:8000/...` (Docker network), not `localhost` |

## 8. Flow diagram

```
Gmail INBOX (IMAP)
    → Parse (/procurement/parse, ScraperAPI)
    → [budget block only if no marketplace data]
    → Generate PO (/orders/generate + snapshot)
    → Email: draft summary
    → Wait (webhook approve)
    → PATCH approve
    → Email: approved
```

Score/Justification nodes remain in the file for manual experiments; the **active path** goes straight from budget check to **Generate PO** (matches your successful terminal test).
