# GitHub Pages dashboard preview

The `gh-pages` branch contains a prebuilt, public **UI preview** of the dashboard. It uses browser storage only. It has no Python backend connection, no Codex execution, no secrets, no real test evidence and no billing. A visible banner identifies the preview, and its sample backlog starts entirely queued.

The installed application's normal production build still requires the private local API and authentication. Public preview mode is enabled only at build time by `VITE_DEMO_MODE=true`; it cannot be enabled through a URL or runtime API setting.

## One-time repository setting

If Pages is not already enabled, a repository administrator must open:

https://github.com/Ablelyf-Tech/hiyo/settings/pages

Under **Build and deployment**, choose **Deploy from a branch**, select **gh-pages**, choose **/ (root)**, and save. GitHub then builds the site. If GitHub requires an account plan upgrade for a private repository, do not purchase or change repository visibility automatically; the administrator must decide.

Expected site address after GitHub confirms deployment:

https://ablelyf-tech.github.io/hiyo/

The source and deployment branch can be pushed with existing Git authentication. The current cloud environment denies the GitHub REST API host, so Pages activation cannot be performed from this environment. A pushed branch is not proof of a deployed public site.

## Rebuild the preview

From `dashboard/`, install the locked dependencies and set the preview flag for the build:

```powershell
npm.cmd ci
$env:VITE_DEMO_MODE = 'true'
npm.cmd run build -- --outDir dist-preview
Remove-Item Env:VITE_DEMO_MODE
```

On Linux/macOS: `VITE_DEMO_MODE=true npm run build -- --outDir dist-preview`.

Publish **only the contents of `dashboard/dist-preview/`**, plus an empty `.nojekyll` file, to `gh-pages`. Never include the Python state directory, access token, `.env`, Codex credentials or logs. The Vite base is relative so assets work below `/hiyo/`. Use the normal `npm run build` command without the preview flag for the installed private application.

## Verified preview behavior

- Seven frontend tests pass, including no invented executions, denied model starts and valid browser-only task creation.
- Both the public-preview and private-app production builds pass.
- Chromium smoke checks pass: no login needed for preview, task creation, persistence on reload, preview-only evidence, disabled worker start, no controller API requests, no JavaScript errors, and no horizontal overflow at 390px.
- Public GitHub Pages deployment is unverified until GitHub enables and serves the branch.
