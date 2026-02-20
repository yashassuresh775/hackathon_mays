const fetch = require('node-fetch');
const crypto = require('crypto');
const { S3Client, GetObjectCommand } = require('@aws-sdk/client-s3');
const { KendraClient, BatchPutDocumentCommand } = require('@aws-sdk/client-kendra');
const { Readable } = require('stream');

const BUCKET = process.env.BUCKET_NAME;
const KENDRA_INDEX_ID = process.env.KENDRA_INDEX_ID;
const S3_PREFIX = 'research';
const s3 = new S3Client({});
const kendra = new KendraClient({});

const MAX_DOC_BYTES = 4 * 1024 * 1024; // 4 MB (Kendra limit 5 MB)
const FETCH_TIMEOUT_MS = 15000;
const BATCH_SIZE = 10;

function streamToString(stream) {
  return new Promise((resolve, reject) => {
    const chunks = [];
    stream.on('data', (c) => chunks.push(c));
    stream.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    stream.on('error', reject);
  });
}

async function getJson(bucket, key) {
  const out = await s3.send(new GetObjectCommand({ Bucket: bucket, Key: key }));
  const body = out.Body;
  const str = body instanceof Readable ? await streamToString(body) : String(body);
  return JSON.parse(str);
}

/** Simple HTML tag stripping and whitespace normalization */
function htmlToPlainText(html) {
  if (!html || typeof html !== 'string') return '';
  let text = html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, ' ')
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  return text;
}

function docId(companyKey, url) {
  return crypto.createHash('sha256').update(companyKey + url).digest('hex').slice(0, 64);
}

async function fetchUrlContent(url) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, {
      signal: controller.signal,
      headers: {
        'User-Agent': 'CompanyResearchBot/1.0 (Insights extraction)',
        Accept: 'text/html,application/xhtml+xml',
      },
      redirect: 'follow',
    });
    clearTimeout(timeout);
    if (!res.ok) return null;
    const html = await res.text();
    return htmlToPlainText(html);
  } catch (e) {
    clearTimeout(timeout);
    return null;
  }
}

async function ingestCompany(companyKey) {
  const key = `${S3_PREFIX}/${companyKey}/urls.json`;
  let data;
  try {
    data = await getJson(BUCKET, key);
  } catch (e) {
    if (e.name === 'NoSuchKey') {
      return { error: 'No URLs found for this company. Run scrape first.', documentsIngested: 0 };
    }
    throw e;
  }
  const articles = data.articles || [];
  if (articles.length === 0) {
    return { companyKey, documentsIngested: 0, message: 'No articles to ingest' };
  }

  const documents = [];
  for (const article of articles) {
    const url = article.url;
    if (!url) continue;
    const text = await fetchUrlContent(url);
    const snippet = (article.snippet || '').trim();
    const title = (article.title || url).trim();
    const body = text && text.length > 10
      ? text
      : snippet;
    if (!body || body.length < 20) continue;
    const content = (title ? title + '\n\n' : '') + body;
    const truncated = content.length > MAX_DOC_BYTES
      ? content.slice(0, MAX_DOC_BYTES)
      : content;
    const blob = Buffer.from(truncated, 'utf8');
    documents.push({
      Id: docId(companyKey, url),
      Title: title || url,
      Blob: blob,
      Attributes: [
        { Key: 'companyKey', Value: { StringValue: companyKey } },
        { Key: 'sourceUri', Value: { StringValue: url } },
      ],
    });
  }

  let ingested = 0;
  for (let i = 0; i < documents.length; i += BATCH_SIZE) {
    const batch = documents.slice(i, i + BATCH_SIZE);
    await kendra.send(
      new BatchPutDocumentCommand({
        IndexId: KENDRA_INDEX_ID,
        Documents: batch,
      })
    );
    ingested += batch.length;
  }

  return {
    companyKey,
    documentsIngested: ingested,
    totalArticles: articles.length,
    message: `Ingested ${ingested} documents into Kendra. Index may take a few minutes to update.`,
  };
}

function parsePath(event) {
  const path = (event.path || event.rawPath || '').replace(/\/$/, '');
  const match = path.match(/\/company\/([^/]+)\/ingest/);
  return match ? decodeURIComponent(match[1]) : null;
}

const headers = {
  'Content-Type': 'application/json',
  'Access-Control-Allow-Origin': '*',
};

exports.handler = async (event) => {
  const companyKey = parsePath(event);
  if (!companyKey) {
    return {
      statusCode: 400,
      headers,
      body: JSON.stringify({ error: 'Missing companyKey in path. Use POST /company/{companyKey}/ingest' }),
    };
  }
  if ((event.httpMethod || event.requestContext?.http?.method) !== 'POST') {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ error: 'Method not allowed' }),
    };
  }
  try {
    const result = await ingestCompany(companyKey);
    if (result.error) {
      return { statusCode: 404, headers, body: JSON.stringify(result) };
    }
    return { statusCode: 200, headers, body: JSON.stringify(result) };
  } catch (err) {
    console.error(err);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: err.message || 'Ingest failed' }),
    };
  }
};
