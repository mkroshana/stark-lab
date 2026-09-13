# Jellyfin Themes

This directory contains the self-contained base theme for Jellyfin, sourced from **NeutralFin v1.3.0** with **Jellyfin-Lucide** icons.

## Files

| File | Purpose |
| --- | --- |
| 
eutralfin.css | Unminified, structured source with commented sections, including Lucide icon mappings. Use this file to make changes one by one. |
| 
eutralfin.min.css | Minified all-in-one stylesheet for direct pasting into Jellyfin's custom CSS box. |
| jellyfin-lucide.css | Standalone Lucide icons stylesheet for Jellyfin. |

## How to Apply

### Server-wide (All Users)

1. Open Jellyfin Web.
2. Navigate to **Administration → Dashboard → General** (or **Branding**).
3. Scroll down to the **Custom CSS** field.
4. Paste the contents of 
eutralfin.min.css (or 
eutralfin.css).
5. Click **Save** and perform a hard refresh (Ctrl + F5).

### Per-User (Client-side Only)

1. Click your user avatar in the top right corner.
2. Select **Settings → Display**.
3. Scroll down to the **Custom CSS** field.
4. Paste the theme CSS and click **Save**.

## Incremental Customization Workflow

1. Locate the component or variable you want to modify in 
eutralfin.css (e.g. :root variables, cards, headers, OSD player).
2. Apply and test the change incrementally.
3. Once satisfied, update or minify into 
eutralfin.min.css for deployment.
