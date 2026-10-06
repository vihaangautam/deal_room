# PRD.md — Lilkis Deal Room

## 1. Problem

Lilkis Capital AIF Trust (SEBI Category II AIF, Reg. IN/AIF2/23-24/1450) lends to distressed-but-recoverable businesses against collateral: IBC interim finance, last-mile funding, ARC co-investment. Every deal produces 1–3 GB of mostly scanned PDFs plus Word and Excel files. Today these live in personal drives, email threads and WhatsApp. That causes four problems:

1. Nobody can say which version of a security document is current, or who added it.
2. There is no control over who sees sensitive folders such as Borrower details.
3. Work handed between the Investment Manager's team and the sponsor is tracked in conversation, not in a system.
4. There is no record that would satisfy a regulator or auditor asking "who had this document, and when".

The product is a private, internal deal room: a lightweight virtual data room plus a task tracker for running deals. It is the client's first internal software product and must be obvious to use without training.

---

## 2. Goals

| # | Goal | Rationale |
|---|---|---|
| G1 | Every deal document lives in exactly one deal folder, with a known uploader, approver and timestamp. | Removes "which file is current" and creates an audit trail. |
| G2 | Folder-level access control, enforced on the server. | Borrower details and similar folders must be restricted to named people. |
| G3 | The sponsor approves every upload, deletion, task reassignment and task deletion from one queue, in batches. | Samir wants control without becoming a bottleneck. Batch approval keeps that cheap. |
| G4 | Running deals have a task list showing who owes what by when. | Replaces delegation by chat. |
| G5 | Nothing is ever lost: no hard deletes from the app, an append-only audit log, nightly backups. | Legal and security documents of a regulated fund. |
| G6 | Runs for about ₹0–200/month in India, and can move to AWS Mumbai without a rewrite. | Small-fund budget, data residency, and a planned migration. |

---

## 3. Non-goals (v1)

Compliance calendar and regulation watch (on hold). OCR and full-text search. In-browser preview. Email or push notifications. Subfolders. Document versioning (a new upload is a new document). External or borrower-facing access. Google or SSO sign-in. Mobile apps. NBFC entity support. Self-service sign-up.

---

## 4. Users and roles

| Role | Who | Count | Capabilities |
|---|---|---|---|
| Admin | Samir Biyani (sponsor) | 1 | Everything. Creates deals, changes stages, manages folders, users and permissions, sees Archive and Activity. |
| Approver (capability) | Samir; optionally one backup | 1–2 | Approves or rejects requests. A grantable flag (`can_approve`) on a user, not hardcoded to Samir. |
| Member | LeapUp and Lilkis staff | ~9 | Sees all deals. Folder access depends on their per-folder level. Creates and works on tasks. |

Two roles (Admin and Member) plus one capability flag (`can_approve`). Rationale: Samir needs a backup approver for leave without handing over full user management.

---

## 5. Glossary

- **Deal**: one financing case. Name, short code (2–6 uppercase letters, e.g. `KRSN`), borrower name and one-line summary.
- **Deal stage**: `New`, `Running`, `Successful`, `Dropped`. On the Deals home, "Old deals" means Successful plus Dropped.
- **Folder**: one of a single global list (Minutes of the meeting, Bank documents, Security documents, Legal documents, Agreements, Government regulation special to the case, Miscellaneous, Borrower details). Every deal shows every folder. Deals do not own folders. A document records `deal_id + folder_id`.
- **Access level**: a user's level on a folder. `None` (cannot open it), `View` (see and download), `Contribute` (View plus upload, rename, request deletion).
- **Approval request**: a pending change that an approver must accept or reject. Types: document upload, document deletion, task reassignment, task deletion.
- **Pending**: uploaded but not yet approved. Visible only to the uploader and approvers.
- **Archive**: admin-only list of documents whose deletion was approved. Files stay in storage.
- **Purge**: permanent removal of the stored file, done only by a scheduled job under a separate credential. Applies only to rejected uploads (after 30 days) and, if Samir enables it, to Archive items after the configured retention.
- **Activity**: the automatic, append-only record of every action on a deal. **Tasks** are forward-looking work someone must do. **Activity** is a backward-looking record nobody writes by hand.

---

## 6. Feature requirements and acceptance criteria

### F1. Authentication

