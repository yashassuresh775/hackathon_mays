#!/usr/bin/env bash
# Run from repo root or terraform/. Uses your current AWS credentials.
# Imports existing briefs/packets S3 buckets into state, then applies.
set -e
cd "$(dirname "$0")"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Using AWS account: $ACCOUNT_ID"
echo "Importing S3 buckets..."
terraform import aws_s3_bucket.generated_briefs "interview-ai-briefs-hackathon-${ACCOUNT_ID}"
terraform import aws_s3_bucket.pre_interview_packets "interview-ai-packets-hackathon-${ACCOUNT_ID}"
echo "Applying..."
terraform apply
