export interface Env {
	EDGE_SECRET: string;
	GATEWAY_URL: string; // the cloudflared tunnel URL pointing at the FastAPI gateway
	CLIENT_KEYS: string; // comma-separated demo client keys, set via wrangler secret
}

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const clientKey = request.headers.get('x-client-key');
		const validKeys = env.CLIENT_KEYS.split(',').map((k) => k.trim());

		if (!clientKey || !validKeys.includes(clientKey)) {
			return new Response(JSON.stringify({ error: 'unauthorized' }), {
				status: 401,
				headers: { 'content-type': 'application/json' },
			});
		}

		const url = new URL(request.url);
		const upstream = new URL(url.pathname + url.search, env.GATEWAY_URL);

		const upstreamRequest = new Request(upstream.toString(), request);
		upstreamRequest.headers.set('x-edge-secret', env.EDGE_SECRET);

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
