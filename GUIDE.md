# Taking the Lilkis Deal Room live

A step-by-step path from "it runs on my laptop" to "Samir uses it at
work". Written on the assumption you have not done this before.

Work through it in order. Each phase ends with something you can check,
and nothing in a later phase depends on you having guessed right in an
earlier one.

**Terms, once:** a *tenancy* is your whole Oracle account. A *compartment*
is a folder inside it for organising resources. A *bucket* is where files
live. A *VM* (or *instance*) is the computer in Oracle's data centre that
runs the app. A *tunnel* is how the internet reaches that computer without
opening any ports on it.

---

## Phase 0. The one decision to make before anything else

**Read this phase. Do not skip it.** It is the only part of this document
where getting it wrong loses documents.

### The problem

Oracle's Free Tier comes in two states, and people confuse them:

| | What it is |
|---|---|
| **Free Trial** | 30 days with US$300 of credits. A countdown. |
| **Always Free** | A permanent set of small resources — 2 OCPUs, 12 GB RAM, 20 GB object storage, 200 GB disk. |

When a Free Trial ends, the account drops to Always Free only. Oracle's
documentation on what happens to your files at that moment:

> "If you are using more than the 20-GB limit when your Free Trial ends,
> all of your objects will be deleted."

Not archived. Not frozen. Deleted.

There is a second clause. Oracle may **reclaim idle compute instances** —
idle meaning 95th-percentile CPU under 20%, network under 20% and memory
under 20%, over 7 days. A deal room that three people open a few times a
week meets that definition comfortably.

And the limits move. In June 2026 Oracle halved the Always Free Ampere
allowance from 4 OCPUs / 24 GB to 2 OCPUs / 12 GB, and users were given
until August to comply. There was no advance announcement.

### The fix

**Upgrade the account to Pay As You Go on day one. Do not stay on the
Free Trial.**

This sounds like it contradicts "cost nil". It does not:

- Always Free allowances **still apply** on a Pay As You Go account. The
  20 GB of object storage and the 2 OCPU / 12 GB VM remain free.
- What you lose is the trial *expiry*, and with it the clause that
  deletes your objects.
- If you ever exceed 20 GB, you are billed for the excess at roughly
  US$0.0255 per GB per month — about ₹2 per GB. Going to 50 GB costs
  under ₹70 a month. Verify the current rate for your region on Oracle's
  price list; the point is the order of magnitude, not the exact figure.

So: a card on file, a bill of approximately zero, and no deletion clause.
That is the trade, and for client documents in a SEBI-regulated room it
is not a close call.

**Set a budget alert anyway** (Phase 2, step 7). The thing you are
guarding against is an accident, not the normal bill.

### What actually protects you

The provider matters less than these three, in this order:

1. **The documents exist in two places, on two different providers.** If
   all your copies can be destroyed by one account going wrong, one
   account going wrong destroys everything. This is Phase 7, and it is
   the phase that protects your job.
2. **The application's key cannot delete anything.** Already built: the
   app holds a read/write key with no delete permission, and only the
   purge job holds a key that can delete. A bug in the app cannot destroy
   a document, because the credential it holds is not allowed to.
3. **Nothing is ever hard-deleted from the app.** Already built: PRD Goal
   G5. Deleting moves a file to the Archive, where it sits for the
   retention window and can be recovered.

Phases 2 and 7 are what turn 1 into a fact rather than an intention.

---

## Phase 1. Create the Oracle account

**Time:** 20 minutes, plus up to a few hours for verification.

1. Go to <https://signup.cloud.oracle.com>.
2. Choose your country as **India**, and give a real email you control.
3. For **home region**, choose **India South (Hyderabad)** or **India
   West (Mumbai)**.

   > This cannot be changed later. Always Free compute only exists in
   > your home region. Pick the one nearer to you; for Lilkis either is
   > fine.

4. Enter your details and verify by card. Oracle takes a small temporary
   authorisation (around ₹100) and reverses it. This is identity
   verification, not a charge.
5. Wait for the "your account is ready" email.

**Check:** you can sign in at <https://cloud.oracle.com> and see the
console.

### Then upgrade to Pay As You Go

Per Phase 0. Do this now, while you remember.

1. In the console, open the **☰ menu → Billing & Cost Management →
   Upgrade and Payment**.
