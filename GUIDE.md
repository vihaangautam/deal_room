# Taking the Lilkis Deal Room live

> **Status, 25 Oct 2026.** Deployed to **AWS Mumbai**, not OCI — EC2 at
> `13.126.222.201`, S3 bucket `lilkis-deal-vault` with versioning and the
> split app/purge keys. Phases 1, 2 and 4 below still describe the OCI
> route and are kept for reference; the AWS equivalents were done
> directly. **Phases 3, 5, 6, 6b, 7 and 8 all still apply as written.**
>
> **Handing over to Samir for real use — see "Handover night" below.**
> That section is the ordered list for tonight; the phases it refers to
> have the detail.

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

## Phase 1. The Oracle account

**Time:** 5 minutes if the account exists; 20 minutes plus verification
if not.

**You already have an account**, so skip to *Then upgrade to Pay As You
Go* below. The signup steps are kept only in case you ever start again
from nothing.

<details>
<summary>Creating an account from scratch</summary>

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

</details>

### Then upgrade to Pay As You Go

Per Phase 0. Do this now, while you remember.

1. In the console, open the **☰ menu → Billing & Cost Management →
   Upgrade and Payment**.
2. Choose **Upgrade to Pay As You Go**.
3. Confirm.

**Check:** the orange "Free Trial — N days left" banner at the top of the
console is gone.

> **Decided, 24 Oct 2026:** Vihaan is upgrading to Pay As You Go. The
> deletion clause is the one risk in this whole document that cannot be
> undone afterwards, and a near-zero bill is the right price for closing
> it. Nothing else in this guide depends on which way this went — it just
> stops being a question.

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

## Phase 6. HTTPS — without this, nobody can sign in

**Time:** 30 minutes, plus DNS propagation. **Needs a domain.**

### Why this is not optional

The session cookie is set `Secure`:

```
set-cookie: lilkis_session=...; HttpOnly; SameSite=strict; Secure
```

A browser will only store and return a `Secure` cookie over HTTPS. Served
over plain `http://`, Chrome accepts the login response, silently throws
the cookie away, and the very next request is unauthenticated. Tested
against the live server on 25 Oct 2026:

```
POST /api/auth/login     -> 204       the server is happy
document.cookie          -> (none)    Chrome refused to store it
GET  /api/auth/me        -> 401       so nobody is signed in
```

`curl` does not enforce `Secure`, which is why a health check and an API
smoke test both pass while the actual site is unusable. **HTTPS is what
makes the application work at all**, not a hardening step to do later.

There is no practical way to get a trusted certificate for a bare IP
address, so this needs a domain name. That is the one prerequisite.

### 6.1 A domain

Ideally `lilkis.in`, or whatever Samir's firm already owns — it belongs
with the firm, like their email domain. If that will take weeks, any
cheap domain works for now and can be changed later; it is about ₹800 a
year and the tunnel does not care which one it is.

Either way the domain's nameservers have to point at Cloudflare:

1. <https://dash.cloudflare.com> → **Add a site** → enter the domain →
   **Free** plan.
2. Cloudflare shows you two nameservers. Set those at your registrar
   (GoDaddy, Namecheap, BigRock — wherever it was bought), replacing
   what is there.
3. Wait. Minutes usually, up to a few hours. Cloudflare emails when the
   site is Active.

### 6.2 Create the tunnel

1. **Zero Trust** (left sidebar) → **Networks → Tunnels** → **Create a
   tunnel**.
2. Choose **Cloudflared**, name it `lilkis-prod`, **Save**.
3. The next screen offers install commands for various systems. **Ignore
   all of them** — the compose file already runs cloudflared. You only
   want the **token**: the long string after `--token` in the command
   shown. Copy that.

   > It is a credential. Treat it like a password: it lets anything
   > holding it publish traffic for that hostname.

4. **Next**, then **Public Hostname**:

   | Field | Value |
   |---|---|
   | Subdomain | `deals` |
   | Domain | your domain |
   | Path | *(leave empty)* |
   | Type | `HTTP` |
   | URL | `web:8080` |

   > `web:8080`, not `api:8000` and not an IP. `web` is the nginx
   > container, reachable from cloudflared over the compose network. It
   > serves the site and proxies `/api` to the backend, which is what
   > keeps everything same-origin so the cookie works. Pointing the
   > tunnel at the API serves no frontend at all.

5. **Save tunnel.**

### 6.3 Point the app at the new address

On the server:

```bash
cd /opt/lilkis
git pull
nano .env
```

Two lines change:

```
PUBLIC_ORIGIN=https://deals.yourdomain.in     # was http://13.126.222.201
CLOUDFLARE_TUNNEL_TOKEN=<the token from 6.2>
```

`PUBLIC_ORIGIN` must be the `https://` address with no trailing slash. It
is what the API allows as an origin; leave it as the old IP and the
browser's requests get rejected.

