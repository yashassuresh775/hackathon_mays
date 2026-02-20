import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as iam from 'aws-cdk-lib/aws-iam';
import { join } from 'path';

export interface CompanyResearchStackProps extends cdk.StackProps {
  /** SSM Parameter Store name for SerpAPI key (e.g. /company-research/serpapi-key). If not set, set SERPAPI_API_KEY in Lambda env manually. */
  readonly serpapiKeyParam?: string;
}

export class CompanyResearchStack extends cdk.Stack {
  public readonly bucket: s3.Bucket;
  public readonly scraperFunction: lambda.Function;
  public readonly api: apigateway.RestApi;
  public readonly distribution: cloudfront.Distribution;

  constructor(scope: cdk.App, id: string, props?: CompanyResearchStackProps) {
    super(scope, id, props);

    const serpapiKeyParam = props?.serpapiKeyParam;

    // S3 bucket for storing article URLs and scraped data
    this.bucket = new s3.Bucket(this, 'CompanyResearchBucket', {
      bucketName: undefined, // let CDK generate a unique name
      versioned: false,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.GET, s3.HttpMethods.HEAD],
          allowedOrigins: ['*'],
          allowedHeaders: ['*'],
        },
      ],
    });

    // Lambda: given company name, search web and store relevant article URLs in S3
    // Package: run "npm install" in functions/company-scraper before deploy
    const lambdaEnv: Record<string, string> = {
      BUCKET_NAME: this.bucket.bucketName,
    };
    if (serpapiKeyParam) {
      lambdaEnv.SERPAPI_API_KEY_PARAM = serpapiKeyParam;
    }

    this.scraperFunction = new lambda.Function(this, 'CompanyScraper', {
      runtime: lambda.Runtime.NODEJS_20_X,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(join(__dirname, '../../functions/company-scraper')),
      timeout: cdk.Duration.seconds(60),
      memorySize: 256,
      environment: lambdaEnv,
    });
    this.bucket.grantReadWrite(this.scraperFunction);

    // Grant Lambda read access to the SSM parameter by ARN (no CFN parameter reference, so SecureString works)
    if (serpapiKeyParam) {
      const paramNameForArn = serpapiKeyParam.startsWith('/') ? serpapiKeyParam.slice(1) : serpapiKeyParam;
      const paramArn = this.formatArn({
        service: 'ssm',
        resource: 'parameter',
        resourceName: paramNameForArn,
        arnFormat: cdk.ArnFormat.SLASH_RESOURCE_NAME,
      });
      this.scraperFunction.addToRolePolicy(
        new iam.PolicyStatement({
          effect: iam.Effect.ALLOW,
          actions: ['ssm:GetParameter', 'ssm:GetParameters'],
          resources: [paramArn],
        })
      );
    }

    // REST API to trigger scraper
    this.api = new apigateway.RestApi(this, 'CompanyResearchApi', {
      restApiName: 'Company Research API',
      description: 'Trigger company research scraping and list stored URLs',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: ['Content-Type', 'Authorization'],
      },
    });

    const scrape = this.api.root.addResource('scrape');
    const scrapeIntegration = new apigateway.LambdaIntegration(this.scraperFunction);
    scrape.addMethod('POST', scrapeIntegration);

    const company = this.api.root.addResource('company').addResource('{companyKey}');
    company.addMethod('GET', new apigateway.LambdaIntegration(this.scraperFunction));

    // CloudFront distribution: API as origin for deployment / access
    this.distribution = new cloudfront.Distribution(this, 'CompanyResearchDistribution', {
      comment: 'Company Research API and S3 access',
      defaultBehavior: {
        origin: new origins.RestApiOrigin(this.api, {
          customHeaders: {},
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
      },
      additionalBehaviors: {
        '/research/*': {
          origin: origins.S3BucketOrigin.withOriginAccessControl(this.bucket),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        },
      },
      defaultRootObject: '',
      errorResponses: [
        { httpStatus: 404, responseHttpStatus: 404, responsePagePath: '/404' },
      ],
    });

    new cdk.CfnOutput(this, 'BucketName', {
      value: this.bucket.bucketName,
      description: 'S3 bucket for company research article URLs',
      exportName: 'CompanyResearchBucketName',
    });
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: this.api.url,
      description: 'API Gateway URL (direct)',
    });
    new cdk.CfnOutput(this, 'CloudFrontUrl', {
      value: `https://${this.distribution.distributionDomainName}`,
      description: 'CloudFront URL for API and S3 access',
    });
  }
}