2. Choose **Upgrade to Pay As You Go**.
3. Confirm.

**Check:** the orange "Free Trial — N days left" banner at the top of the
console is gone.

> If you would rather test on the trial first and upgrade later, that is
> survivable **as long as you upgrade before the 30 days are up**. Put a
> reminder in your calendar for day 20. If the trial lapses with more
> than 20 GB stored, the objects go.

---

## Phase 2. Object storage — where the documents live

**Time:** 30 minutes.

### 2.1 Find your namespace

Every tenancy has an **object storage namespace** — a short random
string. You need it for the endpoint URL.

1. Click the **profile icon** (top right) → **Tenancy: \<your tenancy\>**.
2. Copy the **Object storage namespace** value.

Write it down. It looks like `axbz9k1mnopq`, not like your company name.

### 2.2 Create the bucket

1. **☰ menu → Storage → Buckets**.
2. Check the **Compartment** dropdown on the left says `(root)`. It is
   fine to use root for a deployment this size.
3. **Create Bucket**:
   - **Name:** `lilkis-deals`
   - **Default storage tier:** Standard
   - **Encryption:** Encrypt using Oracle managed keys
4. **Create**.

### 2.3 Turn on versioning — do this before a single file is uploaded

1. Open the bucket you just made.
2. Under **Object Versioning**, click **Edit** → **Enable Versioning**.

> This is your undo button at the storage layer. With versioning on,
> overwriting or deleting an object keeps the previous version, and it
> can be brought back from the console. It is the difference between
> "a file was destroyed" and "a file needs restoring". It costs you the
> storage of the old versions, which for this app is negligible.

### 2.4 Create the application user

The app gets its own user so its key can be restricted.

1. **☰ menu → Identity & Security → Domains → Default domain → Users**.
2. **Create user**:
   - **Username:** `lilkis-app`
   - **First/Last name:** `Lilkis`, `App`
   - Untick **Use the email address as the username** and give it
     something like `lilkis-app@lilkis.in`
3. **Create**.

Repeat for a second user named `lilkis-purge`.

> Two users, because they get different permissions. `lilkis-app` will
> not be allowed to delete. `lilkis-purge` will. That separation is the
> control described in Phase 0.

### 2.5 Write the policy that enforces no-delete

1. **☰ menu → Identity & Security → Domains → Default domain → Groups**.
2. Create a group `lilkis-app-grp`, add the user `lilkis-app`.
3. Create a group `lilkis-purge-grp`, add the user `lilkis-purge`.
4. **☰ menu → Identity & Security → Policies** → **Create Policy**.
   - **Name:** `lilkis-storage`
   - **Compartment:** root
   - Switch to **Show manual editor** and paste:

```
Allow group lilkis-app-grp to read buckets in tenancy where target.bucket.name = 'lilkis-deals'
Allow group lilkis-app-grp to manage objects in tenancy where all {target.bucket.name = 'lilkis-deals', any {request.permission = 'OBJECT_CREATE', request.permission = 'OBJECT_READ', request.permission = 'OBJECT_INSPECT', request.permission = 'OBJECT_OVERWRITE'}}
Allow group lilkis-purge-grp to read buckets in tenancy where target.bucket.name = 'lilkis-deals'
Allow group lilkis-purge-grp to manage objects in tenancy where target.bucket.name = 'lilkis-deals'
```

5. **Create**.

> Read the first `manage objects` line carefully: it lists the
> permissions granted, and `OBJECT_DELETE` is not among them. That is
> the whole point. The application code calls the right client, but it
> is this policy that makes it true — code can have bugs, a policy
> cannot be argued with.

### 2.6 Generate the two key pairs

For **each** of `lilkis-app` and `lilkis-purge`:

1. **Identity & Security → Domains → Default domain → Users →** click the
   user.
2. Left menu → **Customer secret keys** → **Generate secret key**.
3. Name it `lilkis-app-key` (or `lilkis-purge-key`) → **Generate**.
4. **Copy the secret now.** It is shown once and never again. If you lose
   it, delete the key and generate another.
5. Close the dialog. The **Access key** is listed in the table.

You now have four values. Keep them somewhere safe — a password manager,
not a text file on the desktop, and **not** in the repository.

> A user can hold at most two secret keys at a time. That is deliberate,
> so you can rotate: generate a second, switch over, delete the first.