- Email and password only. Accounts created by the admin. No self sign-up, no social login.
- A new user gets a temporary password and must change it at first login before reaching any other page.
- Login rate-limited: after 5 failed attempts within 15 minutes, that email is locked for 15 minutes. The response message is identical for unknown email, wrong password and lockout.
- Sessions are httpOnly, Secure, SameSite=Strict cookies backed by a database token. They expire 12 hours after login. Deactivating a user ends their sessions immediately.

**Acceptance:**
- A user created with a temporary password who logs in is redirected to "Set a new password". Every API call other than change-password returns 403 `password_change_required` until they set one.
- After deactivation, the user's next request returns 401 and they cannot log in again.
- The sixth failed attempt within 15 minutes returns the same generic error, and a correct password is refused until the lock expires.

### F2. Deals home

- Three tabs: **New**, **Running**, **Old**. Old has a segmented filter: All / Successful / Dropped.
- Each tab is a table: Deal (name and short code), Borrower, Stage pill, Documents (count of active files the viewer can see), Open tasks (Running only), Last activity, Created.
- Search filters by deal name, code or borrower. Default sort is last activity, newest first.
- Only the admin sees "New deal".

**Acceptance:**
- A member sees every deal in every tab.
- Document counts exclude folders where the viewer has `None` and exclude pending files.
- A deal moved from Running to Dropped appears under Old → Dropped without a page reload.

### F3. Deal creation and stage changes (admin only)

- Create with name, short code (unique, 2–6 letters), borrower name and summary (max 280 characters). Stage starts at New.
- Allowed transitions: New→Running, New→Dropped, Running→Successful, Running→Dropped, Dropped→(previous stage) as a reopen.
- Every change requires a reason (5 to 1,000 characters) and writes a `deal_stage_history` row and an audit entry.
- Old deals (Successful or Dropped) are read-only. Upload, rename, delete request, task create, task edit and comment are disabled. Download still works. The per-deal flag `allow_uploads_when_closed` (default false) re-enables uploads without code changes.

**Acceptance:**
- A member calling the stage endpoint gets 403.
- New→Successful returns 422 `invalid_transition`.
- Reopening a Dropped deal returns it to the stage recorded in the latest history row's `from_stage`.

### F4. Folders (global)

- Admin can create, rename, reorder and delete folders. Each change is a single row change that appears in every deal immediately.
- Deletion is blocked while any document in any deal (status pending, active, delete_requested or archived) references the folder. Error lists counts per deal.
- When creating a folder, the admin chooses the default access level for all current members (default: View).
- No subfolders.

**Acceptance:**
- After "Add folder: Valuation reports", every deal page lists it, including Old deals.
- Deleting "Bank documents" while any file exists returns 409 with per-deal counts.

### F5. Documents

- Folder shows a file table: name, type icon, size, uploaded by, uploaded on, status pill (non-active rows only), row menu.
- **Multi-upload.** A Contribute user selects several files or drags them in. They pick the target folder (pre-filled with current). Each file has its own progress bar, status and a remove control. Allowed types: .pdf, .doc, .docx, .xls, .xlsx, .csv. Maximum 2 GB per file, 100 files per batch.
- **Duplicates.** SHA-256 hash computed in the browser. If the same hash exists in this deal as pending or active, that file is refused with "Already in Bank documents as 'HDFC stmt Apr.pdf'". Cross-deal duplicates are allowed.
- **Approval.** Uploaded file is `pending`. Uploader sees it greyed with "Pending approval". Other members do not see it. When approved it becomes `active`. When rejected, the uploader sees "Rejected" with reason for 30 days, then the file is purged.
- **Approver's own uploads.** Uploads by a user with `can_approve` are approved automatically, with an audit entry.
- **Download.** Clicking a file name downloads it. The server checks permission, returns a 10-minute presigned URL with `Content-Disposition: attachment; filename="<current display name>"`.
- **Rename.** A Contribute user edits the name inline. Extension is locked. Takes effect immediately and is audited. The stored object is not touched.
- **Delete.** A Contribute user chooses "Request deletion" with an optional reason. The file shows "Deletion requested" and remains downloadable. If approved, moves to Archive. If rejected, returns to active.

**Acceptance:**
- Dragging in 12 files uploads all 12 with individual progress bars. Failing one does not affect the rest; Retry resumes only that file.
- A user with View has no upload, rename or delete controls, and the API returns 403 for each.
- A user with None sees the folder row with a lock icon and cannot list its files (403).
- Download URLs expire after 10 minutes. A link opened after a user loses access but before expiry still works until expiry. Accepted and documented.

