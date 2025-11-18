# [COUPLING] [MEDIUM]: Contract coupling deficiency - Missing API versioning across all HTTP endpoints

## Problem Statement

None of the HTTP services (email-agent, sms-agent TypeScript, sms-agent Python) implement API versioning on their endpoints. This creates implicit contract coupling where any API change is potentially breaking, and there's no mechanism for clients to request specific API versions or for services to evolve their APIs independently.

## Current State

**Location**:
- Files: `email-agent/server/server.ts:143-170` (all `/api/*` endpoints)
- Files: `sms-agent/server/index.ts:36-86` (all endpoints)
- Files: `sms-agent-python/server/api.py:122-236` (all FastAPI routes)
- Owner: All service teams

**Coupling Type**: Contract coupling
**Degree**: Missing versioning strategy - implicit v1 contract

**Evidence**:
```typescript
// email-agent/server/server.ts - No versioning
if (url.pathname === '/api/sync' && req.method === 'POST') {
  return handleSyncEndpoint(req);
}

if (url.pathname === '/api/emails/inbox' && req.method === 'GET') {
  return handleInboxEndpoint(req);
}

// sms-agent/server/index.ts - No versioning
if (url.pathname === "/webhook/sms" && req.method === "POST") {
  // ...
}

if (url.pathname === "/dashboard" && req.method === "GET") {
  // ...
}

// sms-agent-python/server/api.py - No versioning
@app.post("/webhook/sms")
async def sms_webhook(webhook_data: WebhookSMS):
    # ...

@app.get("/dashboard")
async def get_dashboard():
    # ...
```

**Missing capabilities**:
- No version in URL path (e.g., `/api/v1/emails`)
- No version in headers (e.g., `Accept: application/vnd.api+json; version=1`)
- No deprecation strategy
- No way to evolve APIs without breaking clients

## Impact Assessment

**Severity**: MEDIUM

**Why This Matters**:
- **Breaking Changes**: Any API modification breaks all clients immediately
- **No Deprecation Path**: Cannot sunset old behavior gracefully
- **Tight Coupling**: Clients and servers must deploy together
- **Innovation Blocked**: Fear of breaking changes prevents API improvements
- **Multi-Client Chaos**: Different clients may need different API versions

**Blast Radius**:
- Modules affected: All API endpoints across all services (15+ endpoints)
- Teams affected: 2 (email-agent, sms-agent)
- Deployment coupling: HIGH - clients and servers tightly coupled

**Risk Factors**:
- Change frequency: MEDIUM - APIs evolve with product features
- Failure probability: HIGH - easy to make breaking change without realizing
- Detection difficulty: MEDIUM - caught in integration testing (if it exists)

## Current Behavior vs. Expected Behavior

**Current**: All APIs operate as implicit v1 with no versioning mechanism, forcing breaking changes on all clients whenever the API evolves.

**Expected**: Explicit versioning strategy allowing multiple API versions to coexist, enabling graceful deprecation and independent evolution of clients and servers.

**Violated Principle(s)**:
- Explicit Contract - API version should be explicit
- Backward Compatibility - no mechanism to maintain it
- Open/Closed Principle - APIs not open for extension, closed for modification

## Remediation Plan

### Recommended Solution

Implement URL path-based versioning with explicit v1 designation and deprecation strategy.

**Design Strategy**:
1. Add `/v1/` prefix to all existing endpoints (making current implicit v1 explicit)
2. Create version routing middleware
3. Establish deprecation policy
4. Document versioning strategy
5. Plan for future v2 when needed

### Specific Steps

1. **Step 1: Define versioning strategy**
   ```markdown
   # API Versioning Strategy

   ## URL Path Versioning
   - Format: `/api/{version}/{resource}`
   - Example: `/api/v1/emails/inbox`
   - Version format: `v{major}` (no minor/patch in URL)

   ## Version Lifecycle
   - New version introduces breaking changes
   - Old version deprecated with 6-month sunset period
   - Deprecation warnings in response headers
   - Documentation must specify supported versions

   ## Breaking Changes
   - Removing a field
   - Changing field type
   - Changing endpoint behavior
   - Renaming endpoints
   ```

