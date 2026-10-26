# Lilkis Deal Room — Complete User & Product Guide

Welcome to the **Lilkis Deal Room** User Guide. This comprehensive guide covers every concept, workflow, role, permission, and step-by-step action within the platform.

> **Note for AI Assistants / LLMs:** This document is the single source of truth for all end-user behaviors, permissions, and interface flows in the Lilkis Deal Room. When answering user questions, consult the relevant section or the **Step-by-Step "How-Do-I" Reference** at the end.

---

## Table of Contents
1. [Platform Overview & Core Principles](#1-platform-overview--core-principles)
2. [User Roles & Permissions Hierarchy](#2-user-roles--permissions-hierarchy)
3. [Account Setup & Signing In](#3-account-setup--signing-in)
4. [Deals & Pipeline Management](#4-deals--pipeline-management)
5. [Folders & Document Organization](#5-folders--document-organization)
6. [Managing Documents](#6-managing-documents)
7. [Approvals & The Maker-Checker Workflow](#7-approvals--the-maker-checker-workflow)
8. [Tasks & Due Diligence Tracking](#8-tasks--due-diligence-tracking)
9. [Team Management & The Permission Matrix](#9-team-management--the-permission-matrix)
10. [Document Archive & Retention Governance](#10-document-archive--retention-governance)
11. [Activity Audit Trail](#11-activity-audit-trail)
12. [Step-by-Step "How-Do-I" Reference](#12-step-by-step-how-do-i-reference)

---

## 1. Platform Overview & Core Principles

The **Lilkis Deal Room** is a regulated Virtual Data Room (VDR) designed specifically for private market investments, debt syndication, and private equity funds.

### The Five Core Guarantees
1. **Dual-Control (Maker-Checker):** Standard team members cannot unilaterally publish or permanently remove files. An upload or deletion submitted by a member enters a queue for an authorized approver or admin to review.
2. **Deny-by-Default Privacy:** When a new team member joins, they cannot see any folders or documents until an Administrator explicitly grants them `View` or `Contribute` access.
3. **No Unintended Hard Deletions:** Deleting a document from a deal never destroys the file. It safely moves the file to the **Archive**, preserving full version history and audit evidence.
4. **Immutable Audit Trail:** Every login attempt, file upload, move, rename, stage transition, approval, and permission change is recorded permanently in a tamper-proof audit log.
5. **The Application Cannot Destroy a Document:** the credential the Deal
   Room uses to talk to storage has no delete permission at all. Only a
   separate maintenance job, holding a different key, can remove a file —
   and only one already archived or rejected. A fault in the application
   cannot take a document with it.

---

## 2. User Roles & Permissions Hierarchy

There are three key roles and permission capabilities in the Deal Room:

```
┌────────────────────────────────────────────────────────┐
│                   Owner (Fund Sponsor)                 │
│  • Full Admin privileges                               │
│  • Cannot be demoted, deactivated, or deleted by anyone│
└───────────────────────────┬────────────────────────────┘
                            │
┌───────────────────────────▼────────────────────────────┐
│                    Administrators                      │
│  • Full access to all deals, folders & files           │
│  • Can create deals, master folders, and invite users  │
│  • Can review/approve requests & restore from Archive  │
└───────────────────────────┬────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐       ┌───────────────────────┐
│       Approver        │       │    Standard Member    │
│ • Member role         │       │ • Member role         │
│ • "Can Approve" = YES │       │ • "Can Approve" = NO  │
│ • Reviews uploads,    │       │ • Restricted by       │
│   deletions & tasks   │       │   Folder Matrix       │
└───────────────────────┘       └───────────────────────┘
```

### Detailed Role Matrix

| Capability | Owner | Administrator | Approver | Standard Member |
| :--- | :---: | :---: | :---: | :---: |
| **Create New Deals** | Yes | Yes | No | No |
| **Change Deal Stage** | Yes | Yes | No | No |
| **Manage Global Master Folders** | Yes | Yes | No | No |
| **Bypass Folder Restrictions** | Yes | Yes | No | No |
| **Access "Users & Permissions"** | Yes | Yes | No | No |
| **Reset Team Member Passwords** | Yes | Yes | No | No |
| **Access Approvals Queue** | Yes | Yes | Yes | No |
| **Approve / Reject Requests** | Yes | Yes | Yes | No |
| **Access Global Activity Log** | Yes | Yes | No | No |
| **Access Global Archive** | Yes | Yes | No | No |
| **Upload Files Directly** | Instant Active | Instant Active | Instant Active | Needs Approval |
| **Archive Files Directly** | Instant Archive | Instant Archive | Instant Archive | Needs Approval |
| **Work on Tasks & Comments** | Yes | Yes | Yes | Yes |

---

## 3. Account Setup & Signing In

### First-Time Login (Account Activation)
1. You will receive your Deal Room URL (e.g., `https://deals.vihaangautam.dev`), your registered email address (e.g., `samir@lilkis.in`), and a temporary 14–16 character password.
2. Navigate to the login page and enter your credentials.
3. **Mandatory Password Change:** Because this is your first sign-in, the system will immediately require you to create a secure personal password before entering.
4. Passwords must be at least 10 characters long and confirm correctly.

### Security Lockout Safeguard
* To protect sensitive deal data against brute-force attacks, entering an incorrect password **5 consecutive times within a 15-minute window** will temporarily lock the account for 15 minutes.
* If locked out, contact an Administrator to reset your temporary password, or wait for the 15-minute window to expire.

### Updating Your Password
* Click your name or avatar in the top-right corner of the header.
* Select **Change password** from the dropdown menu.
* Enter your current password, type your new one, and click **Update
  password**.

> On the forced change at first sign-in there is no current-password
> field. Signing in with the temporary one has already proved who you are.

---

## 4. Deals & Pipeline Management

Deals represent the companies, borrower entities, or transactions being evaluated by the fund.

### The Deal Stages
A deal always exists in one of four distinct stages:
1. **New:** An early-stage prospect or initial opportunity undergoing preliminary evaluation.
2. **Running:** An active transaction where due diligence, financial modeling, legal review, and committee approvals are actively taking place.
3. **Successful:** The transaction has closed, agreements are executed, and capital is deployed. The deal is preserved for historical reference and recordkeeping.
4. **Dropped:** The transaction did not proceed (e.g., failed due diligence, rejected terms). Stored in the archive state for compliance audits.

### Filtering and Finding Deals
On the **Deals** homepage:
* Use the stage filter tabs:
  * **New:** Deals in the early pipeline.
  * **Running:** Active transactions.
  * **Old:** Closed transactions (`Successful` or `Dropped`).
* Use the **Search deals** bar to instantly filter deals by company name, borrower name, or short code.

### The Four Tabs Inside a Deal
* **Documents** — the folder tree and the file table. Where most of the
  work happens.
* **Tasks** — only on `Running` deals. A deal that has not started, or has
  closed, has no task list and no tab for one.
* **Comments** — the deal's discussion thread. Worth knowing what arrives
  here on its own: the **reason given for a stage change** is posted as a
  comment, and so is an **approver's reply** to a request. Both would
  otherwise sit in places only an administrator can read. One level of
  replies; authors can edit for 15 minutes.
* **Activity** — **administrators only.** Every action on this deal, with
  filters for person, action and date, plus a keyword search.

The tab counts are each counted separately — `Comments 2 · Activity 41`
means two comments and forty-one history entries, not a total.

### Creating a New Deal (Admins Only)
1. Navigate to **Deals** in the left sidebar.
2. Click the green **+ New deal** button in the top right.
3. Fill in the required fields:
   * **Deal Name:** Full title of the project (e.g., `Aura Life Sciences Debt Facility`).
   * **Short Code:** A 2 to 6 letter identifier (e.g., `AURA`, `KRSN`). This code is permanently used as the prefix for all task keys (e.g., `AURA-1`, `AURA-2`).
   * **Borrower / Company:** Legal name of the operating company.
   * **Summary:** A concise executive summary of the opportunity (maximum 280 characters).
4. Click **Create deal**.

The new deal shows all of the master folders immediately. Nothing is
copied into it — the folders are global, which is why renaming one renames
it inside every deal, including closed ones.

> The facility amount is not asked for at creation. Set it afterwards by
> editing the deal.

### Changing Deal Stage
*Administrators only.*
1. Inside the deal, click **Change stage** in the top-right header.
2. Pick the target stage. Only the moves that are legal from where you are
   now are offered: `New` goes to Running or Dropped, `Running` to
   Successful or Dropped, and `Successful` is final. A **Dropped** deal can
   be reopened, but only back to the stage it was dropped from — the
   dialog works that out and offers the one option.
3. **Mandatory reason:** type an explanation, at least 5 characters (e.g.
   *"Investment Committee approved the ₹45 Cr facility on 26 Oct"*).
4. Click **Change stage**.

The reason is recorded in the deal history *and* posted as a comment on
the deal's **Comments** tab — the history is admin-only, so without that
the one sentence explaining why a deal started would be invisible to the
people doing the work. Everyone on the deal can read it, so write it for
them.

> Closing a deal makes it read-only: no uploads, renames, deletion
> requests, task edits or new comments. Downloads keep working.

---

## 5. Folders & Document Organization

The Deal Room utilizes a two-tier folder structure designed for consistency across deals while allowing deal-specific flexibility.

### Tier 1: Master Folders (Global Templates)
Master folders appear automatically inside **every deal room**. When an Administrator renames, reorders, or adds a master folder under **Admin > Folders**, that change applies across the entire platform immediately.

The eight master folders the Deal Room ships with, in display order:

1. **Minutes of the meeting** — IC memos, partner notes, borrower call summaries.
2. **Bank documents** — statements, sanction letters, banking correspondence.
3. **Security documents** — hypothecation deeds, charge annexures, guarantees.
4. **Legal documents** — ROC searches, title reports, litigation history, opinions.
5. **Agreements** — term sheets, facility agreements, executed contracts.
6. **Government regulation special to the case** — regulatory filings and approvals specific to the transaction.
7. **Miscellaneous** — anything that does not belong in the folders above.
8. **Borrower details** — KYC packs, board resolutions, promoter identity documents.

These are starting points, not fixtures. Rename, reorder or add to them
under **Folders** to match how the fund actually files things; a folder
cannot be deleted while any deal still has a document in it, or while it
has subfolders.

### Tier 2: Deal-Specific Subfolders
Inside an individual deal, an **Administrator** can create subfolders
under any folder. (Creating folders is an admin action, like every other
folder change — members file documents into them but do not make them.)

* *Example:* under `Minutes of the meeting`, subfolders for `March 2026`,
  `April 2026`, or `Credit committee`.
* Subfolders exist **only within that one deal**. Two deals can each have
  their own `March 2026` under the same parent without colliding.
* They nest as deep as you like, though the sidebar stops indenting after
  four levels.
* **Access is never set on a subfolder.** It is whatever the viewer has on
  the top-level folder its tree hangs off. So a subfolder created inside
  `Borrower details` is as restricted as `Borrower details` from the
  moment it exists — and a subfolder inside a folder you have no access to
  is not listed for you at all, because its name alone can give something
  away.

**To create one:** hover the folder in the left-hand list and click the
small folder-plus icon that appears on the right of the row. Name it in
the dialog and click **Create folder**.

---

## 6. Managing Documents

### Folder Permission Levels
Your access to each folder is determined by the Administrator:
* **None (`🔒` Locked):** the folder still appears in the list, with a lock
  icon and the tooltip *"You don't have access to this folder. Ask
  Samir."* — you can see that it exists, which is deliberate, so you know
  what to ask for. Opening it shows *"Ask Samir if you need to see these
  files."* and no filenames.
* **View (`👁️` Read-Only):** You can preview and download existing active files, but cannot upload or delete.
* **Contribute (`✏️` Full Collaboration):** You can view, download, upload new documents, and submit deletion requests.

### Supported File Formats & Limits
* Supported formats: **PDF**, Word documents (`.doc`, `.docx`), Excel spreadsheets (`.xls`, `.xlsx`), and CSV files (`.csv`).
* Maximum file size: **2 GB per file**.

### Uploading a Document
1. Inside a deal, open the **Documents** tab.
2. Select the destination folder in the left column.
3. Click the green **Upload files** button in the header.
4. Drag and drop your file into the dashed upload area, or click **Choose files**.
5. Once selected, the upload progress bar will track progress until complete.
6. **What happens next:**
   * If you are an **Administrator or Approver**, the file is published immediately as **Active**.
   * If you are a **Standard Member**, the file enters **Pending approval** status and is sent to the Approvals queue.

### Moving a Document to Another Folder
If a document was placed in the wrong folder:
1. Locate the document in the file table.
2. Click the three-dots action menu (`•••`) on the right side of the row.
3. Select **Move**.
4. In the modal, choose the new **Destination folder** from the dropdown. (The current folder is automatically excluded).
5. Click **Move document**.

> Moving needs `Contribute` on **both** the folder it leaves and the one
> it goes to, and it is recorded in the audit trail with both folder
> names. Note that a folder carries its own access list, so moving a file
> changes who can see it.

### Renaming a Document
1. Click the row action menu (`•••`) and select **Rename**.
2. Enter the new display name (e.g., `Aura_Facility_Agreement_Final_Signed.pdf`).
3. Click **Rename**.
4. *Note:* The display name updates everywhere, but the immutable original file name and cryptographic hash are retained for compliance audit trails.

### Deleting or Archiving a Document
1. Click the row action menu (`•••`) and select **Delete** (or **Request deletion**).
2. Enter an optional reason explaining why the document is being removed.
3. **Outcome:**
   * **For Administrators:** The file is immediately moved to the **Archive** (`Admin > Archive`) and hidden from the deal view.
   * **For Standard Members:** A deletion request is submitted to the Approvals queue. The file remains visible with a `Deletion requested` badge until an approver approves the request.

---

## 7. Approvals & The Maker-Checker Workflow

The **Approvals** screen is the operational command centre for fund
compliance. Administrators find it under **Admin**; an approver who is not
an administrator gets it on its own in the sidebar, above everything else
they can reach.

### What Requires Approval?
When standard members perform any of the following actions, the platform holds the change in suspense:
1. **Document Uploads:** The file is held in `pending` state and cannot be downloaded by third parties until approved.
2. **Document Deletions:** The file remains active until the deletion request is approved.
3. **Task Reassignments:** If a member reassigns a task to another colleague, the transfer must be approved.
4. **Task Deletions:** Requests to delete tasks are held until approved.

### Reviewing and Deciding on Requests
1. Navigate to **Approvals** in the left sidebar.
2. Use the category tabs (`All`, `Uploads`, `Deletions`, `Reassignments`, `Task deletions`) or the search bar to locate items.
3. The queue is a table, one row per request, with columns for **Type**,
   **Item** (the filename is a link — click it to read the document before
   deciding), **Deal**, **Requested by**, **Requested on**, **Their note**
   and **Your reply**.
4. **Tick the checkbox** on each row you want to act on. A bar appears
   above the table with **Approve selected** and **Reject selected**.
   There is no per-row approve button: the queue is built to be worked in
   batches, because forty uploads should be forty ticks and one click.
5. **To approve:** tick the rows, click **Approve selected**. Files become
   Active and task changes take effect at once.
6. **To reject:** tick the rows, click **Reject selected**, and give a
   reason in the dialog (e.g. *"Please upload the version with borrower
   sign-off on page 12"*).
7. **To say something to one person:** type in that row's **Your reply**
   box before deciding. Typing in it ticks the row for you, and a reply
   typed on a row beats the shared reason given in the reject dialog — so
   rejecting eleven for one reason while telling Meera something of her
   own is still one pass down the queue.

**Where the reply goes.** It is posted as a comment from you, on the
thread the request came from: the **task's** comment thread if the upload
was made from a task, otherwise the deal's **Comments** tab. The requester
never sees this queue, so an answer left here is an answer nobody reads —
and in the thread they can reply to it. Everyone on that deal can see it.

An approval with nothing written in **Your reply** posts no comment. The
file turning Active is the message.

---

## 8. Tasks & Due Diligence Tracking

Tasks allow deal leads and analysts to track closing conditions, legal checklist items, and condition precedent (CP) trackers.

### Task Anatomy
* **Key:** An automated, persistent identifier derived from the deal code (e.g., `AURA-1`, `AURA-2`).
* **Title & Description:** Detailed scope of the requirement.
* **Status:**
  * `Not started`
  * `In progress`
  * `Awaiting approval` (submitted with attachments)
  * `Done`
* **Dates:** Optional Start Date and Due Date.
* **Assignee:** The person responsible for completing the work.
* **Attachments:** Documents linked directly to the task from the deal's document library.
* **Needs Attention:** A red warning indicator displayed if an attached file was rejected during review.

### Creating and Assigning a Task
1. Inside a deal, select the **Tasks** tab.
2. Click **+ New task**.
3. Enter the task title, description, priority, due date, and select an assignee.
4. Click **Create task**.

### Linking Documents to a Task
1. Open the task by clicking its row.
2. Click the **Attach** button.
3. Choose **Link an existing document** to pick a file from the deal library, or choose **Upload new file**.
4. Once attached, team members can view the supporting proof directly from the task screen.

### Completing a Task
* If the task has pending file uploads, click **Submit for approval**.
* When all required documents are approved, the task automatically advances to **Done**.

---

## 9. Team Management & The Permission Matrix

Administrators manage user accounts and folder permissions under **Admin > Users & permissions**.

### Adding a New User
1. Navigate to **Admin > Users & permissions**.
2. On the **Users** tab, click **Add user**.
3. Fill in the user details:
   * **Full Name:** (e.g., `Meera Sharma`).
   * **Email Address:** (e.g., `meera@lilkis.in`).
   * **Role:** Choose `Member` or `Admin`.
   * **Can approve requests:** Toggle `Yes` if this user should have delegated approval authority.
   * **Copy folder access from:** Optionally copy an existing colleague's folder permissions to save setup time.
4. The system automatically generates a **Temporary Password** (14 phonetic, phone-safe characters).
5. Click **Copy password** and provide it securely to the user.
6. Click **Add user**.

### Using the Folder Access Matrix
To customize which folders a member can access:
1. Open **Admin > Users & permissions** and select the **Folder access** tab.
2. A grid displays all team members as rows and all master folders as columns.
3. For each intersection, click to toggle access:
   * **`N` (None):** User cannot see or access the folder (`🔒`).
   * **`V` (View):** User can browse and download files, but cannot upload or delete.
   * **`C` (Contribute):** User can upload documents and request deletions.
4. Changes take effect instantly—no save button is needed.

---

## 10. Document Archive & Retention Governance

The **Archive** (`Admin > Archive`) protects against data loss and provides regulatory compliance.

### How Files Enter the Archive
Files enter the Archive when:
* An Administrator deletes a document directly.
* An Approver approves a team member's deletion request.

### Archive Capabilities
* **Search & Filter:** Filter deleted documents by Deal, Folder, Deleted by, Approved by, or Date Range.
* **Download:** Download any historical document directly from the archive.
* **Restore:** Click `•••` -> **Restore**. The document is immediately returned to its original deal and folder in `active` status.
* **Permanent Purge:** Only Administrators can permanently remove an archived document.

### Retention Policy
* At the top of the Archive screen, the **Retention Policy** indicates how long deleted files are stored.
* Default setting: **Keep forever** (recommended for SEBI compliance).
* To set a time limit, click **Change** next to Retention and pick one of
  **30 days**, **1 year** or **7 years**. Files older than that are removed
  from storage for good by a nightly job; the record of who uploaded and
  deleted them is always kept.
* Each row shows how long is left — "27 days left", or "Due for deletion"
  once past, or "Kept forever" under the default.

---

## 11. Activity Audit Trail

The **Activity** log (`Admin > Activity`) is an append-only, tamper-proof record of every event across the fund.

### Logged Events
The audit feed records:
* User sign-ins, logouts, and failed authentication attempts.
* Deal creations, updates, and stage changes (with full explanations).
* Document uploads, renames, moves, and deletions.
* Approvals and rejections (with notes from both parties).
* Task creation, assignment, reassignment and deletion.
* User accounts created, roles changed, passwords reset.
* Folder access changed in the matrix.

Comments are **not** in the audit log. They live on the deal or the task
and are read there; deleting one leaves "Comment removed" rather than
removing the fact that something was said.

### Filtering the Audit Log
Use the filter controls at the top of the feed:
* **Deal:** Isolate actions belonging to a single transaction.
* **Anyone:** Filter by a specific person (e.g., actions taken by `Samir`).
* **Any action:** Filter by event type (e.g., `document.uploaded`, `permission.changed`, `deal.stage_changed`).
* **Date Range:** Filter from date to date.
* **Search:** Free-text search matching document titles, borrower names, or comments.

---

## 12. Step-by-Step "How-Do-I" Reference

Use this quick-reference section to find immediate answers to common questions:

### How do I invite a new colleague to the Deal Room?
1. Go to **Admin > Users & permissions** in the sidebar.
2. Click **Add user**.
3. Enter their Name, Email, Role (`Member` or `Admin`), and toggle whether they can approve.
4. Copy the generated 14-character temporary password and send it to them securely.
5. Click **Add user**.
6. Switch to the **Folder access** tab and set their permissions (`V` for View, `C` for Contribute) across the folders they need.

### How do I let an analyst into one folder and not the others?
1. Go to **Admin > Users & permissions** and click **Folder access**.
2. Find the analyst's row and the column for the folder — say **Bank
   documents**.
3. Click `V` for view-only or `C` to let them upload. It saves as you
   click.

Everything else stays at `N`, which is where everyone starts. Admins do
not appear as adjustable rows: they have every folder by definition, which
the matrix shows as "Full access".

### How do I move a document to a different folder?
1. Open the deal and go to the **Documents** tab.
2. In the file row, click the three-dots menu (`•••`) on the right.
3. Click **Move**.
4. Select the target folder from the dropdown and click **Move document**.

### How do I create a deal-specific subfolder (e.g. "March 2026")?
*Administrators only.*
1. Go to the deal's **Documents** tab.
2. Hover the folder it should sit inside — say *Minutes of the meeting* —
   in the left-hand list.
3. Click the small folder-plus icon that appears at the right of that row.
4. Type the name and click **Create folder**. It exists on this deal only,
   and inherits that folder's access.

### How do I approve a pending document uploaded by an analyst?
1. Click **Approvals** in the sidebar.
2. Click the **Uploads** tab.
3. **Click the filename** to open the document in a new tab and read it.
   Approving from a filename and a folder is a guess.
4. Close that tab, tick the checkbox on the row, and click **Approve
   selected**. Add something in **Your reply** first if you want to tell
   them anything.

### How do I restore an accidentally deleted document?
1. Go to **Admin > Archive** in the sidebar.
2. Find the file in the table (use the search bar if needed).
3. Click the three-dots menu (`•••`) on the right.
4. Click **Restore**. The file returns to its original deal and folder.

### What happens if I upload the same file twice?
* The system checks the file's unique cryptographic hash (SHA-256).
* If an identical copy already exists in that deal — as Pending or Active
  — the upload is refused and names where it already is: *"Already in Bank
  documents as 'HDFC stmt Apr.pdf'"*. The same file in two different deals
  is fine; this only guards against duplicates inside one deal.

### How do I change a deal from "New" to "Running"?
1. Open the deal.
2. In the top-right header, click **Change stage**.
3. Select **Running**.
4. Type the reason in the text box (e.g. *"Preliminary due diligence
   completed, moving to committee review"*). At least 5 characters.
5. Click **Change stage**.

> The reason is not filed away out of sight. It is posted as the first
> comment on the deal's **Comments** tab, so the people doing the work can
> read why it started — the deal history is admin-only.
