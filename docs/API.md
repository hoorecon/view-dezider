# View Dezider API (OpenAPI-style)

Base URL: `http://localhost:8080/api`

## Auth
### POST /auth/register
Create user and return JWT.

**Request**
```json
{ "email": "admin@org.com", "password": "secret", "role": "ADMIN" }
```

**Response**
```json
{ "token": "jwt" }
```

### POST /auth/login
Authenticate and return JWT.

## Projects
### GET /projects
List projects.

### POST /projects
Create project.

**Request**
```json
{ "name": "LMS Purchase", "description": "Evaluate vendors" }
```

### GET /projects/{projectId}
Get project.

### POST /projects/{projectId}/factor-groups
Add factor group.

```json
{ "code": "A1", "name": "Strategy", "weight": 85 }
```

### POST /projects/factor-groups/{factorGroupId}/sub-factors
Add sub-factor.

```json
{ "code": "1.1", "name": "Strategic alignment", "weightPercent": 100 }
```

### POST /projects/{projectId}/gates
Add gate.

```json
{ "factorGroupId": 1, "gateType": "HARD", "mode": "FLAG_ONLY", "threshold": 6, "note": "Security minimum" }
```

### POST /projects/{projectId}/options
Add option.

```json
{ "name": "Vendor Alpha", "description": "Cloud-first" }
```

## Scoring
### POST /options/{optionId}/scores
Set score for sub-factor.

```json
{ "subFactorId": 10, "score": 7 }
```

## Results
### POST /projects/{projectId}/compute
Compute and return results.

### GET /projects/{projectId}/export
Return computed results (JSON export).
