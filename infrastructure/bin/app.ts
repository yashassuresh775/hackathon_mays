#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { CompanyResearchStack } from '../lib/company-research-stack';

const app = new cdk.App();
new CompanyResearchStack(app, 'CompanyResearchStack', {
  env: {
    account: process.env.CDK_DEFAULT_ACCOUNT,
    region: process.env.CDK_DEFAULT_REGION || 'us-east-1',
  },
  description: 'Company research: web scraping + S3 storage, fronted by CloudFront',
  serpapiKeyParam: app.node.tryGetContext('serpapiKeyParam') as string | undefined,
});
