#!/bin/bash
#description=Daily ZFS snapshot of spinning-disks/LeadData (CT 213 data disks on pve1), keeps the newest 7
#arrayStarted=true
# Unraid User Scripts: /boot/config/plugins/user.scripts/scripts/leaddata-snapshots/script
# Schedule: custom "30 2 * * *". Snapshots are crash-consistent (CT 213
# keeps running); Postgres and SQLite recover from that like a power cut.
# Restore one file: /mnt/spinning-disks/LeadData/.zfs/snapshot/<name>/images/213/
# holds the raw disk images; loop-mount one read-only on pve1 to copy from it.

DS=spinning-disks/LeadData
KEEP=7
NOW=$(date +%Y-%m-%d_%H%M)

zfs snapshot "$DS@auto-daily-$NOW" && echo "created $DS@auto-daily-$NOW"

zfs list -H -t snapshot -o name -s creation "$DS" | grep "@auto-daily-" | head -n -"$KEEP" |
	while read -r snap; do
		zfs destroy "$snap" && echo "destroyed $snap"
	done

zfs list -t snapshot -o name,used,refer -s creation "$DS"
