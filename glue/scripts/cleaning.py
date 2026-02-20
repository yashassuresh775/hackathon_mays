# Minimal Glue ETL: list objects under uploads/, normalize text, write to cleaned/
# Run with --source_bucket and --clean_output_prefix (set in Terraform default_arguments).
import sys
import boto3
from awsglue.utils import getResolvedOptions

args = getResolvedOptions(sys.argv, ["source_bucket", "clean_output_prefix", "JOB_NAME"])
bucket = args["source_bucket"]
prefix_out = args["clean_output_prefix"]
s3 = boto3.client("s3")

paginator = s3.get_paginator("list_objects_v2")
for page in paginator.paginate(Bucket=bucket, Prefix="uploads/"):
    for obj in page.get("Contents") or []:
        key = obj["Key"]
        if not key.endswith((".txt", ".csv")):
            continue
        try:
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            text = body.decode("utf-8", errors="replace").strip()
            text_clean = " ".join(text.split())
            out_key = prefix_out + key.replace("uploads/", "")
            s3.put_object(Bucket=bucket, Key=out_key, Body=text_clean.encode("utf-8"), ContentType="text/plain; charset=utf-8")
        except Exception:
            pass