### 2.7 Set a budget alert

1. **☰ menu → Billing & Cost Management → Budgets** → **Create Budget**.
2. Target the root compartment, monthly amount **₹500**, alert at **50%**.
3. Give your email address.

₹500 is far above what this should ever cost. It is there to tell you
something has gone wrong, not to cap spending.

---

## Phase 3. Test the storage from your laptop — before anything is deployed

**This is the step that matters most right now.** The application's
storage layer has only ever run against S3Mock, a local fake. Real OCI
will differ in at least signing and possibly in multipart uploads. Better
to find that out here than on a server.

1. Open `.env` in the project root. Fill in:

```
OCI_ENDPOINT_URL=https://<your-namespace>.compat.objectstorage.<your-region>.oraclecloud.com
OCI_BUCKET=lilkis-deals
OCI_ACCESS_KEY_ID=<lilkis-app access key>
OCI_SECRET_ACCESS_KEY=<lilkis-app secret>
OCI_ADMIN_ACCESS_KEY_ID=<lilkis-purge access key>
OCI_ADMIN_SECRET_ACCESS_KEY=<lilkis-purge secret>
```

   Region is `ap-hyderabad-1` or `ap-mumbai-1`. So the endpoint looks
   like:
   `https://axbz9k1mnopq.compat.objectstorage.ap-hyderabad-1.oraclecloud.com`

2. `.env` is gitignored. Confirm with `git status` that it does not
   appear. If it ever does, stop and tell me.

3. Run the check:

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.checks.storage_check
```

   Or tell me it is filled in and I will run it and fix what it turns up.

It prints a line per check and exits non-zero if any fail. Against the
local S3Mock it reports **4 passed, 1 failed** — the no-delete check
cannot pass locally, because S3Mock has no permissions model at all and
both keys are the same unrestricted access. That is the honest state of
things: *the no-delete control has never been true in development.* It
becomes true the moment the policy from 2.5 is in place, and this check
is how you find out that it is.

**What we are checking:**

- Upload, download and presigned URLs work against OCI's S3 API
- Multipart (chunked) upload works — this is how a 2 GB file gets in
- The `Expect: 100-continue` workaround in `storage.py`, which exists
  for S3Mock, does the right thing against OCI
- **The app's key genuinely cannot delete.** If a delete succeeds with
  the app key, the policy in 2.5 is wrong and we fix it before going
  further.

Do not move to Phase 4 until this passes.

---

## Phase 4. The server

**Time:** 45 minutes.

### 4.1 Create the VM

1. **☰ menu → Compute → Instances** → **Create instance**.
2. **Name:** `lilkis-prod`
3. **Image and shape → Edit**:
   - **Image:** Ubuntu 22.04 (Canonical Ubuntu)
   - **Shape → Ampere → VM.Standard.A1.Flex**
   - **OCPUs: 2**, **Memory: 12 GB** — the whole Always Free allowance
4. **Networking:** accept the defaults. It creates a VCN for you.
   - Leave **Assign a public IPv4 address** as **Yes** for now; you can
     remove it after the tunnel works.
5. **Add SSH keys → Generate a key pair for me** → **download both**.
   Keep the private key safe; it is how you get in, and it is not
   recoverable.
6. **Create.**

> **"Out of host capacity"** is common on Ampere. It means that
> availability domain has no free Arm capacity right now. Try a
> different availability domain in the dropdown, or retry in a few
> hours. It is not something you have done wrong.

### 4.2 Connect

From PowerShell on your laptop:

```powershell
icacls .\ssh-key-xxxx.key /inheritance:r /grant:r "$($env:USERNAME):(R)"
ssh -i .\ssh-key-xxxx.key ubuntu@<the public IP>
```

**Check:** you get a shell prompt ending in `@lilkis-prod`.

### 4.3 Install Docker

```bash
sudo apt update && sudo apt upgrade -y
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit
```

Reconnect (the group change needs a new session), then:

```bash
docker run --rm hello-world
```

**Check:** "Hello from Docker!".

### 4.4 Get the code onto it

```bash
sudo mkdir -p /opt/lilkis && sudo chown ubuntu:ubuntu /opt/lilkis
git clone https://github.com/vihaangautam/deal_room.git /opt/lilkis
cd /opt/lilkis
```

> The repository is public. Before the first real client document goes
> in, make it private — GitHub → Settings → Danger Zone → Change
> visibility. There are no secrets in it, but a document room's source
> is not something to advertise.

---

## Phase 5. Configure and deploy

### 5.1 The environment file

```bash
cd /opt/lilkis
cp .env.production.example .env
nano .env
chmod 600 .env
```

Fill in every blank. Generate the two database passwords and the secret
key **on the server**, not from your head:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # run three times
```

