# SSH To The TJH Lead-Extraction Server

The server is reached at `leads-mkssh.thejobhelpers.com` through Cloudflare. Before SSH
connects, Cloudflare asks you to sign in with your email. Only approved emails get in. A
sign-in lasts 24 hours.

## One-Time Setup

1. Install `cloudflared`:
   - **Windows:** `winget install --id Cloudflare.cloudflared`
   - **macOS:** `brew install cloudflared`
   - **Linux:** see <https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/>
2. Add this to your SSH config (`~/.ssh/config`, on Windows `C:\Users\<you>\.ssh\config`):

   ```
   Host leads-mkssh.thejobhelpers.com
     ProxyCommand cloudflared access ssh --hostname %h
   ```

## Connecting

```
ssh <your-username>@leads-mkssh.thejobhelpers.com
```

The first time each day a browser tab opens. Enter your email, then the code Cloudflare
emails you. SSH then continues with your usual password or key.

VS Code Remote-SSH uses the same SSH config, so pick `leads-mkssh.thejobhelpers.com`
from its host list.

## If It Fails

- **Browser never opens:** copy the URL the terminal prints into a browser.
- **"That account does not have access":** your email isn't on the list. Ask Roshana.
- **Host key warning:** the server's key was copied from the old Azure VM. If you
  connected to the old address before, the key is the same, but the name is new, so
  SSH asks once.
