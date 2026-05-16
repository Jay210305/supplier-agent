# Phase 5 — n8n Workflow Automation

## Objective
Configure and automate the procurement workflow using n8n to connect email ingestion, entity extraction, budget checking, PO generation, and human approval steps. This phase focuses on importing the pre-built workflow, configuring credentials and endpoints, and testing the end-to-end automation.

## Tasks

### 1. Import and Configure n8n Workflow

Import the procurement workflow into n8n:

- Access n8n UI at `http://localhost:5678`
- Navigate to Workflows → Import
- Select `n8n/workflows/procurement_flow.json`
- Verify all nodes are properly imported
- Activate the workflow after configuration

### 2. Configure Email Trigger (IMAP)

Set up the Gmail IMAP trigger node:

- Create IMAP credentials in n8n:
  - Host: `imap.gmail.com`
  - Port: `993`
  - User: `compras@mype.com.pe` (from `.env`)
  - Password: App-specific password (from `.env`)
  - Enable SSL/TLS
- Configure trigger settings:
  - Check for new emails every 1 minute
  - Only unread emails
  - Move processed emails to a label/folder (optional)
  - Download attachments (if needed for future phases)

### 3. Configure HTML-to-Text Node

Verify the HTML-to-Text conversion node:

- Ensures email body is plain text for processing
- No configuration typically needed beyond default settings
- Test with sample HTML email to verify conversion

### 4. Configure HTTP Request Node (Entity Extraction)

Set up the call to FastAPI procurement parser:

- Method: POST
- URL: `http://fastapi:8000/procurement/parse` (use internal Docker hostname)
- Headers:
  - Content-Type: application/json
- Body:
  ```json
  {
    "email_body": "{{ $('HTML-to-Text').item.json.text }}"
  }
  ```
- Enable JSON parsing for response
- Set timeout to 60 seconds (Ollama can be slow)
- Add error handling for failed requests

### 5. Configure IF Node (Budget Check)

Set up conditional logic for budget exceeded:

- Condition: `{{ $('HTTP Request').item.json.budget_exceeded === true }}`
- True path: Budget alert workflow
- False path: Continue to PO generation
- Test with sample data exceeding and not exceeding budget

### 6. Configure Budget Alert Path

Set up email alert for budget exceeded:

- Email Send Node:
  - To: Manager/compras@mype.com.pe (configurable)
  - Subject: "Budget Alert: Procurement Request {{ $json.request_id }} Exceeds Budget"
  - Body: Include details from the procurement request:
    - Request ID
    - Items and quantities
    - Estimated cost
    - Budget limit
    - Recommendation to review manually
- Optionally add Slack notification if configured

### 7. Configure HTTP Request Node (PO Generation)

Set up the call to generate purchase order:

- Method: POST
- URL: `http://fastapi:8000/orders/generate`
- Headers:
  - Content-Type: application/json
- Body:
  ```json
  {
    "request_id": "{{ $('HTTP Request').item.json.request_id }}",
    "items": {{ $('HTTP Request').item.json.items }},
    "constraints": {{ $('HTTP Request').item.json.constraints }},
    "priority": "{{ $('HTTP Request').item.json.priority }}"
  }
  ```
- Enable JSON parsing for response
- Set timeout to 30 seconds

### 8. Configure Webhook Node (Human Approval)

Set up the approval wait point:

- Webhook path: `/approval/{{ $node["HTTP Request"].json.request_id }}`
- HTTP Method: GET
- Response Mode: On Wait
- Response Data:
  ```json
  {
    "message": "Waiting for approval...",
    "options": ["Approve", "Reject", "Needs Review"]
  }
  ```
- Configure security (optional): Basic auth or token validation
- Set timeout for how long to wait (e.g., 24 hours)

### 9. Configure HTTP Request Node (Approval Update)

Set up the call to update PO status after approval:

- Method: PATCH
- URL: `http://fastapi:8000/orders/{{ $json.request_id }}/approve`
- Headers:
  - Content-Type: application/json
- Body:
  ```json
  {
    "status": "{{ $json.approval_decision }}",
    "approved_by": "{{ $json.approved_by || 'n8n_workflow' }}",
    "approved_at": "{{ $now }}"
  }
  ```
- Handle different approval outcomes:
  - Approve: Continue to send PO
  - Reject: Cancel workflow, notify requester
  - Needs Review: Escalate to manager, wait for manual intervention

### 10. Configure Final Notification Nodes

Set up success/failure notifications:

- Email Send Node (Success):
  - To: Requester (extracted from email or default)
  - Subject: "Purchase Order Approved: {{ $json.request_id }}"
  - Attach: Generated PO PDF (from previous step)
  - Body: Confirmation with PO details and next steps
  
