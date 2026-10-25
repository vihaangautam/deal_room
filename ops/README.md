# ops — backups, restore, and the scheduled jobs

Everything here runs on the server, from `/opt/lilkis/ops`. The scripts
read `/opt/lilkis/.env` themselves, so no credential is ever written into
a systemd unit or a crontab.

| | What it does | When |
|---|---|---|
| `backup.sh` | Dump the database, encrypt, upload, prune, verify | Nightly, 02:30 IST |
| `restore.sh` | Put a backup back | By hand |
| `sync-documents.sh` | Copy every document to a second provider | Weekly, Sun 03:30 IST |
| `lilkis-purge.*` | The retention sweep (`app.jobs.purge`) | Daily, 04:00 IST |
| `reset-owner-password.sh` | New temporary password for the owner | When locked out or exposed |
| `reset-for-handover.sh` | Wipe test data and hand over a clean room | **Once, before handover** |

The purge runs *after* the backup, so anything it removes was captured in
that night's dump first.

---

## Install

```bash
sudo apt update && sudo apt install -y awscli gnupg
```

Add to `/opt/lilkis/.env`:

```bash
# Database backups --------------------------------------------------
BACKUP_BUCKET=lilkis-deal-backups        # a DIFFERENT bucket
BACKUP_PASSPHRASE=                       # 32+ random chars, see below
BACKUP_KEEP_DAYS=30

# Backup-only credentials. Optional, and worth doing: without them the
# script falls back to the purge key, which can also delete the live
# documents — one stolen credential would then reach the originals and
# the copies.
BACKUP_ACCESS_KEY_ID=
BACKUP_SECRET_ACCESS_KEY=

# Off-provider document copy ----------------------------------------
DOCS_MIRROR_BUCKET=lilkis-docs-mirror
DOCS_MIRROR_ACCESS_KEY_ID=
DOCS_MIRROR_SECRET_ACCESS_KEY=
DOCS_MIRROR_ENDPOINT=                    # e.g. Cloudflare R2's endpoint
DOCS_MIRROR_REGION=auto
```

Generate the passphrase on the server:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

> **Store that passphrase somewhere other than this server.** A password
> manager, or written down at home. It is the only thing that can open
> the backups, and if the only copy of it is on the machine the backups
> exist to recover, the backups are decoration.

Then the timers:

```bash
sudo cp /opt/lilkis/ops/*.service /opt/lilkis/ops/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lilkis-backup.timer
sudo systemctl enable --now lilkis-sync-documents.timer
sudo systemctl enable --now lilkis-purge.timer
systemctl list-timers 'lilkis-*'
```

Run the first backup by hand rather than waiting for 02:30:

```bash
/opt/lilkis/ops/backup.sh
```

---

## Handing over a clean room

After testing properly — uploads, approvals, deletions, permissions —
and **before** the client puts anything real in:

```bash
/opt/lilkis/ops/reset-for-handover.sh
```

It takes a backup, empties the documents bucket including every version,
rebuilds the database from the migration, and re-creates the owner.

**Before handover, never after.** There is no way to remove your test
uploads and keep someone else's real ones, so running it later destroys
their work. It asks for the bucket name and then the word DESTROY, which
is two more chances to notice than freehand `aws s3 rm` gives you.

---

## The restore drill

**Do this once before real documents go in.** PRD §12 lists it as a
deliverable, and the reason is that a backup nobody has restored is a
file you *hope* is a backup.

```bash
/opt/lilkis/ops/backup.sh            # 1. take one
/opt/lilkis/ops/restore.sh           # 2. list them
/opt/lilkis/ops/restore.sh lilkis_2026....sql.gz.gpg   # 3. put it back
```

Then **sign in through the browser and open a deal.** Row counts prove
the load ran; only signing in proves the restore worked.

Write down how long the whole thing took. That number is your honest
answer when Samir asks what happens if something breaks.

---

## Checking it is still working

```bash
systemctl list-timers 'lilkis-*'              # when each last ran, when next
journalctl -u lilkis-backup -n 40             # last night's output
aws s3 ls s3://${BACKUP_BUCKET}/db/           # are the files actually there
```

The last one is the one that matters. A green timer means the script
ran, not that a backup exists.

---

## What is and is not protected

| Risk | Covered by |
|---|---|
| A file deleted in the app | Archive + retention — recoverable in the UI |
| A bug deleting from the bucket | The app's key has no delete permission |
| Someone deleting an object directly | Bucket versioning |
| The database corrupted, or a bad migration | `backup.sh` → `restore.sh` |
| The VM lost entirely | `backup.sh` + rebuilding from GUIDE.md |
| **The whole AWS account lost or compromised** | **`sync-documents.sh`, and only if the mirror is at another provider** |

That last row is the reason the mirror exists, and the reason it belongs
somewhere the AWS credentials cannot reach. A second bucket in the same
account covers a mistake, not an account.

Still not covered: the documents between the weekly sync and whenever
something goes wrong. Narrow the gap by running the sync more often if
upload volume ever justifies it.
