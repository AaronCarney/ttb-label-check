// Proxies ttb.aaroncarney.me to the Cloud Run service.
//
// The origin is addressed by its own hostname on purpose. Cloud Run's front end
// routes on the Host header, so forwarding this request with its own Host
// produces Google's 404 rather than the app. Building a Request against the
// origin URL sets the Host the origin expects, and carries the method, headers,
// and body through unchanged — which matters here, because a label check is a
// multipart upload and a batch reads a server-sent event stream.
export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = new URL(env.ORIGIN);
    url.protocol = origin.protocol;
    url.hostname = origin.hostname;
    url.port = origin.port;
    return fetch(new Request(url, request));
  },
};