### F6. Access control

- Admin sets each user's level per global folder in a matrix (users as rows, folders as columns).
- Resolution order: admin → Contribute; otherwise global row; otherwise None. Schema ready for per-deal overrides later.
- Every endpoint that touches a document enforces this, including list, count, download, rename, delete request, task attachment, and before presigned URL generation.
- When a task links a document the viewer cannot access, the task shows "Restricted document" with no name, size or link.

**Acceptance:**
- Automated test covers every document endpoint for each of None, View and Contribute and checks expected status codes.
- Task attachment list for a user with None on Borrower details shows the placeholder; the API response contains no filename.

### F7. Approvals queue (approvers)

- Table of pending requests: checkbox, Type, Item, Deal, Folder, Requested by, Requested on, Note.
- Filters: deal, requester, type. "Select all" checkbox plus **Approve selected** and **Reject selected**. Reject opens a dialog with optional reason.
- Pending count badge in navigation; refreshes every 60 seconds and after any mutation.
- Bulk actions return a per-item result. If one item was already decided, the others still succeed and a toast reports "11 approved, 1 already handled".

**Acceptance:**
- Approving 40 uploads in one action makes all 40 active within 5 seconds.
- Two approvers deciding the same item: first wins, second gets "already handled" for that item.

### F8. Tasks (Running deals)

- Tasks tab shown on Running deals, hidden on New and Old by a single setting (`tasks_enabled_stages = ['running']`).

**Fields:** key (`KRSN-12`), title (max 200 characters), description, status, assignee, reporter, assigned by, start date (optional), due date (must not be before start date), attachments, comments.

**Statuses:** Not started → In progress → Done, plus **Awaiting approval** (`submitted`). Boolean flag `needs_attention` set when an attachment is rejected.

**Creating and assigning.** Anyone can create and assign. Assigning an unassigned task does not need approval. Changing an existing assignee creates a reassignment request; the task stays with the current assignee until approved. When approved, the requester becomes "assigned by". Approvers reassign directly. Self-assigning an unassigned task is immediate.

**Editing the description.** Anyone can edit while unassigned. Once assigned, only the "assigned by" user and admin can edit. Shows "Edited by {name} on {date}".

**Changing status.** The assignee, the "assigned by" user and admin can change status.

**Marking done.**
- No pending attachments → Done immediately.
- Pending attachments present → status becomes Awaiting approval.
- All pending attachments approved → moves to Done automatically.
- Any attachment rejected → returns to In progress with "Needs attention: attachment rejected".

**Reopening.** Reporter, "assigned by" user or admin can move a Done task back to In progress.

**Deleting.** Delete is a request needing approval. Approved deletions soft-delete the task. Approvers delete directly.

**Comments.** Flat thread, newest last, one level of replies. Authors can edit within 15 minutes and can delete (shows "Comment removed"). Plain text with line breaks.

**Attachments.** One "Attach" control with two options:
1. **Link existing document from this deal.** A picker lists the deal's active documents the user can see, grouped by folder. Creates a pointer, no copy.
2. **Upload new.** User must choose a target folder; Miscellaneous suggested for unrelated files. File enters the normal approval flow and is linked automatically. While pending, visible and downloadable inside the task to participants who have View on that folder. If rejected, shows "Rejected" and the reason.

**My Tasks.** Every task assigned to me across Running deals, grouped by status, sorted by due date with no-due-date last.

**Acceptance:**
- On a New deal, the Tasks tab is absent and `GET /deals/{id}/tasks` returns 404 `tasks_disabled_for_stage`.
- A reassignment request leaves `assignee_id` unchanged until approved.
- A task with two pending attachments marked done shows Awaiting approval. Approving one keeps it Awaiting approval; approving the second makes it Done.
- Rejecting either attachment returns the task to In progress with the flag set.

### F9. Admin: users

- Create user with name, email, temporary password (or generated 14-character one), role, `can_approve`, and initial folder levels.
- Deactivate or reactivate. No delete. Deactivated users stay in history and on assignments, marked "(deactivated)".
- Reset password: sets a new temporary password and forces a change.

### F10. Admin: Archive and Activity

- **Archive:** deleted documents with deal, folder, deleted-by, approved-by, date and reason. Admin can download or restore. Restoring is audited.
- **Activity:** filterable log by deal, user, action type and date range, read-only. UI may be deferred after the demo; recording starts on day one.

### F11. Settings (admin)