- `POSTGRES_ADMIN_PASSWORD` — one of them
- `POSTGRES_APP_PASSWORD` — another
- `SECRET_KEY` — the third
- the four OCI values from Phase 2.6
- `PUBLIC_ORIGIN` — the URL people will type, e.g.
  `https://deals.lilkis.in`
- `CLOUDFLARE_TUNNEL_TOKEN` — Phase 6, come back for it

**One trap:** `POSTGRES_APP_PASSWORD` must also be written into
`db-init/01-app-role.sql`. That script runs **once**, when the database
volume is first created. If the two disagree, the API cannot connect, and
changing `.env` afterwards will not fix it — the role already exists with
the old password.

```bash
nano db-init/01-app-role.sql   # put the same password in
```

### 5.2 Cloudflare tunnel

See Phase 6, then return here.

### 5.3 First start

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

The build takes 5–10 minutes on 2 Arm cores. All services should read
`running`; postgres should read `healthy`.

### 5.4 Create the schema

The containers do **not** run migrations on their own.

```bash
docker compose -f docker-compose.prod.yml exec api python -m alembic upgrade head
```

**Check:**

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U lilkis_admin -d lilkis -c '\dt'
```

You should see the tables listed.

### 5.5 Create Samir's account

> **Never run `python -m app.seed` here.** That is the demo seed. It
> creates three accounts with the password `changeme123` and no forced
> password change. On a public server that is an open door.

```bash
docker compose -f docker-compose.prod.yml exec api python -m app.bootstrap
```

It asks for Samir's name, email and a first password, creates exactly one
account — admin, owner — and refuses to run if any user already exists.
Give Samir the password directly; he is forced to change it at first
sign-in.

**Check:** sign in at your domain as Samir and reach the Deals page.

---

## Phase 6. The domain and the tunnel

**Time:** 30 minutes. Needs a domain you control.

The tunnel is how the internet reaches the VM. It dials **out** from the
server to Cloudflare, so the VM needs no open inbound ports at all — no
port 80, no port 443, nothing to scan or attack. It also terminates
HTTPS for you, so there are no certificates to manage or renew.

1. At <https://dash.cloudflare.com>, add the domain (`lilkis.in`) and
   follow the nameserver instructions at your registrar. Propagation
   takes anywhere from minutes to a few hours.
2. **Zero Trust → Networks → Tunnels → Create a tunnel**:
   - **Cloudflared**, name it `lilkis-prod`
   - On the next screen, **copy the token** — the long string in the
     install command. That is `CLOUDFLARE_TUNNEL_TOKEN`. You do not need
     to run their install command; the compose file runs cloudflared for
     you.
3. **Public hostname**:
   - **Subdomain:** `deals` → **Domain:** `lilkis.in`
   - **Service type:** HTTP
   - **URL:** `web:8080`

   > `web`, not `api`. `web` is the nginx container that serves the site
   > and proxies `/api` through to the backend. Pointing the tunnel at
   > the API serves no frontend at all and breaks the same-origin cookie.

4. Put the token in `.env`, then `docker compose -f
   docker-compose.prod.yml up -d`.

**Check:** `https://deals.lilkis.in` shows the sign-in page, with a
padlock.

---

## Phase 7. Backups — the phase that protects your job

**Nothing before this point protects you from losing data.** Everything
so far has one copy of the documents, in one Oracle account.

Two things need backing up, and they are different:

| | Where it lives | What loses it |
|---|---|---|
| **The database** | Postgres on the VM | VM reclaimed, disk failure, a bad migration |
| **The documents** | OCI bucket | Account problem, a mistaken purge |

### 7.1 Database backup, nightly

```bash
mkdir -p /opt/lilkis/ops
nano /opt/lilkis/ops/backup.sh
```

