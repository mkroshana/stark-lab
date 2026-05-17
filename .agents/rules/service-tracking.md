# Service Tracking Rule

**CRITICAL REQUIREMENT FOR AI ASSISTANTS:**
Whenever a new homelab service is added to or removed from the Traefik infrastructure (`traefik-setup/conf.d/`), you **MUST ALWAYS** update the master service tracking documentation located at `D:\Development\service_links.md`.

### Required Updates in `D:\Development\service_links.md`:
1. **Public Access Table**: Add or remove the service if it is publicly exposed via Cloudflare.
2. **Local Access Table**: Add or remove the service from the LAN tracking table.
3. **Backend Details Table**: Add or remove the VM/CT ID, internal IP address, and port.
4. **Summary Note**: Update the total DNS records count at the bottom of the document.
