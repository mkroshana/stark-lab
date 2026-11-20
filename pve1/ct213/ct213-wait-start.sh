#!/bin/bash
# Start CT 213 (thejobhelpers-vps) only once its data disks on the Unraid
# LeadData NFS share are reachable. After a power cut Unraid boots more
# slowly than pve1, and starting the CT against a missing share fails.
# Installed at /usr/local/sbin/ct213-wait-start.sh, run by
# ct213-wait-start.service. CT 213 has onboot=0 on purpose.
set -u

CTID=213
STORAGE=LeadData
TRIES=180   # 180 x 10 s = 30 minutes

for _ in $(seq 1 "$TRIES"); do
	# pvesm checks that the NFS server answers before reporting the
	# storage active, so we never stat a hard mount on a dead server.
	if pvesm status --storage "$STORAGE" 2>/dev/null | awk 'NR==2 { exit !($3 == "active") }'; then
		if pct status "$CTID" | grep -q running; then
			echo "CT $CTID already running"
			exit 0
		fi
		echo "$STORAGE active, starting CT $CTID"
		exec pct start "$CTID"
	fi
	sleep 10
done

echo "$STORAGE not active after 30 minutes; CT $CTID not started" >&2
exit 1
