# Interview AI — Frontend (Amplify)

React app for the Interview AI dashboard. Connects to API Gateway (orchestrator).

## Setup

1. Copy env and set your API URL (from Terraform):

   ```bash
   cp .env.example .env
   # Edit .env: set VITE_API_URL to your API Gateway URL (terraform output api_gateway_url)
   ```

2. Install and run:

   ```bash
   npm install
   npm run dev
   ```

   Open http://localhost:3000. Use "Generate brief" with a company name.

## Build for Amplify

```bash
npm run build
```

Deploy the `dist/` folder via AWS Amplify (Console: connect repo and set build output to `dist`, or use Amplify CLI `amplify publish`).

## Architecture

User → this app → API Gateway → Orchestrator Lambda → Brief Generator / Document Processor.
