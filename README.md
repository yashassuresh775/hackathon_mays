# Hackathon Mays – Company Research Service

Service to help interviewers ask better questions: given a company name, retrieve information from the internet and store relevant article URLs for later use (e.g. feeding into Bedrock).

## Phase 1: Web Scraping & S3 Storage

- **Input:** Company name  
- **Behaviour:** Search the web for the company, collect relevant article URLs, and store them in S3.  
- **Deployment:** AWS CDK with **CloudFront** in front of the API and S3.

### Architecture

- **API Gateway** (REST) – trigger scrape and list stored results  
- **Lambda** – runs the scraper (SerpAPI search), writes/reads from S3  
- **S3** – stores `research/{companyKey}/urls.json` with article URLs and metadata  
- **CloudFront** – single entry point: default behaviour to API, `/research/*` to S3

### Prerequisites

- Node.js 18+
- AWS CLI configured (`aws configure`)
- AWS CDK CLI: `npm install -g aws-cdk`

### Search API key (SerpAPI)

The scraper uses [SerpAPI](https://serpapi.com/) (free tier available). Provide your API key in one of two ways:

**Option A – SSM Parameter Store (recommended)**

1. Create a parameter (e.g. SecureString) with your SerpAPI key:
   ```bash
   aws ssm put-parameter --name "/company-research/serpapi-key" --value "YOUR_SERPAPI_KEY" --type SecureString
   ```
2. Deploy with the parameter name:
   ```bash
   npx cdk deploy -c serpapiKeyParam=/company-research/serpapi-key
   ```

**Option B – Lambda environment variable**

After deploy, set `SERPAPI_API_KEY` in the Lambda’s environment (e.g. in the AWS Console or via CDK). Prefer SSM for production.

### Deploy (Infrastructure as Code)

```bash
# Install Lambda dependencies (required for packaging)
cd functions/company-scraper && npm install && cd ../..

cd infrastructure
npm install
npx cdk bootstrap   # once per account/region
npx cdk deploy
# With SSM param: npx cdk deploy -c serpapiKeyParam=/company-research/serpapi-key
```

After deploy, note the stack outputs: **BucketName**, **ApiUrl**, **CloudFrontUrl**.

### Usage

**1. Scrape and store article URLs for a company**

```bash
# Via CloudFront (recommended)
curl -X POST "https://<CloudFrontDomain>/scrape" \
  -H "Content-Type: application/json" \
  -d '{"companyName": "Amazon"}'

# Or via API Gateway directly
curl -X POST "https://<ApiId>.execute-api.<region>.amazonaws.com/prod/scrape" \
  -H "Content-Type: application/json" \
  -d '{"companyName": "Amazon"}'
```

Response includes `companyKey`, S3 `key`, `articleCount`, and `articles` (url, title, snippet).

**2. List stored URLs for a company**

```bash
# companyKey = sanitized name, e.g. "amazon", "google"
curl "https://<CloudFrontDomain>/company/amazon"
```

**3. Read stored JSON via CloudFront (S3)**

Stored object key: `research/{companyKey}/urls.json`

```bash
curl "https://<CloudFrontDomain>/research/amazon/urls.json"
```

### S3 layout

| Key | Description |
|-----|-------------|
| `research/{companyKey}/urls.json` | Scrape result: `companyName`, `scrapedAt`, `articles[]` with `url`, `title`, `snippet` |

This file is ready to be used as context for Phase 2 (e.g. Bedrock) to generate interview questions.

### Project layout

```
hackathon_mays/
├── README.md
├── infrastructure/           # AWS CDK (TypeScript)
│   ├── bin/app.ts
│   ├── lib/company-research-stack.ts
│   ├── cdk.json
│   ├── package.json
│   └── tsconfig.json
└── functions/
    └── company-scraper/      # Lambda: search + S3 write
        ├── index.js
        └── package.json
```

### Other search providers

You can add support for **Google Custom Search** or **Bing Web Search** by implementing a similar function (call their JSON API and map results to `{ url, title, snippet }`), and choosing the provider via an environment variable.

### Destroy stack

```bash
cd infrastructure
npx cdk destroy
```

(Empty the S3 bucket first if it contains data.)
