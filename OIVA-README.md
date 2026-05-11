## About this note
In addition to README.md and the standard Docs set, this file describes Oiva-specific customizations for observing the OTel Demo App with Honeycomb.

## Getting started
1. Clone the repo
2. `cd` into the project root (the one that contains `compose.yaml`)
3. Create `.env.secrets` and add your API key (see below)
4. `make start`


## Secrets
Create this file and add your secrets:
```bash
# .env.secrets

# Honeycomb ingest key
HONEYCOMB_API_KEY=hcaik_01krcjhcvkmt4q...
```