- Email Send Node (Failure/Rejection):
  - To: Requester
  - Subject: "Purchase Order Rejected: {{ $json.request_id }}"
  - Body: Reason for rejection and next steps

### 11. Configure Error Handling

Set up workflow error management:

- Add Error Trigger node at workflow level
- Configure to notify administrators via email/Slack
- Include error details and workflow execution data
- Optionally retry failed steps with exponential backoff

### 12. Test the Complete Workflow

Validate the automation with test scenarios:

Test Case 1: Normal Procurement Flow
1. Send test email: "Necesito 10 laptops antes del lunes, presupuesto 30000 soles."
2. Verify email triggers workflow
3. Check entity extraction returns valid JSON
4. Confirm budget check passes (under 30k)
5. Validate PO generation is triggered
6. Verify approval webhook waits for input
7. Test approval via webhook URL
8. Confirm final notification sent with PDF

Test Case 2: Budget Exceeded Flow
1. Send test email: "Necesito 100 laptops antes del lunes, presupuesto 30000 soles."
2. Verify budget exceeds threshold
3. Confirm workflow branches to alert path
4. Check alert email is sent to manager
5. Verify workflow terminates without PO generation

Test Case 3: Ollama Failure Handling
1. Temporarily stop Ollama service
2. Send test email
3. Verify workflow handles service unavailability
4. Confirm appropriate error routing
5. Check administrator notification

## Deliverables

By the end of this phase, the project must include:

- Imported and activated `n8n/workflows/procurement_flow.json` in n8n UI
- Configured IMAP credentials for Gmail access
- Configured HTTP nodes pointing to correct FastAPI endpoints
- Functional budget alert pathway
- Human-in-the-loop approval webhook
- Success/failure notification pathways
- Error handling and logging configuration
- Documented test procedures for validation

## Technical Expectations

### n8n Configuration
- Use Docker internal hostnames for service communication (`fastapi:8000`)
- External URLs only for webhooks accessed from outside Docker (`localhost:5678`)
- Secure credential management (never hardcode passwords in workflow JSON)
- Proper node naming and organization for maintainability
- Consistent data flow between nodes using expression language

### Workflow Design
- Modular design with clear separation of concerns
- Adequate error handling at each step
- Timeout configurations appropriate for each service
- Retry logic for transient failures where appropriate
- Clear approval/rejection paths with appropriate notifications

### Security Considerations
- Credentials stored in n8n credential store, not in workflow JSON
- Webhook URLs should be difficult to guess (use request IDs)
- Consider implementing token validation for webhook endpoints
- Sanitize inputs where user data flows into emails or notifications

### Performance & Reliability
- Reasonable timeouts for each service call (email: 60s, Ollama: 120s, FastAPI: 30s)
- Concurrency settings appropriate for expected load
- Dead letter queue or retry mechanisms for failed executions
- Workflow execution history retention for auditing

## Success Criteria

1. `docker compose up -d` starts all services including n8n
2. n8n UI accessible at `http://localhost:5678`
3. Procurement workflow imported and visible in workflows list
4. IMAP trigger successfully connects to Gmail test account
5. Entity extraction HTTP call returns valid JSON for test emails
6. Budget check correctly routes exceeded vs normal requests
7. Approval webhook generates unique URLs and waits for input
8. Approval/rejection decisions properly update PO status via FastAPI
9. Success and failure notifications sent appropriately
10. Error handling captures and reports workflow failures
11. End-to-end test passes with sample procurement email
12. Budget alert test correctly triggers notification path
13. Manual testing of approval webhook confirms functionality

## Troubleshooting Guide

### Common Issues
- **IMAP Connection Failures**: Verify app password, SSL settings, and that 2FA is enabled on Gmail account
- **HTTP Request Failures**: Check service availability, correct internal hostnames, and port mappings
- **JSON Parsing Errors**: Ensure FastAPI endpoints return properly formatted JSON
- **Webhook Timeouts**: Verify n8n can access the webhook URL and service is responsive
- **Permission Errors**: Check n8n user has write access to workflow directory if saving executions

### Debugging Steps
1. Check n8n execution logs for failed nodes
2. Verify individual service endpoints work outside n8n (curl tests)
3. Test credentials independently (IMAP login, API access)
4. Use n8n's built-in debugging tools to inspect data at each node
5. Review Docker container logs for service-specific issues

## Next Steps After Phase 5

Once the workflow automation is functional, proceed to:
- Phase 6: Integrate scoring algorithm into the procurement flow
- Phase 7: Enhance PDF generation with dynamic templates and branding
- Phase 8: Add advanced features like multi-currency support and contract management
- Phase 9: Production hardening, monitoring, and alerting setup