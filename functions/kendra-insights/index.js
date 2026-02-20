const { KendraClient, QueryCommand } = require('@aws-sdk/client-kendra');

const KENDRA_INDEX_ID = process.env.KENDRA_INDEX_ID;
const kendra = new KendraClient({});

const DEFAULT_QUERY =
  'Key facts, recent news, products, leadership, culture, strategy, and important information about this company.';
const MAX_RESULTS = 15;

function parsePath(event) {
  const path = (event.path || event.rawPath || '').replace(/\/$/, '');
  const match = path.match(/\/company\/([^/]+)\/insights/);
  return match ? decodeURIComponent(match[1]) : null;
}

async function getInsights(companyKey) {
  const response = await kendra.send(
    new QueryCommand({
      IndexId: KENDRA_INDEX_ID,
      QueryText: DEFAULT_QUERY,
      AttributeFilter: {
        EqualsTo: {
          Key: 'companyKey',
          Value: { StringValue: companyKey },
        },
      },
      PageNumber: 1,
      PageSize: MAX_RESULTS,
    })
  );

  const items = response.ResultItems || [];
  const insights = items.map((item) => {
    const doc = item.DocumentAttributes?.find((a) => a.Key === 'sourceUri');
    const sourceUri = doc?.Value?.StringValue;
    const excerptObj = item.DocumentExcerpt;
    const titleObj = item.DocumentTitle;
    return {
      excerpt: (excerptObj?.Text || '').trim() || null,
      title: (titleObj?.Text || '').trim() || null,
      documentId: item.DocumentId || null,
      sourceUri: sourceUri || null,
      score: item.ScoreAttributes?.ScoreConfidence,
    };
  });

  return {
    companyKey,
    query: DEFAULT_QUERY,
    count: insights.length,
    insights,
  };
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
      body: JSON.stringify({ error: 'Missing companyKey in path. Use GET /company/{companyKey}/insights' }),
    };
  }
  if ((event.httpMethod || event.requestContext?.http?.method) !== 'GET') {
    return {
      statusCode: 405,
      headers,
      body: JSON.stringify({ error: 'Method not allowed' }),
    };
  }
  try {
    const result = await getInsights(companyKey);
    return { statusCode: 200, headers, body: JSON.stringify(result) };
  } catch (err) {
    console.error(err);
    return {
      statusCode: 500,
      headers,
      body: JSON.stringify({ error: err.message || 'Insights retrieval failed' }),
    };
  }
};
