// CloudFront Function for erranddesk.com, runtime: cloudfront-js-2.0
// Uses only features listed for runtime 2.0 (const/let, for, for-in, endsWith, includes; no for...of).
// Event: VIEWER REQUEST on the distribution's Default (*) behavior.
// 1) Redirects www.erranddesk.com -> https://erranddesk.com (301), keeping path and query string.
// 2) Serves folder URLs from S3: "/guides/fax-prices/" -> "/guides/fax-prices/index.html",
//    and "/guides/fax-prices" (no dot, no trailing slash) -> "/guides/fax-prices/index.html".
const APEX = 'erranddesk.com';

function buildQuery(qs) {
  const parts = [];
  for (const key in qs) {
    const p = qs[key];
    if (p.multiValue) {
      for (let i = 0; i < p.multiValue.length; i++) {
        const mv = p.multiValue[i];
        parts.push(mv.value === '' ? key : key + '=' + mv.value);
      }
    } else {
      parts.push(p.value === '' ? key : key + '=' + p.value);
    }
  }
  return parts.length ? '?' + parts.join('&') : '';
}

function handler(event) {
  const request = event.request;
  const host = request.headers.host ? request.headers.host.value.toLowerCase() : '';

  if (host === 'www.' + APEX) {
    return {
      statusCode: 301,
      statusDescription: 'Moved Permanently',
      headers: { location: { value: 'https://' + APEX + request.uri + buildQuery(request.querystring) } }
    };
  }

  const uri = request.uri;
  if (uri.endsWith('/')) {
    request.uri = uri + 'index.html';
  } else if (!uri.split('/').pop().includes('.')) {
    request.uri = uri + '/index.html';
  }
  return request;
}
