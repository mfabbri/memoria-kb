# External Data Root

`memoria-workspace` is a descriptor repository. It must not contain the real Me.Mo.Ri.a data corpus.

The operational data root is external:

```text
P:\Comune\Me.Mo.Ri.a
```

## Path resolution order

Tools should resolve the data root in this order:

1. explicit CLI argument, for example `--data-root "P:\Comune\Me.Mo.Ri.a"`;
2. environment variable `MEMORIA_DATA_ROOT`;
3. `memoria-workspace/manifest.yml` with `workspace.provider: local` and
   `workspace.root`;
4. legacy `data_root.windows_path` in `memoria-workspace/manifest.yml`;
5. fallback to the documented default path above.

The manifest may describe future providers such as pCloud with a
`credentials_ref`, but it must not store tokens or credentials.

## Workspace provider selection

The workspace backend can be selected without code changes:

```dotenv
MEMORIA_WORKSPACE_PROVIDER=local
MEMORIA_DATA_ROOT=P:\Comune\Me.Mo.Ri.a
```

For the first pCloud read-only integration, use a local `.env` file that is not
committed. Before OAuth approval, only the app credentials are needed:

```dotenv
MEMORIA_WORKSPACE_PROVIDER=pcloud
MEMORIA_PCLOUD_APP_NAME=MemoriaStorage
MEMORIA_PCLOUD_CLIENT_ID=<clientid>
MEMORIA_PCLOUD_CLIENT_SECRET=<client-secret>
MEMORIA_PCLOUD_API_HOST=eapi.pcloud.com
MEMORIA_PCLOUD_ROOT=/MeMoRiA
MEMORIA_PCLOUD_FOLDER_ID=<optional-folderid>
```

The pCloud developer console provides the app name, `client_id` and
`client_secret`. Those values identify the OAuth app; they are not enough by
themselves to call file/folder APIs. Generate the authorization URL with:

```powershell
memoria workspace pcloud-auth-url
```

After approval, pCloud returns an authorization `code`; exchange it with
`oauth2_token` using `client_id`, `client_secret` and `code`, then store the
returned bearer token in the same local `.env`:

```dotenv
MEMORIA_PCLOUD_ACCESS_TOKEN=<token returned by oauth2_token>
```

The CLI can do the exchange and update the local `.env` without printing the
token:

```powershell
memoria workspace pcloud-exchange-code --code <authorization-code> --save-env
```

The default secret variable names are declared in `manifest.yml` as
`client_id_ref`, `client_secret_ref` and `access_token_ref`. They can be renamed
with `MEMORIA_PCLOUD_CLIENT_ID_REF`, `MEMORIA_PCLOUD_CLIENT_SECRET_REF` and
`MEMORIA_PCLOUD_ACCESS_TOKEN_REF` if different local secret names are needed.
For OAuth tokens, API calls pass the bearer as the pCloud global parameter
`access_token`; the older `auth` parameter is only for username/password login
tokens.

### App access mode and existing folders

Before approving the OAuth request, verify the app's **Folder access** mode in
the pCloud developer console. `Specific app folder` grants the token access
only to the dedicated folder created under `Apps`; it does not grant access to
an existing folder elsewhere in the account, even when the browser and OAuth
account are the same. If the setting is disabled after app creation, the app
cannot be converted from this mode in the console; ask pCloud support to
enable `All folders` or create an equivalent app with that access mode.

When diagnosing a folder ID, test the API root and the target with
`listfolder` before changing paths or creating anything. A successful OAuth
authentication does not prove that the token can see the intended folder:
`2005` means that the directory is not present in the namespace visible to the
token, while `2002` from `createfolder` means that the requested parent
directory is not present. Do not use a temporary write as the first diagnostic
and never store tokens in the repository.

The pCloud backend is read-only in T26: standard tests use mock HTTP, and live
checks must be explicitly requested.

## Data policy

- Real PDFs, scans, OCR outputs, generated JSON-LD, review dashboards and backups remain under `P:\Comune\Me.Mo.Ri.a`.
- The Git repository stores only configuration, manifests, templates and validation scripts.
- Never commit personal, archival or licensed source documents unless explicitly approved.
