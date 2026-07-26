# SharePoint Online setup

Phase 10 integrates only with SharePoint Online document libraries through
Microsoft Graph. Local storage remains the default and continues to work when
Graph is disabled.

## Entra application

1. Register a single-tenant Microsoft Entra application.
2. Record the tenant ID and application/client ID.
3. Development may use a short-lived client secret. Production should upload a
   certificate whose private key is stored outside the repository.
4. Add the minimum application permissions described in
   `microsoft-graph-permissions.md`, grant admin consent, and explicitly grant
   the application access to the selected site.
5. Never configure delegated username/password authentication.

## Application configuration

Copy `.env.development.example` or `.env.production.example`. Set
`MICROSOFT_GRAPH_ENABLED=true` only after all required values are present.
The application accepts either:

- `MICROSOFT_GRAPH_AUTH_MODE=client_secret`, with the secret supplied by the
  configured secret provider; or
- `MICROSOFT_GRAPH_AUTH_MODE=certificate`, with a protected PEM/PFX path and
  password supplied at runtime.

No secret is persisted in `sharepoint_connections`.

## Site and library

Set either `SHAREPOINT_SITE_ID` directly or the hostname/path pair, for example
`contoso.sharepoint.com` and `/sites/ControlledDocuments`. Resolve and test the
site through the backend connection page. Select the document-library drive,
then configure `SHAREPOINT_ROOT_FOLDER_PATH=DocumentCompliance`.

Folder browsing is constrained to the configured site and drive. The browser is
not a tenant-wide SharePoint explorer.

## Initial verification

1. Create the connection as a user with `sharepoint:configure`.
2. Run **Test connection** and verify authentication, site, drive, and root
   folder separately.
3. Create deterministic folder and metadata mappings.
4. Create an outbound-only sync profile with conflict policy `MANUAL`.
5. Push a generated sample document.
6. Confirm remote metadata and download it through the authenticated backend.
7. Enable delta sync and webhooks only after full reconciliation succeeds.

Temporary Graph download URLs are never stored or returned to the browser.

## Delete and restore semantics

Application soft delete does not call the SharePoint recycle-bin restore API.
It moves the item with Graph `PATCH` into the configured
`documents/deleted/...` namespace and records its prior storage key. Explicit
application restore moves the same item back. This preserves the Phase 5
soft-delete contract for `LOCAL`, `SHAREPOINT`, and `HYBRID` storage.

`SharePointStorageProvider.supports_restore` remains `false` specifically for
provider-native recycle-bin restore. Microsoft Graph v1.0 `driveItem: restore`
supports OneDrive Personal, not work/school SharePoint drives. The v1.0
`recycleBin` resource applies to SharePoint Embedded containers, and the
corresponding restore operation remains beta. Production code therefore never
calls `/beta` or claims native SharePoint Online recycle-bin restore support.

References:

- <https://learn.microsoft.com/graph/api/driveitem-restore?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/resources/recyclebin?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/driveitem-move?view=graph-rest-1.0>
- <https://learn.microsoft.com/graph/api/driveitem-delete?view=graph-rest-1.0>

Graph `DELETE` sends a drive item to the recycle bin. Retention cleanup may
remove the application row after an approved policy, but that is not a
guarantee of physical purge from Microsoft 365. The irreversible
`permanentDelete` operation is intentionally not used without a separately
approved retention policy and permission review.
