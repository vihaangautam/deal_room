# Demo script — 10 October 2026

Roughly 12 minutes. Every screen below already has data in it; nothing has
to be created live except where it says so.

**Before you start:** run `python -m app.seed` once (it repairs files lost
when the containers restarted — downloads fail silently otherwise). All
three accounts use `changeme123`. Have
http://localhost:5173 open and be signed out. Close other tabs — the audit
log records every sign-in and you will be showing it at the end.

---

## 1 · Deals home — 1 min

Sign in as **samir@lilkis.in**.

> "Every deal the fund is working on, in one place. Four here: one new,
> one running, two closed."

- Click through **New / Running / Old**. Point out the counts.
- On **Old**, show the `All · Successful · Dropped` filter.
- Point at the **Documents** and **Tasks** columns — "29 files, 4 of 6
  tasks done, at a glance, without opening anything."

---

## 2 · Documents and permissions — 3 min

Open **Sharma Infra Ltd**.

> "This is the live deal. Folders down the left are the same in every deal,
> so people always know where to look."

- Click two or three folders. Counts update, URL changes — **say that the
  URL is shareable**: "you can paste this in WhatsApp and the other person
  lands on the same folder."
- Click a file name → it downloads. "Ten-minute signed link, and we log who
  downloaded what."
- Hover a row → **•••** → **Rename**. Change a name, press Enter.
  **A toast appears with Undo — click it.** "Nothing here is a one-way
  door."

### The permission story (this is the one Samir cares about)

Open a second browser **in a private window** and sign in as
**rohan@lilkis.in**, same deal.

> "Same deal, different person."

- **Borrower details** shows a lock and no count — Rohan has None there.
- Count the files: Rohan sees fewer than you do. One is a pending upload
  from Meera that only approvers can see.

Leave the private window open — you will come back to it.

---

## 3 · Upload — 2 min

Back as Samir, **Upload files**. Drag in **two or three dummy PDFs**.

> "Big files go up in chunks, so a dropped connection resumes instead of
> starting over. Two gigabytes a file."

- Each file gets its own progress bar.
- They land as **Added** because Samir is an approver — "his own uploads
  don't need his own approval."

> Have a few junk PDFs ready on the desktop. Do not use anything real.

---

## 4 · Tasks — 2 min

**Tasks** tab.

> "Six pieces of work on this deal, and you can see the state of all of
> them without asking anyone."

Point at, without clicking:

- **SHRM-4** — `Needs attention` plus a red overdue date
- **SHRM-5** — Unassigned
- **SHRM-1** — Done

Open **SHRM-3 Chase HDFC for the May statement**.

- Show the comment thread, and the **reply** underneath it.
- Add a comment live. "Everything on a deal stays on the deal."

---

## 5 · The approval chain — 2 min ⭐

**This is the bit to slow down for.**

Open **SHRM-2 Verify hypothecation deed registration**.

> "This says *Awaiting approval*. Not because someone set it to that — the
> file attached to it hasn't been approved yet."

Go to **Approvals** in the sidebar.

> "Three things waiting: an upload, a deletion, and a reassignment request.
> Samir is the only one who can decide."

- **Click the filename first.** It downloads. "I'm not approving something
  I can't read — I open it, then I decide."

- Tick **Hypothecation deed signed.pdf** → **Approve selected**.
- Toast confirms it.
- Go back to **SHRM-2**. **It is now Done.**

> "Nobody marked that task complete. Approving the document completed it.
> That is the rule you described — the system decides, not the person."

---

## 6 · Closed deals are read-only — 1 min

Deals → **Old** → **Mehta Logistics**.

> "This one closed successfully."

- Blue banner: *"This deal is closed. Files can be downloaded but not
  changed."*
- **No Upload button. No Tasks tab. No row menu on any file.**
- Click a file name — **it still downloads**. "Read-only means read-only,
  not locked away."

---

## 7 · Admin — 2 min

Quick tour, don't linger:

- **Folders** — "add one here and it appears in every deal, past and
  present. Drag to reorder." Show the **Files across deals** column: "this
  is why a folder with files in it can't be deleted."
- **Users & permissions** → **Folder access** tab. The grid.
  > "This is the whole security model on one screen. Every person, every
  > folder, three levels."
- **Archive** — the deleted file, with who deleted it, who approved it and
  why. Point at **Retention: Keep forever — Change**.
- **Activity** — filter by deal or by person.
  > "Every action on every deal, kept forever, and nobody can edit it —
  > not even me."

---

## 8 · Close

> "Everything you have seen is running on this laptop. The same thing goes
> on your own server, behind your own domain, next — the application
> doesn't change."

---

## If something goes wrong

| What happens | What to say | What to do |
|---|---|---|
| A page is blank or stuck | "One second, let me refresh." | F5. The session survives it. |
| Login says it's incorrect | — | Caps lock. It's `changeme123`. Five wrong tries locks that email for 15 minutes — use a different account. |
| Everything 401s | "Session timed out." | Sign in again. |
| An upload fails | "That's the connection — it resumes." | Click **Retry** on that row. |
| Tab shows an error | — | Go to Deals and come back. Don't debug on screen. |

**Don't demo:** creating a user (the password dialog is a distraction),
deleting a folder, or the purge job.

**Don't say:** "bucket", "S3", "presigned", "migration", "endpoint". Say
*file*, *storage*, *link*, *update*.

---

## Questions you will probably get

**"Can people see each other's documents?"**
Only what you give them. Per folder, three levels: None, View, Contribute.
Show the matrix again.

**"What if someone deletes something important?"**
They can't. A member requests, you approve, and it goes to the Archive
rather than disappearing. Nothing is ever hard-deleted.

**"Can we get to it from outside the office?"**
Yes — that's the next step. Your own domain, over HTTPS.

**"How big can files be?"**
Two gigabytes each, a hundred at a time.

**"Does it email people?"**
Not in this version — it was on the not-doing list. It's on the roadmap.

**"What happens when someone leaves?"**
You deactivate them. They keep their place in the history and on their
tasks, marked *(deactivated)*, and they cannot sign in again.