I will write this script for you — ask and I will add it to the repo
rather than have you type it from a guide. It will:

- `pg_dump` the database
- encrypt it with a passphrase
- upload it to a **separate bucket**, `lilkis-backups`
- keep 30 days and delete older ones
- exit non-zero loudly if any step fails

Then schedule it:

```bash
sudo nano /etc/systemd/system/lilkis-backup.service
sudo nano /etc/systemd/system/lilkis-backup.timer
sudo systemctl enable --now lilkis-backup.timer
```

### 7.2 Document backup, to a different provider

This is the one that matters. A copy of the documents inside the same
Oracle account does not protect you from the account being the problem.

Use `rclone` on the VM to sync the bucket to a second provider —
Cloudflare R2 is the natural fit since you already have a Cloudflare
account for the tunnel, its free tier is 10 GB with no egress charges and
no expiry, and it speaks the same S3 API. Backblaze B2 works equally
well.

Weekly is enough, given documents are only ever added.

### 7.3 The restore drill — do it before go-live, not after

A backup you have never restored is not a backup. It is a file that you
hope is a backup.

Once, before the first real document goes in:

1. Take a backup.
2. Destroy the database: `docker compose -f docker-compose.prod.yml down -v`
3. Restore from the backup.
4. Confirm you can sign in and the deals are there.

Write down how long it took. That number is your honest answer when
Samir asks what happens if something breaks.

> PRD §12 lists "restore drill" in Phase 2. This is it. It is listed as
> a deliverable because an untested backup is a very common way to find
> out, far too late, that you had no backup.

### 7.4 Schedule the purge job

```bash
sudo nano /etc/systemd/system/lilkis-purge.service   # ExecStart runs app.jobs.purge
sudo nano /etc/systemd/system/lilkis-purge.timer     # daily
sudo systemctl enable --now lilkis-purge.timer
```

Run it with `--dry-run` first and read the report. It is the only thing
in the system that deletes objects.

---

## Phase 8. Before you hand it over

- [ ] Phase 3 storage test passed against real OCI
- [ ] Bucket versioning is on
- [ ] The app key cannot delete — tested, not assumed
- [ ] Upgraded to Pay As You Go; no trial countdown in the console
- [ ] Budget alert set
- [ ] `.env` is `chmod 600` and not in git
- [ ] Repository is private
- [ ] Samir can sign in; `changeme123` exists nowhere on the server
- [ ] A second account (Rohan or Meera) created through the UI, and the
      permission matrix set
- [ ] Nightly database backup running, verified by looking at the bucket
- [ ] Document backup to a second provider running
- [ ] **Restore drill done**, with the time written down
- [ ] Purge timer enabled, dry run read
- [ ] Upload a real-sized file (100 MB+) over the tunnel and download it
- [ ] 2-page user guide written for Samir, Rohan and Meera

---

## When something breaks

```bash
cd /opt/lilkis
docker compose -f docker-compose.prod.yml ps        # what is running
docker compose -f docker-compose.prod.yml logs -f api    # API logs
docker compose -f docker-compose.prod.yml logs -f web    # nginx
docker compose -f docker-compose.prod.yml restart api    # restart one
```

**Site not loading at all** — check the tunnel: `docker compose -f
docker-compose.prod.yml logs cloudflared`. Then check the Cloudflare
dashboard says the tunnel is Healthy.

**Sign-in fails for everyone** — almost always the database password
mismatch in Phase 5.1. `logs api` will show an authentication failure
against Postgres.

**Uploads fail** — `logs api` for the OCI error. A `SignatureDoesNotMatch`
means the keys or endpoint are wrong; a `403` on a put means the policy
in Phase 2.5 is too tight.

**Everything looks fine but nothing saves** — check the disk:
`df -h`. 200 GB is the Always Free limit, shared with the database.

---

## What this costs

| | |
|---|---|
| VM, 2 OCPU / 12 GB Arm | ₹0 — Always Free |
| 200 GB disk | ₹0 — Always Free |
| First 20 GB of documents | ₹0 — Always Free |
| Documents beyond 20 GB | about ₹2 per GB per month |
| Outbound traffic | ₹0 up to 10 TB a month |
| Cloudflare tunnel | ₹0 |
| Domain | whatever you already pay |

Realistically zero until the deal room holds more than 20 GB, and small
for a long time after that.
