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
cd functions/kendra-ingest && npm install && cd ../..
cd functions/kendra-insights && npm install && cd ../..

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

## Phase 2: AWS Kendra – Insights extraction from company URLs

After URLs are stored (Phase 1), **AWS Kendra** is used to extract insightful information from those URLs. The insights can later be passed to a Bedrock agent for generating interview questions.

### Flow

1. **Scrape** (Phase 1) → company URLs stored in S3 as `research/{companyKey}/urls.json`.
2. **Ingest** → Lambda fetches each URL’s content, strips HTML to text, and indexes it in a Kendra index with metadata `companyKey` (and `sourceUri`).
3. **Insights** → Lambda queries Kendra with a company-focused query and an attribute filter on `companyKey`, returning relevant passages as “insights”.

### API (Kendra)

**4. Ingest company URLs into Kendra** (run after scrape for that company)

```bash
curl -X POST "https://<CloudFrontDomain>/company/amazon/ingest"
```

Response: `documentsIngested`, `totalArticles`, and a message. The Kendra index may take a few minutes to update before insights are available.

**5. Get company insights from Kendra**

```bash
curl "https://<CloudFrontDomain>/company/amazon/insights"
```

Response: `companyKey`, `query`, `count`, and `insights[]` with `excerpt`, `title`, `documentId`, `sourceUri`, and optional `score`. These insights are suitable to pass to a Bedrock agent for question generation (not implemented in this repo).

### Architecture (Phase 2)

- **Kendra index** (Developer Edition) – one index for all companies; documents are tagged with `companyKey` and optionally `sourceUri`.
- **Kendra Ingest Lambda** – reads `urls.json` from S3, fetches each URL, converts HTML to text, and calls `BatchPutDocument`.
- **Kendra Insights Lambda** – runs a Kendra `Query` with an attribute filter on `companyKey` and returns the top passages.

Deploy outputs include **KendraIndexId** for reference.

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
    ├── company-scraper/      # Lambda: search + S3 write
    │   ├── index.js
    │   └── package.json
    ├── kendra-ingest/       # Lambda: fetch URLs → Kendra BatchPutDocument
    │   ├── index.js
    │   └── package.json
    └── kendra-insights/     # Lambda: Kendra Query → insights
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
