# Microsoft Graph application permissions

Use application permissions with OAuth 2.0 client credentials. The token scope
is `https://graph.microsoft.com/.default`.

## Recommended least privilege

| Capability | Permission | Notes |
|---|---|---|
| Selected SharePoint sites | `Sites.Selected` | Preferred production baseline |
| Send notification email | `Mail.Send` | Separate from document storage |
| Development fallback | `Files.ReadWrite.All` | Avoid in production when possible |
| Development fallback | `Sites.ReadWrite.All` | Broad; requires risk approval |

`Sites.Selected` alone does not grant access to any site. A SharePoint or Graph
administrator must assign the application `read` or `write` permission to the
specific site after tenant-wide admin consent.

Example administrative sequence (adapt identifiers to the tenant):

```text
Grant admin consent to Sites.Selected
Resolve the target site ID
POST /sites/{site-id}/permissions
Grant the application write access only to that site
Test the connection from the application
```

Email delivery should use a fixed configured sender mailbox. Do not allow event
payloads or frontend input to choose an arbitrary sender.

## Review checklist

- Permission corresponds to an enabled feature.
- Storage and mail permissions are reviewed separately.
- Admin consent was recorded by the organization.
- Only the intended site is assigned.
- Expired client secrets are removed.
- Certificate rotation and ownership are documented.
- Access is revoked before disabling a compromised connection.

The application never assumes consent is present; a `403` is mapped to a safe
authorization/admin-consent error without exposing Graph response details.