2. **Step 2: Implement version routing for email-agent**
   ```typescript
   // server/version-router.ts
   export class VersionRouter {
     private routes = new Map<string, Map<string, Handler>>();

     register(version: string, path: string, handler: Handler) {
       if (!this.routes.has(version)) {
         this.routes.set(version, new Map());
       }
       this.routes.get(version)!.set(path, handler);
     }

     route(req: Request): Response | null {
       const url = new URL(req.url);
       const match = url.pathname.match(/^\/api\/(v\d+)\/(.+)$/);

       if (!match) return null;

       const [_, version, path] = match;
       const versionRoutes = this.routes.get(version);

       if (!versionRoutes) {
         return new Response(
           JSON.stringify({ error: `API version ${version} not supported` }),
           { status: 404, headers: { 'Content-Type': 'application/json' } }
         );
       }

       const handler = versionRoutes.get(path);
       if (!handler) return null;

       return handler(req);
     }
   }

   // server/server.ts
   const versionRouter = new VersionRouter();

   // Register v1 endpoints
   versionRouter.register('v1', 'sync', handleSyncEndpoint);
   versionRouter.register('v1', 'sync/status', handleSyncStatusEndpoint);
   versionRouter.register('v1', 'emails/inbox', handleInboxEndpoint);
   versionRouter.register('v1', 'emails/search', handleSearchEndpoint);
   // ... etc

   async fetch(req: Request) {
     // Try version routing first
     const versionedResponse = versionRouter.route(req);
     if (versionedResponse) return versionedResponse;

     // Legacy unversioned routes (temporary - redirect to v1)
     if (url.pathname.startsWith('/api/') && !url.pathname.includes('/v')) {
       const newPath = url.pathname.replace('/api/', '/api/v1/');
       return new Response(null, {
         status: 308,
         headers: {
           'Location': newPath,
           'X-Deprecated': 'true',
           'X-Deprecation-Message': 'Unversioned APIs deprecated, use /api/v1/ instead'
         }
       });
     }

     // ... other routes
   }
   ```

3. **Step 3: Implement versioning for SMS agents**
   ```typescript
   // sms-agent/server/index.ts
   // Prefix all routes with /v1/
   if (url.pathname === "/v1/webhook/sms" && req.method === "POST") {
     // ...
   }

   if (url.pathname === "/v1/dashboard" && req.method === "GET") {
     // ...
   }

   // Legacy redirects
   if (url.pathname === "/webhook/sms") {
     return Response.redirect("/v1/webhook/sms", 308);
   }
   ```

   ```python
   # sms-agent-python/server/api.py
   from fastapi import APIRouter

   # Create versioned router
   v1_router = APIRouter(prefix="/v1")

   @v1_router.post("/webhook/sms")
   async def sms_webhook(webhook_data: WebhookSMS):
       # ...

   @v1_router.get("/dashboard")
   async def get_dashboard():
       # ...

   app.include_router(v1_router)

   # Legacy redirects
   @app.post("/webhook/sms")
   async def sms_webhook_legacy(webhook_data: WebhookSMS):
       raise HTTPException(
           status_code=308,
           headers={"Location": "/v1/webhook/sms"}
       )
   ```

4. **Step 4: Add deprecation headers middleware**
   ```typescript
   // server/middleware/deprecation.ts
   export function addDeprecationHeaders(
     response: Response,
     isDeprecated: boolean,
     sunsetDate?: Date,
     alternativeUrl?: string
   ): Response {
     if (!isDeprecated) return response;

     const headers = new Headers(response.headers);
     headers.set('Deprecation', 'true');

     if (sunsetDate) {
       headers.set('Sunset', sunsetDate.toUTCString());
     }

     if (alternativeUrl) {
       headers.set('Link', `<${alternativeUrl}>; rel="successor-version"`);
     }

     headers.set(
       'X-API-Deprecation-Info',
       'https://docs.example.com/api-deprecation-policy'
     );

     return new Response(response.body, {
       status: response.status,
       headers
     });
   }
   ```

