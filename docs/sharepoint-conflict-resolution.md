# SharePoint conflict resolution

Conflicts are created when local hashes/business timestamps and remote
eTags/storage timestamps show incompatible changes. Supported types include
both-modified, delete-versus-modify, metadata/path conflicts, duplicate remote
items, hash mismatch, and version mismatch.

## Manual workflow

1. Open the conflict within the permitted department scope.
2. Compare bounded local and remote metadata, hashes/eTags, sizes, timestamps,
   and actor display names.
3. Assign the conflict when additional review is needed.
4. Select a resolution and provide a mandatory comment.
5. The backend rechecks optimistic concurrency before applying the resolution.
6. The operation and resulting file/version IDs are audit logged.

## Resolution semantics

- `KEEP_LOCAL`: uploads the current local file as a new remote storage version.
- `KEEP_REMOTE`: downloads through the backend and creates internal file
  history; it does not rewrite an existing business revision in place.
- `KEEP_BOTH`: creates a safely suffixed copy and preserves both sides.
- `MERGE_METADATA`: applies only registered metadata transformers.
- `IGNORE_REMOTE_CHANGE` / `IGNORE_LOCAL_CHANGE`: records the decision without
  deleting either history.

Profiles using `MANUAL` never overwrite automatically. `APPLICATION_WINS`,
`SHAREPOINT_WINS`, and `LATEST_MODIFIED_WINS` require explicit administrative
configuration and still preserve history. `CREATE_COPY` is the safest automated
option when both contents must remain accessible.

Raw Graph tokens, delta links, webhook client state, and temporary download URLs
are never shown on the conflict page.

