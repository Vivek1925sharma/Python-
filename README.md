# GenAI Payments Demo

A lightweight payments API with a built-in fraud scoring workflow and a generative-AI style insight endpoint.

## Features
- `/pay` endpoint that scores fraud risk and returns an approval, review, or block decision.
- `/ai-insights/{customer_id}` endpoint that summarizes customer activity in natural language.
- In-memory velocity tracking for the last 24 hours.

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn payment_app.app:app --reload
```

## Example request

```bash
curl -X POST http://localhost:8000/pay \
  -H 'Content-Type: application/json' \
  -d '{
    "amount": 850,
    "currency": "USD",
    "customer_id": "cust_123",
    "merchant_id": "mrc_789",
    "ip_country": "US",
    "billing_country": "US",
    "device_id": "device_456",
    "card_bin": "414720"
  }'
```
