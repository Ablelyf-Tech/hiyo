# Hiyo Universal Connector

One connector registration model, one credential policy and one execution/evidence interface support multiple HTTP-based protocols:

| Protocol | Request format | Discovery | Constraints |
| --- | --- | --- | --- |
| REST | GET or JSON POST/PUT/PATCH | OpenAPI `paths` | Configure the provider's resource paths and permissions |
| GraphQL | POST JSON `query` + `variables` | Explicitly approved read-only introspection | Escape literal GraphQL `$variables` as `$$variables` in a Hiyo string template |
| SOAP | POST XML | WSDL operation inspection | XML input values are escaped; DTD/entity declarations are rejected |
| Webhook | POST JSON | No universal schema; user-configured endpoint | Every outbound delivery requires approval |

HubSpot can use `https://api.hubapi.com` with a scoped private-app bearer token and `/crm/v3/...` paths. SAP OData can use the customer's authorized HTTPS tenant/service endpoint, with its specific API permissions and payload schema. A SAP tenant URL cannot be guessed from the product name. No real HubSpot or SAP request has been validated here.

## Register

Use Connections → Universal connector in the private local app. Provide a display name, HTTPS base URL, protocol, auth scheme and a credential **variable name**, e.g. `HIYO_CONNECTOR_HUBSPOT`. Do not enter secret values in the UI. The operator configures the binding securely and adds the exact hostname to `HIYO_CONNECTOR_HOSTS`, plus the managed environment's network policy when applicable.

Supported auth forms: bearer, pre-encoded Basic, scoped API-key header and unauthenticated APIs. Access-token refresh, OAuth consent, service-to-service certificates and unusual vendor signing schemes need additional provider-specific work. Redirects are rejected, and credentials are not forwarded to another host. Private/reserved IP literals and localhost URLs are rejected. Private SAP networks need an authorized hostname and supported organization/VPN route; this release does not install a VPN or bypass egress policy.

## Map and approve

A workflow connector step chooses a registered connector, method, endpoint path and JSON/XML body. Path substitutions are URL-escaped. JSON is parsed before values are substituted into string fields, so input text cannot inject additional JSON fields. SOAP values are XML-escaped. Workflow output references use `$name` or `${name}`; output IDs must refer to prior steps.

Schema discovery API: `POST /api/automation/connectors/{id}/discover` with `approve_external_request: true` and the provider's spec path. This performs a real external request only after explicit consent. OpenAPI, GraphQL or WSDL must actually be available at that endpoint. Discovery output is capped and does not authorize executing every discovered action.

All connected-system calls pause for explicit approval. A successful HTTP response records request success, not end-to-end business correctness. Verify the provider's returned record and domain semantics. On timeout or crash, an external service might already have accepted the request; inspect its state before resuming. This release does not guarantee exactly-once delivery to arbitrary third parties.

## Scope boundary

No single connector can access a system that provides no accessible interface or required permission. Databases, file shares, industrial buses, UI-only software and proprietary protocols need distinct protocol adapters. The framework can be extended; those adapters are not shipped as functioning capabilities in this release.
