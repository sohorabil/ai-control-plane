export interface Env {
	EDGE_SECRET: string;
	GATEWAY_URL: string; // the cloudflared tunnel URL pointing at the FastAPI gateway
	CLIENT_KEYS: string; // comma-separated known app keys, set via wrangler secret
	// (kept as CLIENT_KEYS for the existing secret name; each key belongs to one
	// app and is forwarded to the gateway as x-app-key for role/provider checks)
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		// x-app-key identifies which app is calling — the Worker does a fast,
		// coarse check against the known-keys list; the gateway does the real
		// per-app lookup (role, allowed providers) and rate limiting using
		// this same header (see app/rate_limit.py — Cloudflare's native
		// Workers rate-limiting binding was tried here first, but proved
		// unreliable in testing: 100+ rapid requests against a 30/60s limit
		// never once returned success:false).
		const appKey = request.headers.get('x-app-key');
		const validKeys = env.CLIENT_KEYS.split(',').map((k) => k.trim());

		if (!appKey || !validKeys.includes(appKey)) {
			return new Response(JSON.stringify({ error: 'unauthorized' }), {
				status: 401,
				headers: { 'content-type': 'application/json' },
			});
		}

		const url = new URL(request.url);
		const upstream = new URL(url.pathname + url.search, env.GATEWAY_URL);

		const upstreamRequest = new Request(upstream.toString(), request);
		upstreamRequest.headers.set('x-edge-secret', env.EDGE_SECRET);
		// x-app-key is already present on the original request and passes
		// through untouched to the gateway.

		try {
			return await fetch(upstreamRequest);
		} catch (err) {
			return new Response(JSON.stringify({ error: 'upstream unavailable' }), {
				status: 502,
				headers: { 'content-type': 'application/json' },
			});
		}
	},
} satisfies ExportedHandler<Env>;
