# Serverless Text-to-Speech (Polly) — Lambda + HTTP API + S3 (CI/CD via GitHub Actions)

This project turns plain text in S3 into an **.mp3** using **Amazon Polly** through an **AWS Lambda** function fronted by an **Amazon API Gateway HTTP API**. Deployment to **beta** and **prod** is handled automatically by **GitHub Actions**.

---

## How it works (quick overview)

- The Lambda reads **`speech.txt`** from your S3 bucket (optionally under a prefix).
- It calls **Polly** (`en-US`, **Matthew**) to synthesize **MP3** audio.
- It writes the result back to S3 as **`speech.mp3`** (same bucket/prefix).
- CloudFormation provisions: IAM role/policies, Lambda, HTTP API, stage, and invoke permission.
- GitHub Actions:
  - **Beta workflow** runs on **pull requests to `main`**.
  - **Prod workflow** runs on **pushes to `main`** (e.g., after merge).

> **Important:** The Lambda reads text only from **S3** (`speech.txt`). The request body sent to the HTTP API is **not** used by the function.

The Lambda handler: `synthesize.lambda_handler` (file: `synthesize.py`).

---

## 1) Set up AWS credentials & S3 bucket

### Local AWS CLI (optional but recommended)
```bash
aws configure
# Provide AWS Access Key ID, Secret Access Key, and default region (e.g., us-east-2)
```

### Create S3 buckets (one per env)
Pick bucket names and (optional) prefixes (folder-like paths without leading `/`). The workflows expect **beta** and **prod** values.

Examples:
- **Bucket:** `your-beta-bucket`
- **Prefix:** `polly/beta`  
- **Bucket:** `your-prod-bucket`
- **Prefix:** `polly/prod`

Create buckets (if needed):
```bash
aws s3 mb s3://your-beta-bucket --region us-east-2
aws s3 mb s3://your-prod-bucket --region us-east-2
```

> Ensure your buckets are in the same region you deploy the stack to (e.g., `us-east-2`).

### Required GitHub Secrets
Add these in your repo settings → **Secrets and variables → Actions**:

| Secret | Example / Notes |
|---|---|
| `AWS_ACCESS_KEY_ID` | Access key for a CI user allowed to deploy |
| `AWS_SECRET_ACCESS_KEY` | Secret for the CI user |
| `AWS_REGION` | e.g., `us-east-2` |
| `CF_STACK_NAME_BETA` | e.g., `polly-tts-beta` |
| `CF_STACK_NAME_PROD` | e.g., `polly-tts-prod` |
| `LAMBDA_NAME_BETA` | e.g., `PollyLambdaFunction-beta` |
| `LAMBDA_NAME_PROD` | e.g., `PollyLambdaFunction-prod` |
| `S3_BUCKET_BETA` | your **beta** bucket name |
| `S3_BUCKET_PROD` | your **prod** bucket name |
| `S3_PATH_BETA` | e.g., `polly/beta` (or empty for root) |
| `S3_PATH_PROD` | e.g., `polly/prod` (or empty for root) |

> The CloudFormation template sets Lambda env vars `S3_Bucket` and `S3_Bucket_Prefix` from these values.

---

## 2) Modify the text (what gets synthesized)

The Lambda **always** reads from **`speech.txt`** in your configured S3 bucket/prefix:

- If **no prefix**: `s3://<bucket>/speech.txt`
- If **prefix is set**: `s3://<bucket>/<prefix>/speech.txt`

To update the text:
```bash
# edit locally
echo "Hello from Polly!" > speech.txt

# upload to beta path
aws s3 cp speech.txt s3://$S3_BUCKET_BETA/$S3_PATH_BETA/speech.txt

# upload to prod path
aws s3 cp speech.txt s3://$S3_BUCKET_PROD/$S3_PATH_PROD/speech.txt
```

> The beta/prod workflows *also* upload `speech.txt` from the repo to your S3 bucket/path on each run. If you prefer manual control, remove that step in the workflows.

---

## 3) Trigger the workflows

There are two workflows:

- **Beta** (`.github/workflows/...beta.yml`) — runs on **pull requests to `main`**.  
  Steps: package `synthesize.py` → upload `function.zip` → upload `speech.txt` → `sam deploy` to **beta** stack → **smoke test** Lambda.

- **Prod** (`.github/workflows/...prod.yml`) — runs on **pushes to `main`**.  
  Steps: package/upload → `sam deploy` to **prod** stack → **smoke test** Lambda.

### Typical commands
```bash
# Create a feature branch, commit, push, open PR -> triggers **beta** workflow
git checkout -b feature/adjust-voice
git add .
git commit -m "Adjust text / pipeline"
git push -u origin feature/adjust-voice
# Open a PR to main (GitHub UI)

# Merge the PR -> push to main -> triggers **prod** workflow
# (or push directly to main if your policy allows—not recommended)
```