- `archive_retention_days`: "Keep forever" (default) or 30 / 365 / 2,555 days.
- `rejected_upload_purge_days`: 30, fixed in v1.

---

## 7. Permission matrix

C = Contribute, V = View, N = None on the relevant folder. Admin always acts as C on every folder.

| Action | Admin | Member C | Member V | Member N |
|---|---|---|---|---|
| See all deals and folder names | Yes | Yes | Yes | Yes |
| Create deal / change stage / reopen | Yes | No | No | No |
| Manage folders, users, permissions, settings | Yes | No | No | No |
| List active files in folder | Yes | Yes | Yes | No (lock row) |
| Download active file | Yes | Yes | Yes | No |
| Upload (open deal) | Yes, auto-approved | Yes, pending | No | No |
| See own pending/rejected uploads | Yes | Yes | n/a | n/a |
| See others' pending uploads | Approvers only | No | No | No |
| Rename active file | Yes | Yes | No | No |
| Request deletion | Deletes directly to Archive | Yes | No | No |
| Approve/reject requests | If `can_approve` | If `can_approve` | If `can_approve` | If `can_approve` |
| View Archive / Activity | Yes | No | No | No |
| Create task, comment | Yes | Yes | Yes | Yes |
| Link a document to a task | Yes | Needs V or C on its folder | Needs V or C | No |
| Upload new task attachment | Yes | Needs C on target folder | No | No |
| Reassign task | Direct | Request | Request | Request |
| Delete task | Direct | Request (reporter or assigned-by) | Request | Request |

Task actions are not tied to folder level. Folder level only governs documents shown inside tasks.

---

## 8. State machines

### Deal stage

```
          +---------> Dropped <---------+
          |              |  reopen      |
  New ----+--> Running --+--> Successful
          ^              |
          +--- reopen ---+
```

Allowed: New→Running, New→Dropped, Running→Successful, Running→Dropped, Dropped→New|Running (reopen, to the recorded previous stage). Successful is terminal in v1.

### Document status

```
uploading --complete--> pending --approve--> active --request delete--> delete_requested
    |                      |                   ^                             |        |
    | (24h stale)          | reject            | (restore from Archive)    reject  approve
    v                      v                   |                             v        v
  failed                rejected --30d--> purged                      active     archived
                                                                              (retention)--> purged
```

`purged` means the database row is kept and the object deleted. Rows are never deleted.

### Task status

```
not_started --> in_progress --mark done--> [no pending attachments] --> done
     |               ^                     [pending attachments]   --> submitted
     +---------------+                                                   |   |
                     ^                       all attachments approved ---+   |
                     +---- any attachment rejected (needs_attention) --------+
done --reopen--> in_progress
```

### Approval request

```
pending --approve--> approved
pending --reject---> rejected
pending --cancel---> cancelled      (requester withdraws)
pending -----------> superseded     (target changed: e.g. task deleted, document archived)
```

One pending request per (type, target) at a time. A second request for the same target is refused with 409.

---

## 9. Key user journeys

**Samir: create a deal**
1. Deals → New deal.
2. Enter name "Krishna Steel – interim finance", code KRSN, borrower, summary.
3. Create. The deal opens on Documents with all folders listed and empty.

**Samir: approve a batch**
1. Sidebar badge shows "Approvals 23".
2. Filter Deal = KRSN, then Select all (18 shown).
3. Untick 2, then Approve selected. Toast: "16 approved."
4. Tick the 2, Reject selected. Enter reason. Confirm.

**Samir: set permissions**
1. Admin → Users & permissions → Matrix.
2. Borrower details column: set every member to None except Rohan and Meera (View).
3. Save. Confirmation lists the 9 changes. Audit entries are written.

**Samir: add a folder**
1. Admin → Folders → Add folder.
2. Name "Valuation reports", default access View. Save.
3. Open any deal, old or new — the folder is there.

**Employee: upload multiple files**
1. Running deal → Documents → Bank documents → Upload.
2. Drag in 14 PDFs. Per-file bars run. One fails; press Retry on that row.
3. All 14 appear greyed with "Pending approval".

**Employee: create and assign a task, attach a document, comment**
1. Running deal → Tasks → "+ Create" row. Type title, press Enter.
2. Open the task. Assignee: Meera. Due: 15 Oct.
3. Attach → Link existing → Agreements → "Term sheet v3.pdf".
4. Comment "Need the signed copy, not the draft."