Then:

```bash
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs --tail 20 cloudflared
```

The log should say `Registered tunnel connection` a few times. The
Cloudflare dashboard should show the tunnel as **Healthy**.

> `git pull` matters here: it removes the published port 80 and takes
> cloudflared out of the optional profile it was put in during the first
> deploy. Without it the tunnel container will not start on its own.

### 6.4 Check that sign-in actually works

Not with curl. **In a browser**, because the whole bug was browser-only:

1. Open `https://deals.yourdomain.in` — padlock in the address bar.
2. Sign in as Samir.
3. You should land on the Deals page and **stay there** on a refresh.

If it bounces back to the login screen, the cookie is still being
rejected: check the address really is `https`, and that `PUBLIC_ORIGIN`
matches it exactly.

---

## Phase 6b. Close port 80

Only once Phase 6 works end to end.

The first deploy published port 80 and opened the security group to the
world so the site could be reached on its IP. The tunnel dials **out**,
so none of that is needed any more — and leaving it means the app stays
reachable over plain HTTP, cookie bug and all, by anyone who knows the
address.

1. **AWS Console → EC2 → Instances → `lilkis-prod` → Security tab →**
   click the security group.
2. **Inbound rules → Edit inbound rules.**
3. **Delete** the rule allowing HTTP / port 80 from `0.0.0.0/0`.
4. Keep **SSH (22)** — but narrow its source from `0.0.0.0/0` to **My
   IP** while you are there. That is how you still get in.
5. **Save rules.**

**Check:** `curl -m 10 http://13.126.222.201` now times out, and
`https://deals.yourdomain.in` still works.

That pair of results is the whole point: nothing reachable except through
Cloudflare, over TLS.

---

## Phase 7. Backups — the phase that protects your job

**Nothing before this point protects you from losing data.** Everything
so far leaves one copy of the documents, in one AWS account.

The scripts are written and in the repository under `ops/`. **`ops/README.md`
has the install steps** — this phase is why each one exists.

Two different things need protecting, and they fail in different ways:

| | Where it lives | What loses it |
|---|---|---|
| **The database** | Postgres on the VM | VM lost, disk failure, a bad migration |
| **The documents** | S3 bucket | Account compromised, a mistaken purge |

The database is small — it holds no files, only who everyone is, which
deal each document belongs to, the permissions, the tasks and the audit
log. But without it the bucket is a pile of UUIDs that mean nothing.

### 7.1 `ops/backup.sh` — nightly

Dumps, compresses, encrypts with a passphrase, uploads to a separate
bucket, prunes past 30 days, and **reads the object back** to confirm it
is really there at the right size. Every step is checked, because a
backup job that fails quietly is worse than none at all: it also removes
the worry that would have made someone look.

Pruning only happens after a verified upload, so a run that fails early
never deletes the older backup that is currently the good one.

> Give it its own IAM user (`BACKUP_ACCESS_KEY_ID`). Without one it falls
> back to the purge key, which can also delete the live documents — so a
> single stolen credential would reach both the originals and the copies.
> It warns when it does this.

### 7.2 `ops/sync-documents.sh` — weekly, to a different provider

**This is the row in the table that account-level trouble cannot touch.**

Versioning and the no-delete policy both protect against things going
wrong *inside* the bucket. Neither protects against the bucket, the
account, or the root credentials being the problem. A second bucket in
the same AWS account covers a mistake, not an account.

Point `DOCS_MIRROR_ENDPOINT` at Cloudflare R2 — you already have a
Cloudflare account for the tunnel, the free tier is 10 GB with no egress
charges, and it speaks the same S3 API. Backblaze B2 works equally well.

It syncs, never mirrors: nothing in it deletes from the destination. If a
document vanishes from the primary for any reason, including one nobody
intended, the copy is still there.

### 7.3 The restore drill — before go-live, not after

A backup you have never restored is a file you *hope* is a backup.
`ops/restore.sh` exists so the real thing is a command you have already
run rather than a procedure you are inventing while frightened.

```bash
/opt/lilkis/ops/backup.sh
/opt/lilkis/ops/restore.sh                      # lists what is there
/opt/lilkis/ops/restore.sh lilkis_2026...gpg    # puts it back
```

It downloads and decrypts **before** touching the running database, so a
wrong passphrase or a corrupt object is found while the live system is
still intact. Then it asks you to type the database name, because the
one way it can make things worse is being run by accident.

Afterwards: **sign in through the browser and open a deal.** Row counts
prove the load ran; only signing in proves the restore worked.

Write down how long it took, start to finish. That number is your answer
when Samir asks what happens if something breaks.

### 7.4 The purge sweep

`lilkis-purge.timer`, daily at 04:00 IST — after the backup, so anything
it removes was captured in that night's dump first. It is the only thing
in the system that deletes objects. Run it once with `--dry-run` and read
the report before enabling the timer.

