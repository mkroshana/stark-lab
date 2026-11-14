# NeutralFin Jellyfin Theme

The theme for Jellyfin on `CT 121`. It started as NeutralFin 1.3.0 with Jellyfin-Lucide icons and was later rebuilt on Abyss, with a Netflix-style navbar and hero and an Apple-style design pass.

## Files

| File | Purpose |
| --- | --- |
| `neutralfin.css` | The source. Make every change here. |
| `neutralfin.min.css` | Build output from `build.py`. This is the file that gets deployed. Commit it with the source. |
| `build.py` | Minifies `neutralfin.css` into `neutralfin.min.css`. |
| `deploy.sh` | Builds the theme, copies it into `CT 121` and checks the md5 there. |

## How the Theme Reaches Viewers

The minified theme replaces Jellyfin's own `/usr/share/jellyfin/web/themes/dark/theme.css`. Jellyfin loads that file on every page, the admin dashboard included, so nothing else is needed:

- Dashboard → Branding → Custom CSS is **empty**. Jellyfin skips Branding CSS on the dashboard, and the theme would load twice everywhere else.
- `index.html` and `main.jellyfin.bundle.js` are **stock**. `dpkg -V jellyfin-web` should list only `theme.css`.
- Traefik sends `Cache-Control: no-cache` for `/web/themes/` on both Jellyfin hosts (`traefik-setup/conf.d/jellyfin.yaml`), so browsers pick up a new deploy on their next page load. Opening `10.10.10.121:8096` directly skips Traefik, so a browser there may keep the old copy for a while.

## Making a Change

Run these from this directory in Git Bash. They need ssh access to `root@10.10.10.31`.

1. Edit `neutralfin.css`.
2. `./deploy.sh --stage` builds the theme and copies it to `/web/neutralfin-staging.css`. No page loads that file, so viewers see nothing.
3. Preview it in your own tab only. In the browser console, turn the live theme off and load the staged one:

   ```js
   const live = document.querySelector('link[href*="theme.css"]');
   live.sheet.disabled = true;
   live.after(Object.assign(document.createElement('link'), { rel: 'stylesheet', href: '/web/neutralfin-staging.css?t=' + Date.now() }));
   ```

   A reload brings back the live theme.
4. `./deploy.sh --live` replaces `theme.css`. Other people use this server, and they get the change on their next page load.
5. Commit `neutralfin.css` and `neutralfin.min.css` together.

## After a Jellyfin Update

A `jellyfin-web` package update puts back the stock `theme.css`, so the stock look returns. Run `./deploy.sh --live` again. It finishes by printing `dpkg -V jellyfin-web`, which should list only `theme.css`.

## Going Back to the Stock Look

In `CT 121`, run `apt-get install --reinstall jellyfin-web`. That restores every file in the package, `theme.css` included. `themes/dark/theme.css.orig` is the stock file from Jellyfin 12.0. Don't copy it over a newer version.
