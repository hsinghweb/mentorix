# API Versioning Strategy

## Current State

All Mentorix API routes are currently unversioned:
- `/auth/login`, `/auth/signup`
- `/onboarding/diagnostic`, `/onboarding/submit`
- `/learning/dashboard/{id}`, `/learning/test/submit`
- `/admin/overview`, `/health/status`

## Recommended Strategy: URI Path Versioning

### Phase 1: Add Version Prefix (Non-Breaking)

Add `/v1/` prefix to all routes while keeping existing unversioned routes as aliases:

```python
# main.py
app.include_router(auth_router, prefix="/v1/auth")
app.include_router(auth_router, prefix="/auth")  # backward compat
```

### Phase 2: Frontend Adoption

Update `app.js` API base configuration:
```javascript
const API_VERSION = "v1";
function getApiBase() {
  return `${baseUrl}/${API_VERSION}`;
}
```

### Phase 3: Breaking Changes

When introducing breaking changes in the future:
1. Create `/v2/` routes with new schemas
2. Keep `/v1/` routes working with deprecation headers
3. Add `Sunset: <date>` HTTP header to v1 responses
4. Log v1 usage to track migration progress

## Versioning Rules

- **Patch changes** (bug fixes, new optional fields): Same version
- **Minor changes** (new endpoints, new optional params): Same version  
- **Breaking changes** (removed fields, changed types, renamed endpoints): New version
