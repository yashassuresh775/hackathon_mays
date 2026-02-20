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
- `glue/scripts/` — Glue ETL script (when `enable_glue = true`)
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
terraform apply
```

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

## Optional: Kendra and Glue

- **Kendra** (Texas-focused search): set `enable_kendra = true` in `terraform.tfvars`; create a data source and index content. The brief generator will query Kendra when `KENDRA_INDEX_ID` is set.
- **Glue**: set `enable_glue = true` for ETL. A Glue Python shell job and script are created; the script is uploaded to `s3://<source_bucket>/glue/scripts/cleaning.py`. Trigger the job from the AWS Glue console or CLI. Set `packet_base_url` (and optionally `ses_from_email` for email) in `terraform.tfvars` for shareable links and email.

## User flows

1. **Interviewer**: Open frontend → enter company name (and optional context) or upload a document → Generate brief → view full brief & packet at `/interview/:id` → “Get shareable link” or “Send email” to send the packet to the interviewee.
2. **Interviewee**: Opens shareable link (e.g. `https://yourapp/packet/:id`) → sees “What we learned” and packet → submits “What did we get wrong?” and selects 2–3 questions → Submit.
3. **Interviewer (Stage 2)**: Opens `/interview/:id` again → sees interviewee corrections and selected questions for warm opening and guided conversation.
