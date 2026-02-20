# AI-Powered Interview Intelligence — Hackathon Base

Texas A&M Mays Business School Hackathon: generate interviewer briefs and pre-interview packets using AWS (Bedrock, Textract, Comprehend, S3, DynamoDB, Lambda, API Gateway).

## AWS access (Option 2: environment variables)

Set credentials before running Terraform or calling the API:

```bash
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"
```

Or copy from `.env.example` and source it:

```bash
cp .env.example .env
# Edit .env with your keys, then:
source .env
```

Verify:

```bash
aws sts get-caller-identity
```

### Workshop credentials (Zoom / temporary, e.g. us-west-2)

If you received temporary credentials (with `AWS_SESSION_TOKEN`):

1. Copy the example file and paste your values:
   ```bash
   cp env.workshop.example env.workshop
   # Edit env.workshop with the access key, secret key, session token, and region (e.g. us-west-2).
   ```
2. Load them in your shell:
   ```bash
   source env.workshop
   ```
3. Deploy to the workshop region (e.g. us-west-2):
   ```bash
   cd terraform
   terraform init
   terraform apply -var="aws_region=us-west-2"
   ```
4. In AWS Console (same region): **Amazon Bedrock → Model access** → request **Amazon Nova Lite** (or Nova Micro/Pro) so brief generation works.

**Security:** Do not commit `env.workshop` (it is in `.gitignore`). Rotate or discard workshop credentials after the event.

## Project layout

