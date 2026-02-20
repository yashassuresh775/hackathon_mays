const fetch = require('node-fetch');
const { S3Client, PutObjectCommand, GetObjectCommand } = require('@aws-sdk/client-s3');
const { SSMClient, GetParameterCommand } = require('@aws-sdk/client-ssm');
const { Readable } = require('stream');

const BUCKET = process.env.BUCKET_NAME;
const S3_PREFIX = 'research';
const s3 = new S3Client({});
const ssm = new SSMClient({});

let cachedSerpApiKey = null;

async function getSerpApiKey() {
  if (cachedSerpApiKey) return cachedSerpApiKey;
  if (process.env.SERPAPI_API_KEY) {
    cachedSerpApiKey = process.env.SERPAPI_API_KEY;
    return cachedSerpApiKey;
  }
  const paramName = process.env.SERPAPI_API_KEY_PARAM;
  if (!paramName) {
    throw new Error(
      'Search API key required: set SERPAPI_API_KEY (env) or SERPAPI_API_KEY_PARAM (SSM parameter name). See README.'
    );
  }
  const cmd = new GetParameterCommand({ Name: paramName, WithDecryption: true });
  const out = await ssm.send(cmd);
  cachedSerpApiKey = out.Parameter?.Value || null;
  if (!cachedSerpApiKey) throw new Error(`Empty value for SSM parameter: ${paramName}`);
  return cachedSerpApiKey;
}

function sanitizeCompanyKey(name) {
  return name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'unknown';
}

/**
 * Search via SerpAPI (https://serpapi.com/search). Returns [{ url, title, snippet }].
 */
async function searchSerpAPI(query, maxResults = 20) {
  const apiKey = await getSerpApiKey();
  const url = `https://serpapi.com/search.json?q=${encodeURIComponent(query)}&api_key=${encodeURIComponent(apiKey)}`;
  const res = await fetch(url, {
    headers: { Accept: 'application/json' },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`SerpAPI failed: ${res.status} ${text.slice(0, 200)}`);
  }
  const data = await res.json();
  const organic = data.organic_results || [];
  const articles = organic.slice(0, maxResults).map((r) => ({
    url: r.link || r.url || '',
    title: r.title || '',
    snippet: r.snippet || '',
  })).filter((a) => a.url && a.title);
  return articles;
}

async function putJson(bucket, key, obj) {
  await s3.send(
    new PutObjectCommand({
      Bucket: bucket,
      Key: key,
      Body: JSON.stringify(obj, null, 2),
      ContentType: 'application/json',
    })
  );
}

async function getJson(bucket, key) {
  try {
    const out = await s3.send(
      new GetObjectCommand({ Bucket: bucket, Key: key })
    );
    const body = out.Body;
    const str = body instanceof Readable ? await streamToString(body) : String(body);
    return JSON.parse(str);
  } catch (e) {
    if (e.name === 'NoSuchKey') return null;
    throw e;
  }
}

function streamToString(stream) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    stream.on('data', (c) => chunks.push(c));
    stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    stream.on('error', reject);
  });
}

async function scrapeAndStore(companyName) {
  const companyKey = sanitizeCompanyKey(companyName);
  const query = `${companyName} company news about`;
  const articles = await searchSerpAPI(query, 20);
  const payload = {
    companyName: companyName.trim(),
    companyKey,
    scrapedAt: new Date().toISOString(),
    source: 'serpapi',
    articleCount: articles.length,
    articles,
  };
  const key = `${S3_PREFIX}/${companyKey}/urls.json`;
  await putJson(BUCKET, key, payload);
  return { companyKey, key, articleCount: articles.length, articles };
}

async function listStored(companyKey) {
  const key = `${S3_PREFIX}/${companyKey}/urls.json`;
  const data = await getJson(BUCKET, key);
  if (!data) return { companyKey, found: false, articles: [] };
  return {
    companyKey,
    found: true,
    scrapedAt: data.scrapedAt,
    articleCount: data.articles?.length ?? 0,
    articles: data.articles ?? [],
  };
}

function parseBody(event) {
  if (!event.body) return {};
  try {
    return typeof event.body === 'string' ? JSON.parse(event.body) : event.body;
  } catch {
    return {};
  }
}

exports.handler = async (event) => {
  const path = (event.path || event.rawPath || '').replace(/\/$/, '');
  const method = event.httpMethod || event.requestContext?.http?.method || '';

  const companyMatch = path.match(/\/company\/([^/]+)/);
  if (method === 'GET' && companyMatch) {
    const companyKey = decodeURIComponent(companyMatch[1]);
    const result = await listStored(companyKey);
    return {
      statusCode: 200,
      headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
      body: JSON.stringify(result),
    };
  }

  if (method === 'POST' && /\/scrape\/?$/.test(path)) {
    const body = parseBody(event);
    const companyName = body.companyName || body.company || '';
    if (!companyName.trim()) {
      return {
        statusCode: 400,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({ error: 'Missing companyName in body' }),
      };
    }
    try {
      const result = await scrapeAndStore(companyName);
      return {
        statusCode: 200,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify(result),
      };
    } catch (err) {
      console.error(err);
      return {
        statusCode: 500,
        headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
        body: JSON.stringify({ error: err.message || 'Scrape failed' }),
      };
    }
  }

  return {
    statusCode: 404,
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' },
    body: JSON.stringify({ error: 'Not found' }),
  };
};
