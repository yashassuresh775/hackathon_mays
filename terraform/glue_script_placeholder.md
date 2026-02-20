# Glue cleaning script

When `enable_glue = true`, upload a script to:

`s3://<SOURCE_BUCKET>/glue/scripts/cleaning.py`

The job expects a Python script that:

1. Reads from the source bucket (e.g. `uploads/` or raw data).
2. Cleans/normalizes text (e.g. dedupe, strip, encoding).
3. Writes to `cleaned/` prefix in the same bucket.

Example minimal script (upload manually or via CI):

```python
import sys
from awsglue.utils import getResolvedOptions
from pyspark.context import SparkContext
from awsglue.context import GlueContext
from awsglue.job import Job

args = getResolvedOptions(sys.argv, ["source_bucket", "clean_output_prefix"])
sc = SparkContext()
glueContext = GlueContext(sc)
job = Job(glueContext)
job.init(args["JOB_NAME"], args)

# Read from s3://bucket/uploads/ and write to s3://bucket/cleaned/
# Add your cleaning logic (normalize text, filter, etc.)
job.commit()
```

Then trigger the job from the AWS Glue console or: `aws glue start-job-run --job-name <job-name>`.