- `terraform/` — AWS infrastructure (S3, DynamoDB, Lambda, API Gateway, IAM, optional Kendra/Glue)
- `lambda/orchestrator/` — API Gateway → routes to workers
- `lambda/brief_generator/` — Comprehend + optional Kendra → Bedrock (brief + packet)
- `lambda/document_processor/` — Textract document extraction
- `lambda/upload_url/` — Presigned S3 upload URL for document upload
- `lambda/get_interview/` — GET brief + packet + interviewee response
- `lambda/packet_response/` — POST interviewee corrections and selected 2–3 questions
- `lambda/send_packet/` — Shareable link + optional SES email
- `lambda/external_ingest/` — **Multi-source ingest**: Google CSE, **Microsoft Bing Web**, **Bing News Search**, **DuckDuckGo** (no key), News API → S3 (raw + Kendra-ready .txt). Uses a **“latest news”** query for recent company stories.
- `glue/scripts/` — Glue ETL: uploads → cleaned/; **external/raw/*.json → external/kendra_docs/** for Kendra
- `amplify/` — React frontend: home (generate, upload, send packet), `/packet/:id` (interviewee), `/interview/:id` (interviewer view)

## Deploy with Terraform

From the repo root:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

After apply, note the outputs:

- `api_gateway_url` — base URL for the API
- `generate_brief_invoke_url` — `POST /generate-brief` endpoint
- `source_documents_bucket_name` — upload PDFs here (optional, with prefix `uploads/` for auto-processing)

### S3: "BucketAlreadyOwnedByYou" (409) on apply

The briefs and packets buckets use the **us-west-2** provider (`aws.west`). If they already exist in AWS, import them **once** so Terraform stops trying to create them:

```bash
cd terraform
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
terraform import aws_s3_bucket.generated_briefs "interview-ai-briefs-hackathon-${ACCOUNT_ID}"
terraform import aws_s3_bucket.pre_interview_packets "interview-ai-packets-hackathon-${ACCOUNT_ID}"
terraform import aws_s3_bucket.source_documents "interview-ai-source-docs-hackathon-${ACCOUNT_ID}"
terraform apply
```

### S3: Access Denied (403) on bucket notification or CORS

If Terraform fails with **Access Denied** when reading or updating S3 bucket notification or CORS (e.g. `GetBucketNotificationConfiguration`, `GetBucketCors`), your IAM user or role needs these actions on the source bucket: `s3:GetBucketNotificationConfiguration`, `s3:PutBucketNotificationConfiguration`, `s3:GetBucketCors`, `s3:PutBucketCors`. Alternatively, disable those features so apply can succeed:

1. Add to `terraform.tfvars` (or pass via `-var`):
   ```hcl
   enable_s3_bucket_notification = false
   enable_s3_cors                = false
   ```
2. Remove the resources from state so Terraform stops managing them:
   ```bash
   cd terraform
   terraform state rm 'aws_s3_bucket_notification.source_documents' 'aws_s3_bucket_cors_configuration.source_documents'
   ```
3. Run `terraform apply` again.

With these disabled, PDF uploads to the source bucket will not auto-trigger the document processor (you can still call the extract API manually), and CORS for browser uploads will not be set (upload via API or CLI instead).

## API usage

### Generate brief and packet

```bash
curl -X POST "$(terraform -chdir=terraform output -raw generate_brief_invoke_url)" \
  -H "Content-Type: application/json" \
  -d '{"company_name": "Acme Corp", "context": "Texas-based energy company"}'
```

### Extract text from a document (after uploading to S3)

```bash
curl -X POST "<API_URL>/extract-document" \
  -H "Content-Type: application/json" \
  -d '{"bucket": "<SOURCE_BUCKET>", "key": "uploads/report.pdf"}'
```

## Bedrock

The brief generator uses **Amazon Nova** (Lite, Micro, or Pro) in us-east-1 via the Bedrock Converse API. Ensure Bedrock is enabled and request Nova model access in the console. If you use another region, set `aws_region` in `terraform/variables.tf` and ensure Nova is available there.

## Cost and cleanup

- Set a billing budget in the AWS console.
- To destroy all resources: `cd terraform && terraform destroy`

## Frontend (Amplify)

The React app in `amplify/` calls API Gateway. After `terraform apply`:

1. `cd amplify && cp .env.example .env`
2. Set `VITE_API_URL` to your API URL: `terraform -chdir=terraform output -raw api_gateway_url`
3. `npm install && npm run dev` — open http://localhost:3000
4. To deploy: build with `npm run build` and deploy the `dist/` folder via [Amplify Console](https://console.aws.amazon.com/amplify) (connect repo or manual deploy).

## Optional: External ingest (Google / News) → Kendra + Glue

**End-to-end flow:** External APIs (Google, **Microsoft Bing Web**, **Bing News Search**, **DuckDuckGo**, News) → S3 → Glue cleans → Kendra indexes → brief generator gets richer context.

**Latest-story behavior:** Ingest uses a **“latest news”** query (e.g. `"{company_name} latest news"`) for Google, Bing Web, Bing News, and DuckDuckGo so results favor recent company stories. News API and Bing News are sorted by date; dates are included in snippets for Kendra.

1. **Enable Kendra and Glue:** Set `enable_kendra = true` and `enable_glue = true` in `terraform.tfvars`.
2. **Search engines and keys** (optional; leave empty to skip a source):
   - **DuckDuckGo** — runs with **no API key** (Instant Answer API).
   - **Google:** `google_cse_api_key` and `google_cse_cx` — [Google Custom Search](https://developers.google.com/custom-search/v1/overview)
   - **Microsoft Bing:** `bing_subscription_key` — [Azure](https://learn.microsoft.com/en-us/bing/search-apis/) **Bing Web Search v7** and **Bing News Search v7** (same key for both)
   - **News:** `news_api_key` — [NewsAPI.org](https://newsapi.org/)
3. **Ingest:** `POST /ingest-external` with body `{ "company_name": "Acme Corp", "context": "optional" }`. Writes to S3: `external/raw/<slug>/*.json` and `external/kendra_docs/<slug>_<ts>.txt`.
4. **Glue:** Run the cleaning job (console or CLI); it processes `external/raw/*.json` and writes more docs to `external/kendra_docs/`.
5. **Kendra:** The S3 data source syncs `external/kendra_docs/` and `cleaned/` (daily by default). After sync, **generate-brief** uses this content via Kendra search.
6. **Unique touch:** `POST /generate-brief` with `{ "company_name": "Acme", "ingest_first": true }` runs external ingest for that company before generating the brief (Kendra will have the new doc after the next sync).

## Optional: Kendra and Glue (summary)

- **Kendra**: set `enable_kendra = true`; the Terraform adds an S3 data source for `external/kendra_docs/` and `cleaned/`. Brief generator queries Kendra when `KENDRA_INDEX_ID` is set.
- **Glue**: set `enable_glue = true`; script at `s3://<source_bucket>/glue/scripts/cleaning.py` processes uploads and **external/raw** JSON into Kendra-ready text. Set `packet_base_url` and optionally `ses_from_email` for shareable links and email.

## Automated document → brief flow

When you **upload a document** in the UI, use one of these formats:

- **PDF:** All pages are parsed (Textract async). Single- and multi-page supported.
- **Images (OCR):** JPEG, PNG, TIFF (single image per file).
- **Plain text:** .txt, .csv (read directly from S3, no OCR).

Other formats (e.g. .docx) are not supported and will return an error.

1. The file is stored in S3 at `uploads/{prefix}/{filename}`.
2. The app calls **extract-document**; the **document processor** runs **Textract** and writes the extracted text to **`cleaned/uploads/{prefix}/{filename}.txt`** in the source bucket. That path is indexed by Kendra (when enabled) and is used immediately for the next brief.
3. The UI remembers the upload key. When you click **Generate brief**, it sends **`document_key`** (e.g. `uploads/abc12/report.pdf`). The **brief generator** reads the text from `cleaned/uploads/.../report.txt` and includes it in the Bedrock prompt as **primary source** for the interviewer brief and packet.

So: **upload → extract (Textract) → save to cleaned/ → next Generate brief uses that content automatically.** You can also trigger extraction via S3 event (when `enable_s3_bucket_notification` is true): any new PDF under `uploads/` runs the document processor and writes to `cleaned/` without a separate API call.

## User flows

1. **Interviewer**: Open frontend → enter company name (and optional context) or upload a document → Generate brief → view full brief & packet at `/interview/:id` → “Get shareable link” or “Send email” to send the packet to the interviewee.
2. **Interviewee**: Opens shareable link (e.g. `https://yourapp/packet/:id`) → sees “What we learned” and packet → submits “What did we get wrong?” and selects 2–3 questions → Submit.
3. **Interviewer (Stage 2)**: Opens `/interview/:id` again → sees interviewee corrections and selected questions for warm opening and guided conversation.

## Testing and review (upload → brief)

- **Upload:** `POST /upload-url` → PUT file to presigned URL → file in `uploads/{prefix}/{filename}`. Works for PDF and .txt.
- **Extract:** `POST /extract-document` with `bucket` and `key`. For **.txt/.csv** the processor reads from S3 and writes to `cleaned/...`. For **PDF** it uses Textract (async for multi-page); the hand-crafted minimal PDF in `scripts/make_sample_pdf.py` can be rejected by Textract—use `sample_upload_test.txt` or a standard PDF for tests.
- **Generate brief:** `POST /generate-brief` with `company_name` and `document_key` (the upload `key`). The brief generator reads `cleaned/...` and passes that text into the Bedrock prompt. The prompt instructs the model to use the uploaded document as the primary source and to cite specific details (founding year, location, product names, team size) so the brief matches the document.
- **Get full brief:** `GET /interview/{id}` returns `brief_text`, `packet_text`, and packet response. Response field is `brief_text` (not `brief`).

### "Service unavailable" or timeouts when uploading/parsing

- **Upload:** If you see 503 on **upload-url**, the Lambda may be missing `SOURCE_BUCKET` (check Terraform env). If the **browser** shows "service unavailable" after clicking Upload, the failure is often on the next step: **extract-document**.
- **Extract-document:** API Gateway has a **~29 second** integration timeout. The document processor can take up to ~28 seconds for PDFs (Textract async). If the request takes longer, the gateway returns **504** or the client sees "service unavailable".
  - **Fix:** Use a **.txt or .csv** file for immediate parsing (no OCR; returns in 1–2 seconds). For PDFs, use a **short/single-page** PDF, or upload the PDF and wait 1–2 minutes then run **Generate brief** (if S3 event trigger is enabled, the processor runs in the background and writes to `cleaned/`).
- **Orchestrator** timeout was increased to 120s so it can wait for the document processor; the main limit is still the API Gateway 29s.