5. **Step 5: Update clients and documentation**
   ```typescript
   // Update all client code to use versioned endpoints
   const response = await fetch('/api/v1/emails/inbox');

   // Document versioning in OpenAPI/Swagger
   // openapi.yaml
   openapi: 3.0.0
   info:
     title: Email Agent API
     version: 1.0.0
   servers:
     - url: /api/v1
       description: Version 1 (current)
   ```

### Alternative Approaches

**Option A**: Header-based versioning (`Accept: application/vnd.api.v1+json`)
- Pros: URLs stay clean, more RESTful
- Cons: Harder to test, not cache-friendly, requires header manipulation

**Option B**: Query parameter versioning (`/api/emails?version=1`)
- Pros: Easy to implement
- Cons: Easy to forget, pollutes query params, not standard

**Option C**: Subdomain versioning (`v1.api.example.com`)
- Pros: Complete isolation
- Cons: Requires infrastructure changes, SSL cert complexity

**Recommendation**: URL path versioning (Option described above) - simple, visible, cache-friendly, standard practice.

## Acceptance Criteria

- [ ] All API endpoints have explicit version in path (`/api/v1/...` or `/v1/...`)
- [ ] Version routing correctly dispatches to appropriate handlers
- [ ] Legacy unversioned endpoints redirect to v1 with deprecation headers
- [ ] Deprecation headers include sunset date and alternative URL
- [ ] OpenAPI/Swagger docs specify version
- [ ] Client code updated to use versioned endpoints
- [ ] Versioning strategy documented

**Definition of Done**:
- [ ] Version router implemented
- [ ] All endpoints updated to v1
- [ ] Legacy redirects in place
- [ ] Deprecation middleware working
- [ ] API documentation updated
- [ ] Client code migrated
- [ ] Integration tests pass
- [ ] ADR created: "API Versioning Strategy"

## Effort Estimation

**Size**: Small-Medium (3-5 days)

**Reasoning**:
- Router implementation: straightforward
- Endpoint updates: mechanical but numerous
- Client updates: need to find all call sites
- Testing: ensure no regressions

**Estimated Complexity**:
- Version router: 1 day
- Endpoint migration: 1 day
- Client updates: 1 day
- Testing: 1 day
- Documentation: 0.5 days

## Dependencies

**Blocks**:
- Future API changes (should wait for versioning)

**Blocked By**:
- None

**Related Issues**:
- None directly, but enables safer evolution of APIs

## Migration Strategy

**Phase 1**: Add versioned routes alongside existing unversioned routes
**Phase 2**: Update clients to use versioned routes
**Phase 3**: Add redirects from unversioned to versioned
**Phase 4**: Add deprecation warnings to unversioned routes
**Phase 5**: Remove unversioned routes after sunset period

## Prevention Strategy

- [ ] API review checklist: "Is this change backward compatible?"
- [ ] Automated tests: verify version routing works
- [ ] Documentation template: always specify which version
- [ ] OpenAPI spec: enforce version in paths
- [ ] ADR: "API Evolution and Versioning Policy"
- [ ] Team training: when to bump version

## Additional Context

**Related Documentation**:
- REST API versioning best practices
- Semantic Versioning (SemVer)
- HTTP deprecation headers (RFC 8594)

**Historical Context**:
- Services built quickly without versioning considerations
- No breaking changes made yet, so no pain felt
- As services mature, versioning will become critical
- Demo/prototype origins didn't require versioning

**Questions for Discussion**:
- Should we version per-service or have unified API version?
- What's our deprecation timeline? (Suggest 6 months)
- Do we need minor version in URL? (Suggest major only)
- Should webhook endpoints also be versioned?
- How do we handle version in MCP tool definitions?
