# FarmingOS API reference (v1)

Base path: `/v1`. JSON everywhere. Auth via `Authorization: Bearer <jwt>` except
farmer OTP and channel webhooks. Interactive docs at `/docs` (Swagger) when the
server is running.

## Auth & onboarding
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/auth/otp/request` | — | `{phone}` → `{sent, dev_otp}` (dev returns the code) |
| POST | `/auth/otp/verify` | — | `{phone, code}` → tokens |
| POST | `/auth/staff/login` | — | `{email, password}` → tokens with role claim |
| POST | `/farmers/onboard` | — | one-shot wizard submit (OTP + profile + crops + consent) → tokens |
| GET/PATCH | `/farmers/me` | farmer | profile |
| POST | `/farmers/me/plots` | farmer | add a plot + crops |
| POST | `/farmers/me/consent` | farmer | record PDPA consent |

## Conversation core (channel-agnostic)
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/messages:ingest` | — (rate-limited) | `{channel, external_user_id, modality, text|media_url}` → normalized reply. **Adapters call this.** `modality` may be `text|voice|image`. Voice is transcribed (reply includes `transcript` + a synthesized `reply_media_url`). When assisted mode is on, the reply is a holding message and `assisted=true`. |
| GET | `/conversations/{id}` | — | conversation + message history |

## Agents (direct — portals/testing)
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/agents/price` | — (rate-limited) | `{crop|crop_id, gps_lat, gps_lng, lang}` → Price contract |
| POST | `/agents/crop` | farmer token or `farmer_id` | multipart `image` (+ `crop_id`, `lang`) → Crop contract; persists an Escalation if it escalates |

**Price output contract**
```json
{ "agent":"price","crop":"Tomato",
  "markets":[{"name":"Colombo Manning Market","price_min":170,"price_max":188,
              "net_after_transport":148.1,"distance_km":103.1,"days_old":0}],
  "trend":"flat","recommendation":"go_to:Colombo Manning Market",
  "confidence":1.0,"explanation_localized":"…","escalate":false }
```
**Crop output contract**
```json
{ "agent":"crop","label":"early_blight","confidence":0.67,
  "candidates":[{"label":"early_blight","confidence":0.67}],
  "treatment_steps":["…"],"inputs_needed":["…"],"safety":"…",
  "escalate":false,"diagnosis_case_id":"uuid","treatment_doc_id":"uuid",
  "citations":[{"doc_id":"uuid","title":"Tomato blight management","source":"…","score":null}],
  "explanation_localized":"…" }
```

## Prices, markets, crops (ground-staff portal)
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/crops` · `/markets` | — | reference data (for pickers) |
| POST | `/markets` | admin | create market |
| GET | `/prices?crop&market&date_from&date_to` | ground_staff/admin | list |
| POST | `/prices` | ground_staff/admin | single entry (district-scoped, audited) |
| POST | `/prices:bulk` | ground_staff/admin | CSV: `market_id,crop_id,price_min,price_max,observed_date[,unit]` |
| PATCH | `/prices/{id}` | ground_staff/admin | correct an entry |
| GET | `/prices/coverage` | ground_staff/admin | today's market×crop coverage |

## Knowledge base (admin)
| Method | Path | Auth |
|---|---|---|
| GET/POST | `/kb/docs` | admin |
| PATCH | `/kb/docs/{id}` | admin |
| POST | `/kb/docs/{id}:reindex` | admin |

Only `status="validated"` docs are retrievable by the Crop Doctor (traceability).

## Admin console (Phase 2)
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/admin/settings` | admin | feature flags: `crop_confidence_threshold`, `assisted_mode`, `price_stale_days` |
| PATCH | `/admin/settings` | admin | update flags (audited); agents read them per request |
| GET | `/admin/farmers` | admin | recent farmers |
| GET | `/admin/conversations` | admin | recent conversations |

(KB doc CRUD + reindex are under `/kb/*` above; analytics under `/metrics/*` below.)

## Escalations (officer console)
| Method | Path | Auth |
|---|---|---|
| GET | `/escalations?status&district` | extension_officer/admin (district-scoped) |
| POST | `/escalations/{id}:claim` | extension_officer/admin |
| POST | `/escalations/{id}:resolve` | extension_officer/admin (`{note}`) |

Escalation types: `price` (no data), `crop` (low confidence/unusable photo), `assisted`
(assisted mode — carries the AI's `ai_draft` for the officer to edit & approve).

## Outcomes (north-star)
| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/outcomes` | extension_officer/admin | `{farmer_id, recommended_action?, action_taken, outcome_value?}` → logs an OutcomeLog feeding `/metrics/northstar` |

## Analytics & webhooks
| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/metrics/northstar` | admin | % advised → acted → outcome |
| GET | `/metrics/usage` | admin | conversations, messages, open escalations, cost |
| GET/POST | `/webhooks/whatsapp` | — | verify + inbound (Phase 3 scaffold) |
| POST | `/webhooks/telegram` | — | inbound (Phase 3 scaffold) |
| GET | `/healthz` | — | liveness |
