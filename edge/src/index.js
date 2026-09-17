// The front door: ttb.aaroncarney.me, forwarding to the Cloud Run service.
//
// Two jobs beyond forwarding, both argued in docs/decisions.md.
//
// It signs every forwarded request (0028). The design is that the service runs
// with the invoker check on and grants roles/run.invoker to this Worker's
// service account and to nobody else, so the run.app URL answers everyone else
// with 403 — and a request IAM denies is never billed. The Worker holds a key
// for that account as a secret and mints a Google ID token from it.
//
// That design IS the state of the deployed service, as of the last measurement.
// Measured 2026-09-17 at 22:30 UTC: the IAM policy grants roles/run.invoker to
// this Worker's service account and to nobody else, the run.app URL answers
// /api/health with 403 and no credentials at all, and ttb.aaroncarney.me
// answers it with 200. It has not always been so - the service was deployed
// open with TTB_PUBLIC=1 so that a reviewer could reach it, and while that
// held, the origin could be reached without passing through this Worker.
// scripts/deploy.sh sets this either way depending on the access flag it is
// given, so this is a measurement and not a property of the design.
//
// It rate-limits what does get through (0029) — except that it does not, as the
// measurement at the limit() call below records. So of the two things this file
// names as bounding the meter, neither holds today, and each comment used to
// excuse itself by pointing at the other. What is left is the two-instance cap
// in scripts/deploy.sh. A Free zone's own WAF rule cannot match a hostname, so
// it cannot be scoped to this project alone; the Worker can, because it runs
// for this hostname only.

const TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token";
const JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer";

// Refresh this far before the hour is out, so a request never races an expiry.
const REFRESH_MARGIN_SECONDS = 300;

// Cached across requests in the same isolate. An isolate that has never minted
// one pays the exchange on its first request; the rest read this.
let cachedToken = null; // { token: string, expiresAt: number (epoch seconds) }

function base64Url(input) {
  const bytes =
    typeof input === "string" ? new TextEncoder().encode(input) : new Uint8Array(input);
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// The key arrives as PEM text inside the service account's JSON. WebCrypto wants
// the DER bytes that PEM wraps.
function pemToPkcs8(pem) {
  const body = pem
    .replace("-----BEGIN PRIVATE KEY-----", "")
    .replace("-----END PRIVATE KEY-----", "")
    .replace(/\s+/g, "");
  const raw = atob(body);
  const bytes = new Uint8Array(raw.length);
  for (let i = 0; i < raw.length; i += 1) bytes[i] = raw.charCodeAt(i);
  return bytes.buffer;
}

// The audience is the run.app URL, never ttb.aaroncarney.me: Google does not
// support a custom domain as an `aud` value (0028).
async function mintIdToken(credentials, audience) {
  const now = Math.floor(Date.now() / 1000);
  const header = base64Url(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const claims = base64Url(
    JSON.stringify({
      iss: credentials.client_email,
      sub: credentials.client_email,
      aud: TOKEN_ENDPOINT,
      iat: now,
      exp: now + 3600,
      target_audience: audience,
    }),
  );
  const signingInput = `${header}.${claims}`;

  const key = await crypto.subtle.importKey(
    "pkcs8",
    pemToPkcs8(credentials.private_key),
    { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "RSASSA-PKCS1-v1_5",
    key,
    new TextEncoder().encode(signingInput),
  );

  const response = await fetch(TOKEN_ENDPOINT, {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: JWT_BEARER_GRANT,
      assertion: `${signingInput}.${base64Url(signature)}`,
    }),
  });
  if (!response.ok) {
    throw new Error(`token exchange failed: ${response.status} ${await response.text()}`);
  }

  const { id_token: idToken } = await response.json();
  if (!idToken) throw new Error("token exchange returned no id_token");

  // Trust the token's own expiry rather than assuming the hour we asked for.
  const payload = JSON.parse(atob(idToken.split(".")[1].replace(/-/g, "+").replace(/_/g, "/")));
  return { token: idToken, expiresAt: payload.exp };
}

async function invokerToken(env) {
  const now = Math.floor(Date.now() / 1000);
  if (cachedToken && cachedToken.expiresAt - REFRESH_MARGIN_SECONDS > now) {
    return cachedToken.token;
  }
  cachedToken = await mintIdToken(JSON.parse(env.INVOKER_KEY), env.ORIGIN);
  return cachedToken.token;
}

export default {
  async fetch(request, env) {
    // One key for the whole hostname, not one per client address. What is being
    // bounded is the bill, and a per-address limit multiplies by the number of
    // addresses. The cost is that a flood can crowd out a reviewer here — which
    // is the lesser failure, because it spends nothing. That reasoning used to
    // rest on the invoker check standing between a flood and the meter (0028);
    // as of 2026-09-17 that check is not on — see the header. So the argument
    // for one key over one per address still holds on its own terms, but it is
    // no longer backed by a second gate.
    //
    // This call does not currently deny anything. Measured on the deployed
    // Worker 2026-09-16: configured at 5 requests per 60 seconds, limit()
    // returned success: true on the tenth request of ten, and 310 requests
    // inside one minute were all forwarded. The binding deploys, the call runs,
    // and it fails open on this plan — see decision 0029. It is kept because it
    // is the mechanism that record chose and it starts holding the moment the
    // platform honours it; it is not what bounds the meter today.
    if (env.PROXY_RATE_LIMIT) {
      const { success } = await env.PROXY_RATE_LIMIT.limit({ key: "ttb.aaroncarney.me" });
      if (!success) {
        return new Response("Too many requests. Try again shortly.\n", {
          status: 429,
          headers: { "retry-after": "60", "content-type": "text/plain; charset=utf-8" },
        });
      }
    }

    const url = new URL(request.url);
    const origin = new URL(env.ORIGIN);
    url.protocol = origin.protocol;
    url.hostname = origin.hostname;
    url.port = origin.port;

    // Built against the origin URL so the Host header is the one Cloud Run routes
    // on; method, headers and body carry through, which a multipart label upload
    // and a batch's event stream both need.
    const forwarded = new Request(url, request);
    forwarded.headers.set("authorization", `Bearer ${await invokerToken(env)}`);
    return fetch(forwarded);
  },
};