---

## Handover night — the runbook

**Goal:** by the end of tonight, Samir has one URL and one password, and
from that moment he can use the deal room for real work — adding real
documents — without you needing to touch anything for him to carry on.

That last clause is what sets the list below. Real documents means the
data has to survive the night going wrong, so backups are part of tonight
rather than part of next week.

**About 2.5 hours.** Do them in this order; each one depends on the one
before.

---

### 1. Rotate the AWS keys — 15 min

Both pairs were pasted into a chat transcript and must be treated as
public. These are the only exposed credentials that are usable by anyone,
from anywhere — the database passwords are behind the VM with no
published port, and the session secret turns out not to sign sessions at
all (fastapi-users is on DatabaseStrategy, so tokens are random rows in
`access_tokens`).

1. **AWS Console → IAM → Users → `lilkis-app` → Security credentials →
   Create access key.** Copy both halves.
2. Same for **`lilkis-purge`**.
3. On the server, put all four values into `/opt/lilkis/.env`.
4. Restart and check:

```bash
cd /opt/lilkis
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml exec api python -m app.checks.storage_check
```

**Check:** `5 passed, 0 failed`. This is the first time the no-delete
check can pass — it cannot pass against the local S3Mock, which has no
permissions model. Green here means the policy is real.

5. Back in IAM, **delete** the old keys. Delete, not deactivate.

---

### 2. HTTPS — 30 min

Phase 6 above, in full. Until this is done nobody can sign in at all:
the session cookie is `Secure` and browsers discard it over plain HTTP.

Short version once the tunnel exists in the Cloudflare dashboard:

```bash
cd /opt/lilkis
git pull                       # removes port 80, un-hides cloudflared
nano .env                      # CLOUDFLARE_TUNNEL_TOKEN + PUBLIC_ORIGIN
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml logs --tail 20 cloudflared
```

`PUBLIC_ORIGIN` must be the exact `https://` address, no trailing slash.

**Check:** open the site in a browser, sign in, **refresh**. Staying
signed in through a refresh is the test. curl cannot tell you this.

---

### 3. Close port 80 — 5 min

Phase 6b above. **Check:** `curl -m 10 http://13.126.222.201` times out
while the HTTPS address still works.

---

### 4. Backups — 45 min

Now mandatory, because real documents.

```bash
sudo apt update && sudo apt install -y awscli gnupg
```

Create the backup bucket in S3 (`lilkis-deal-backups`, versioning on),
then add to `.env` the block in `ops/README.md`. Generate the passphrase
on the server and **store it somewhere that is not this server** — a
password manager, or on paper. It is the only thing that opens the
backups, and if its only copy is on the machine they exist to recover,
they are decoration.

```bash
/opt/lilkis/ops/backup.sh
sudo cp /opt/lilkis/ops/*.service /opt/lilkis/ops/*.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lilkis-backup.timer lilkis-purge.timer
systemctl list-timers 'lilkis-*'
```

---

### 5. The restore drill — 15 min, before Samir gets the link

Not after. This is the one chance to do it on a system where nothing is
lost if it goes wrong, and a backup nobody has restored is a file you
hope is a backup.

```bash
/opt/lilkis/ops/restore.sh                     # list
/opt/lilkis/ops/restore.sh lilkis_2026...gpg   # put it back
```

Then sign in through the browser and open a deal. **Write down how long
the whole thing took** — that is your answer when Samir asks what happens
if something breaks.

---

### 6. Samir's account — 5 min

The bootstrap password is in a transcript, so it cannot be the one he
keeps. It is already set to force a change at first sign-in, so the
simplest safe path is: **make sure Samir is the first person to log in**,
and that he changes it immediately.

Send the URL and the password through different channels if you can —
the link by email, the password by phone or WhatsApp.

**Check:** sign in as Samir yourself once, confirm the change-password
screen appears, then *do not* complete it. Leave that for him.

---

### 7. Final pass — 15 min

Walk it as Samir would, on the real URL:

- [ ] Sign in, refresh, still signed in
- [ ] Upload a document to a folder, approve it
- [ ] Open the PDF — it should open in a tab
- [ ] Add a user, set folder access, sign in as them in a private window
- [ ] Delete something and recover it from the Archive
- [ ] Check the Activity tab shows all of it

Anything broken here is better found now than by Samir at 9am.

---

### Not tonight, and that is fine

- **Document copy to a second provider** (`sync-documents.sh`). The
  bucket has versioning and the app's key cannot delete, so documents are
  well protected against everything except losing the AWS account itself.
  Worth doing this week; not worth delaying handover for.
- **Rotating the database passwords and SECRET_KEY.** Only reachable from
  inside the VM.
- **Moving to a Lilkis domain and a Lilkis-owned AWS account.** Both
  should happen before this stops being a pilot. Raise them with Samir
  now so they are his decisions, not surprises later.

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