**Employee (assignee): finish a task with an upload**
1. Attach → Upload new → folder Bank documents → "SBI sanction letter.pdf".
2. Press Mark done. Status becomes Awaiting approval.
3. Samir approves the upload; the task becomes Done automatically.

**Employee: request reassignment**
1. Task → Assignee → choose Arjun. Dialog explains "Samir must approve this. The task stays with Meera until then."
2. Submit. Task shows "Reassignment to Arjun pending".

---

## 10. Edge cases

- **Deactivated assignee.** Tasks keep the assignee with a "(deactivated)" tag. Admin reassigns directly.
- **Stage change with pending requests.** Stage change is allowed. Pending upload approvals remain decidable on Old deals. A pending reassignment on an Old deal is marked superseded.
- **Folder deleted while pending uploads exist.** Blocked. Pending counts toward "files exist".
- **Same file in two folders of one deal.** Refused by the hash check.
- **Rename to an existing name.** Allowed. The list shows the uploaded date to tell them apart.
- **Very large scanned PDF (1.5 GB).** Allowed up to 2 GB. Chunked upload resumes from the last confirmed chunk.
- **Browser closed mid-upload.** The row stays `uploading`. After 24 hours a job aborts the multipart upload and marks it failed.
- **Hash mismatch on server verification.** The document is flagged "Integrity check failed" for approvers, who can only reject it.
- **Permission revoked while a task links a document.** The link remains; the viewer sees "Restricted document".
- **Attachment linked to a task, then the document is archived.** The task shows "Document deleted (archived)". Admin can restore it.
- **Clock and time zones.** Store UTC, display IST (Asia/Kolkata). Dates shown as "15 Oct 2026".

---

## 11. Demo scope: October 10, 2026

**In:**
- Login: Samir (admin, approver), Rohan (Contribute on all except Borrower details = None), Meera (View on all, Contribute on Bank documents).
- Deals home with four seeded deals: New, Running, Successful, Dropped — each with reasons in its stage history.
- Documents: folder list, multi-upload with per-file progress (proxied chunked path), download, inline rename, delete request.
- Tasks on the Running deal: create, assign, status, comments, link and upload attachment, Awaiting approval → Done rule.
- Admin: approvals with checkboxes and bulk actions, add folder (appears in every deal), stage change with reason, create user, folder permission matrix.
- Dummy documents only. Never real borrower files.

**Cut in this order if time is short:** Activity UI, Archive restore, My Tasks grouping (flat list acceptable), password reset UI, comment replies.

---

## 12. Roadmap

| Phase | Target | Scope |
|---|---|---|
| 1 Demo | Oct 10, 2026 | Section 11 |
| 2 Production v1 | 4–6 weeks after sign-off | Hardening, Activity and Archive UI, restore drill, direct upload if spike passes, production domain, onboarding real deals, 2-page user guide |
| 3 | Q1 2027 | Email notifications, in-browser PDF preview (PDF.js range requests), per-deal permission overrides |
| 4 | 2027 | OCR + Postgres tsvector search, subfolders, document versioning, compliance tracker, NBFC entity |

---

## 13. Open questions for Samir

1. **Archive retention.** Storage cost is negligible (~₹20/month for 10 GB). These are legal documents of a SEBI-regulated fund with multi-year record-keeping duties. Default is "Keep forever"; 30, 365 and 2,555 days available. Which do you want?
2. **Permission granularity.** "Rohan can see Borrower details in every deal" vs "only in deal X"? v1 is per folder across all deals; schema ready for per-deal overrides.
3. **Default access for new folders.** View or None when you add a folder?
4. **Pending task attachments vs folder access.** If a task participant lacks access to the folder the assignee uploaded into, they see "Restricted document". Folder rules always win. Confirm.
5. **Backup approver.** Who holds approval rights when you are unavailable?
6. **Your own uploads.** Should uploads by you skip approval (current design) or still appear in the queue?
7. **Domain.** Which domain do you control (e.g. lilkis.in), and who manages its DNS? It must move to Cloudflare DNS for the tunnel and same-site cookies.
8. **Existing documents.** How many deals and GB need importing at go-live? May an admin bulk import skip the approval queue (still audited)?
9. **Deal fields.** Are name, code, borrower and summary enough, or do you need facility amount, sector or IBC case number?
10. **Session length.** 12 hours (log in once per working day). Acceptable?
11. **Hosting and maintenance.** Agree a monthly line in the contract covering backups, updates and restore drills.