> Both workflows use **SAM** to deploy the CloudFormation templates and will create/update: the Lambda, HTTP API, stage, and IAM role/policies.

---

## 4) Verify the uploaded `.mp3` files

After the Lambda runs, it writes **`speech.mp3`** to the same bucket/prefix as the input `speech.txt`:

- No prefix: `s3://<bucket>/speech.mp3`
- With prefix: `s3://<bucket>/<prefix>/speech.mp3`

### Quick checks
```bash
# List objects in the path
aws s3 ls s3://$S3_BUCKET_BETA/$S3_PATH_BETA/

# Download and play locally
aws s3 cp s3://$S3_BUCKET_BETA/$S3_PATH_BETA/speech.mp3 ./speech_beta.mp3

# Optional: Verify ContentType metadata
aws s3api head-object --bucket "$S3_BUCKET_BETA" --key "$S3_PATH_BETA/speech.mp3"   --query 'ContentType' --output text  # should be audio/mpeg

# Generate a pre-signed URL to listen in the browser (valid ~1h by default)
aws s3 presign s3://$S3_BUCKET_BETA/$S3_PATH_BETA/speech.mp3
```

Repeat the same for **prod** with `S3_BUCKET_PROD` / `S3_PATH_PROD`.

---

## 5) Verify deployment (stack outputs, API URL)

Each deploy exposes outputs, including the **HTTP API URL**:
```bash
# Beta
aws cloudformation describe-stacks   --stack-name "$CF_STACK_NAME_BETA"   --query "Stacks[0].Outputs" --output table

# Prod
aws cloudformation describe-stacks   --stack-name "$CF_STACK_NAME_PROD"   --query "Stacks[0].Outputs" --output table
```

Look for:
- **`ApiGatewayUrl`** → `https://<apiId>.execute-api.<region>.amazonaws.com/<stage>`
- **`S3BucketUri`** → *where `speech.txt` and `speech.mp3` live*

### Invoke the API (sanity check)
> Note: The request body is ignored by the Lambda; response includes bucket/prefix.
```bash
API_BETA=$(aws cloudformation describe-stacks   --stack-name "$CF_STACK_NAME_BETA"   --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" --output text)

curl -i "$API_BETA/synthesize"
# Expect 200 + JSON like: {"bucket":"...","prefix":"..."}
```

### Invoke Lambda directly (CLI)
```bash
aws lambda invoke   --function-name "$LAMBDA_NAME_BETA"   --cli-binary-format raw-in-base64-out   --payload '{"ping":"true"}' out.json && cat out.json
```

> The **workflows already perform a smoke test** similar to the above and print the Lambda response in their logs.

---

## Files & templates in this repo

- `synthesize.py` — Lambda code (reads `speech.txt` from S3; writes `speech.mp3`).
- `infrastructure/cloudformation/template-beta.yml` — CFN for beta.
- `infrastructure/cloudformation/template-prod.yml` — CFN for prod.
- `.github/workflows/<...beta>.yml` — Beta CI/CD pipeline.
- `.github/workflows/<...prod>.yml` — Prod CI/CD pipeline.

### Environment variables used by Lambda
- `S3_Bucket` — Target bucket for input/output.
- `S3_Bucket_Prefix` — Optional folder path (`""` for root).

> CFN condition `HasPrefix` is used only for output formatting; the code itself tolerates leading/trailing slashes in the prefix via `prefix.strip("/")`.

---

## Troubleshooting tips

- **403/Forbidden from API**: Confirm you’re using the **HTTP API** URL from stack outputs and the stage (e.g., `/beta` or `/prod`), and that `PermissionForApiToInvokeLambda` exists in the stack.
- **`speech.mp3` not appearing**: Ensure `speech.txt` exists at the expected S3 key **before** invoking Lambda; check CloudWatch logs for the Lambda.
- **Wrong region**: Buckets, stacks, and workflows must point to the **same region**.
- **Prefix got duplicated**: Set `S3_PATH_*` without leading `/` (e.g., `polly/beta`). The code strips slashes but keeping it clean avoids confusion.

---

## Clean up
```bash
# Delete stacks
aws cloudformation delete-stack --stack-name "$CF_STACK_NAME_BETA"
aws cloudformation delete-stack --stack-name "$CF_STACK_NAME_PROD"

# Remove objects/buckets (careful)
aws s3 rm s3://$S3_BUCKET_BETA/$S3_PATH_BETA/ --recursive
aws s3 rm s3://$S3_BUCKET_PROD/$S3_PATH_PROD/ --recursive
aws s3 rb s3://$S3_BUCKET_BETA
aws s3 rb s3://$S3_BUCKET_PROD
```

---

## Security note
Use a dedicated CI IAM user/role with the minimal permissions necessary for:
- Deploying CloudFormation stacks,
- Uploading to S3,
- Creating/updating Lambda & API Gateway resources,
- Calling Polly’s `SynthesizeSpeech`.
