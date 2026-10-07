# DESIGN.md — Lilkis Deal Room

Visual and interaction specification. Read `PRD.md` first for what gets built; this document says how it looks and behaves. Where this document and PRD.md disagree, **PRD.md wins** — report the conflict rather than guessing.

Reference UI: hellobonsai.com — calm, dense, professional B2B internal tool. Bonsai's documented structure (left sidebar, list-first views, row-end `•••` menus, bulk select) is the model. Its in-app colours, font and density are not public, so every token below is a decision anchored to Bonsai's two published brand colours (`#22AD01`, `#F2F7F2`).

---

## 1. Design Principles

**Calm over impressive.** An internal tool for ten people. No flashy transitions, no gradient splashes, no hero imagery.

**Lists before dashboards.** Every primary page is a table. There are no KPI tiles, no charts, no health meters. Users come to find a file or a task.

**Dense but breathable.** 40px rows, 13px table text, 24px gutters. A 1366×768 laptop shows about 12 rows without scrolling.

**Nothing on screen that the database can't produce.** If a value isn't a column in ARCHITECTURE.md §4, it does not appear in the UI. This rule killed an entire earlier mockup round.

**Status is visible without clicking** — but only when it isn't the normal state. Approved documents and active deals carry no badge; a pill means "this differs from the default".

**Plain language.** No compliance jargon, no internal codes, no provider names. If a string needs domain knowledge, rewrite it.

**Hierarchy through weight, not decoration.** Size and weight carry hierarchy. Never underline, italicise or add an icon to achieve it.

---

## 2. Anti-Patterns

Banned outright:

- Purple, indigo or violet anywhere. Gradients of any kind, including gradient text.
- Glassmorphism, backdrop blur, frosted panels, decorative blobs, noise textures.
- Emoji as icons or in copy.
- Box shadows on resting cards or table rows — use a border.
- Radius above 8px on any container (pills are full-round).
- Animations over 150ms (modal enter may be 200ms).
- Centred layouts above 600px width. Left-align everything, including inside the login panel.
- Stat tiles, trend arrows, progress meters on any page.
- Uppercase letter-spaced labels. Section headings are sentence case.
- Red for anything that is not an error or a destructive action. A restricted folder is not an error. A dropped deal is not an error.
- Confirmation dialogs for non-destructive actions (upload, comment, create).
- Toasts for errors that need action — those render inline.
- Spinners for page loads — use skeleton rows.
- Horizontal scroll on the page body above 1024px. Only the permission matrix scrolls inside its own container.
- Placeholder-only form labels. Lorem ipsum. Mascots. "Welcome back!" banners.
- IDs, hashes, block numbers, object keys or room codes shown to the user.

---

## 3. Design Tokens

### 3.1 Colour

```css
:root {
  /* Brand */
  --brand-50:   #F2F7F2;   /* active nav background, selected row */
  --brand-100:  #DFF0DF;
  --brand-600:  #22AD01;   /* active nav bar, focus ring, progress fill, selected checkbox */
  --brand-700:  #177A01;   /* PRIMARY button background, links (5.5:1 on white) */
  --brand-800:  #136401;   /* primary hover */
  --brand-900:  #0F5001;   /* primary pressed */

  /* Canvas / Surface */
  --canvas:          #F6F7F6;
  --surface:         #FFFFFF;
  --surface-sunken:  #F9FAF9;   /* table header, read-only field, inline create row */
  --surface-hover:   #F2F5F2;   /* row hover */

  /* Border */
  --border:          #E3E6E3;   /* dividers, container outlines */
  --border-strong:   #CDD2CD;   /* inputs, secondary buttons */
  --border-danger:   #FDA29B;

  /* Text */
  --text-primary:    #1B1F1C;   /* 16:1 */
  --text-secondary:  #4A514C;   /* 8:1  */
  --text-tertiary:   #6B726D;   /* 4.9:1 — metadata, placeholders, column headers */
  --text-disabled:   #9AA19C;   /* never carries required information */
  --text-inverse:    #FFFFFF;

  --text-danger:     #B42318;
  --text-warning:    #8A5A00;
  --text-info:       #1E5AA8;

  /* Banners */
  --danger-50:   #FBE9E7;
  --warning-50:  #FDF3DC;
  --info-50:     #E8F0FA;
  --danger-700:  #B42318;
}
```

> **Note on `#22AD01`.** It is 3.0:1 on white and therefore fails AA for text. It is used only for non-text elements where 3:1 applies: the focus ring, the 3px active-nav bar, the progress-bar fill and the checked checkbox. Every green *button* and every green *link* uses `--brand-700`.

**Status pills.** 20px tall, 8px horizontal padding, fully rounded, 12px/500, sentence case, 6px leading dot in the text colour.

| Status value (DB) | Label shown | Background | Text / dot | Appears on |
|---|---|---|---|---|
| `new` | New | `#EEF0EE` | `#4A514C` | Deal |
| `running` | Running | `#E8F0FA` | `#1E5AA8` | Deal |
| `successful` | Successful | `#E5F4E1` | `#177A01` | Deal |
| `dropped` | Dropped | `#F3EFEA` | `#6B5A48` | Deal — muted brown, never red. Dropping a deal is a decision, not a failure. |
| `uploading` | Uploading… | `#FDF3DC` | `#8A5A00` | Document |
| `pending` | Pending approval | `#FDF3DC` | `#8A5A00` | Document |
| `active` | — **no pill** | — | — | Document. Active is the normal state; a pill on every row is noise. |
| `delete_requested` | Deletion requested | `#FDF3DC` | `#8A5A00` | Document |
| `rejected` | Rejected | `#FBE9E7` | `#B42318` | Document |
| `archived` | Archived | `#EEF0EE` | `#4A514C` | Document (admin Archive only) |
| `not_started` | Not started | `#EEF0EE` | `#4A514C` | Task |
| `in_progress` | In progress | `#E8F0FA` | `#1E5AA8` | Task |
| `submitted` | Awaiting approval | `#FDF3DC` | `#8A5A00` | Task |
| `done` | Done | `#E5F4E1` | `#177A01` | Task |
| `needs_attention` *(flag)* | Needs attention | `#FBE9E7` | `#B42318` | Task — a second pill beside the status pill, not a replacement |

Enum names above are exactly those in ARCHITECTURE.md §4. Do not invent `todo` or `awaiting_approval` as values.

**Avatars.** 24px circle, 2-letter initials, 11px/600, `#1B1F1C` text. Background is picked by hashing the user id into six muted tints: `#E5F4E1`, `#E8F0FA`, `#FDF3DC`, `#F3EFEA`, `#EEF0EE`, `#EDEBF3`. No photographs. Nothing saturated.

### 3.2 Typography

**Font:** Inter, self-hosted woff2 from `public/fonts/`, weights 400/500/600. Apply `font-feature-settings: "tnum" 1` to **numeric cells only** — never to a whole date string, or `5 Jan 2026` renders with a visible gap after the day.

| Token | Size / line | Weight | Use |
|---|---|---|---|
| `title-page` | 20 / 28 | 600 | Page title |
| `title-section` | 15 / 22 | 600 | Section headings, dialog titles, folder name |
| `title-task` | 18 / 26 | 600 | Task title on the detail page |
| `body` | 14 / 20 | 400 | Paragraphs, inputs, comments |
| `body-strong` | 14 / 20 | 500 | Nav items, button labels, form labels |
| `table` | 13 / 20 | 400 | Table cells; the primary cell is 500 |
| `meta` | 12 / 16 | 400 | Timestamps, helper text, second lines |
| `label` | 12 / 16 | 500 | Column headers, section labels, rail labels — **sentence case** |
| `pill` | 12 / 16 | 500 | Status pills and badges |

At most three sizes per view region. Never bold a whole paragraph.

### 3.3 Spacing, radius, elevation

**Spacing (px):** 2, 4, 6, 8, 12, 16, 20, 24, 32. Component padding 8/12/16. Page gutters 24. Section gaps 24 or 32.

**Radius:** 4px checkboxes and small tags · 6px buttons, inputs, menus · 8px panels, dialogs, drawers · full on pills and avatars.

**Borders:** 1px `--border` for dividers and containers; 1px `--border-strong` for inputs and secondary buttons. Focus ring: 2px `--brand-600`, 2px offset.

**Elevation:** Level 0 (border only) is the default for cards and panels. Level 1 for dropdowns, popovers and toasts: `0 4px 12px rgba(16,24,16,.08), 0 0 0 1px #E3E6E3`. Level 2 for dialogs: `0 12px 32px rgba(16,24,16,.12)` with a `rgba(27,31,28,.32)` overlay and no blur.

**Motion:** 120ms ease-out for hover and menus, 180ms for dialogs. `prefers-reduced-motion` disables transitions.

---

## 4. Layout

### 4.1 Shell

```
┌────────────────────────────────────────────────────────────────┐
│ 48px top bar   [L] Lilkis Deal Room          [SB] Samir Biyani │
│                                                          Admin  │
├────────────┬───────────────────────────────────────────────────┤
│  232px     │  Content — max 1400px centred, 24px gutters       │
│  sidebar   │  bg: canvas                                       │
│  fixed     │                                                   │
└────────────┴───────────────────────────────────────────────────┘
```

**Top bar.** 48px, `--surface`, 1px bottom border. It carries exactly two things.

- Left: 20px square logo mark, then `Lilkis Deal Room` in 15/600.
- Right: 24px initials avatar, then name in 13/500 with the role beneath in 12/400 `--text-tertiary`. One role word (`Admin`, `Member`), never `Sponsor / Admin`. Clicking opens a menu: `Change password`, `Log out`.

No global search (each page has its own, scoped). No notification bell — notifications are a PRD §3 non-goal, and a bell that does nothing is a lie on screen.

**Content area.** 24px gutters, capped at 1400px and centred. A 1200px cap letterboxes the approvals table on a 1440px screen; 1400px keeps the wide tables full on a 1440px laptop while stopping a row from running the whole width of a 1920px monitor, where the eye loses the line between the first and last column. The header and tab bands run edge to edge so their bottom borders do, but their contents sit in the same 1400px column, so the search lines up with the table it filters.

### 4.2 Sidebar

232px, `--surface`, 1px right border, full height, fixed. Identical on every page.

```
Deals                 12
My Tasks               4

ADMIN                              ← group label, admin only
Approvals             (3)          ← green pill
Folders
Users & permissions
Archive
Activity
```

- Nav rows 36px, 12px horizontal padding, 16px lucide icon, 8px gap, label 14/500.
- Active: `--brand-50` background, `--brand-700` text, 3px `--brand-600` bar on the left edge.
- `ADMIN` is a group label in 12/500 `--text-tertiary`, uppercase with tracking — the one permitted exception to §2, because it labels a group rather than a section of content. The whole group is hidden from non-admins.
- Counts right-aligned, 12/400 `--text-tertiary`, in a `#EEF0EE` pill. `Approvals` is the exception: `--brand-700` background, white 11/600, hidden at zero. It refreshes every 60 seconds and after any mutation (PRD F7).
- **Nothing below the nav.** No status card, no version string, no connection indicator.
- The active item reflects the *section*, not the sub-page. Inside a deal's Tasks tab, `Deals` is active — not `My Tasks`.

### 4.3 Page header

64px, `--surface`, 1px bottom border, 24px side padding.

- Left, two lines: breadcrumb in 12/400 `--text-tertiary` (`Deals /`), then the title in 20/600 with the stage pill 8px after it where applicable.
- Right: secondary actions, then one primary action.

Deal pages add a 40px tab row directly beneath, with a 2px `--brand-600` underline on the active tab. The breadcrumb appears **once per page** — never again inside the content card.

---

## 5. Components

### 5.1 Button

| Variant | Background | Text | Border | Use |
|---|---|---|---|---|
| `primary` | `--brand-700` | white | none | One per view region. Hover `--brand-800`, pressed `--brand-900`. |
| `secondary` | `--surface` | `--text-primary` | 1px `--border-strong` | Hover `--surface-sunken`. |
| `ghost` | transparent | `--text-secondary` | none | Toolbar and row actions. |
| `destructive` | `--danger-700` | white | none | Inside confirmation dialogs only. |

Sizes: `md` 36px / `px-4` / 14px-500 (default) · `sm` 32px / `px-3` / 13px-500 (tables, toolbars).

Icon 16px, 6px gap, left of the label. Loading keeps the button width and swaps the label for a 14px spinner plus `Saving…`. Disabled uses 50% opacity, `cursor: not-allowed`, and a tooltip saying *why* — "Only Samir can change the stage."

### 5.2 Data table

A white container, 1px border, 8px radius.

- Header row 36px, `--surface-sunken`, labels 12/500 `--text-tertiary`, **sentence case**. Sortable headers show a 12px chevron when active. No multi-column sort.
- Rows 40px, 1px `--border` divider, none on the last row. Hover `--surface-hover`. Selected `--brand-50`.
- Primary cell 13/500 `--text-primary` and is the click target. A second line beneath it uses `meta`. Other cells 13/400 `--text-secondary`.
- Numbers and dates right-aligned, tabular figures on the digits only. Dates render `14 Jan 2026`. Relative time (`2 hours ago`) appears only in a Last-activity column, with the absolute time on hover.
- **Row actions** live in a ghost `•••` button at the row end, revealed on hover or focus, always visible on touch. The `•••` column header is empty — never put the glyph in the header.
- Toolbar above the table, 40px: search input (240px) on the left, then filter buttons; result count right-aligned in `meta`. Do not give the search its own empty band.
- Loading: 8 skeleton rows at 60% / 30% / 20% widths, no shimmer. Error: inline banner inside the table area with a `Retry` action.
- Footer: count on the left in 12/400, pagination on the right. **Inside a filtered tab, the count is that tab's count** — a tab showing 3 of 3 says `3 deals` and renders no pagination.

### 5.3 Folder list (Deal → Documents, left column)

A bordered panel, 260px wide, containing only folder rows. No heading, no filter box, no size summary.

Each row is 36px: 16px folder icon `--text-tertiary`, name 13/500, active file count right-aligned in 12/400 `--text-tertiary`. Selected row: `--brand-50` background, `--brand-700` text.

**A folder the member has `None` on is still rendered** (PRD §7: "See all deals and folder names — Yes"). In place of the count it shows a 16px lock icon, its name sits in `--text-tertiary`, and the tooltip reads *"You don't have access to this folder. Ask Samir."* No red, no `RESTRICTED` chip. Clicking it shows the no-access empty state on the right.

Folder names must not truncate. The panel is sized for the longest PRD name, `Government regulation special to the case`; if that overflows at 260px, wrap to two lines rather than ellipsis.

Rationale for a list over folder tiles: eight fixed folders read faster as a list, and a list leaves the right side free for the file table.

### 5.4 File row

Columns: `Name` · `Size` · `Uploaded by` · `Uploaded on` · `Status` · `•••`

One line, 40px. There is no `Version` column — PRD §3 lists versioning as a non-goal, and a new upload is a new document. No hash, no checksum, no object key.

- 16px lucide file-type icon (`FileText`, `FileSpreadsheet`, `File`) in `--text-tertiary`. Type is conveyed by shape, never by a coloured badge.
- Name 13/500, the click target; clicking downloads. Row menu: `Download`, `Rename`, `Request deletion` (Contribute only).
- **Pending (own upload):** row text `--text-tertiary`, name not a link, `Pending approval` pill, menu offers only `Withdraw upload`. Tooltip on the name: *"Samir needs to approve this file before others can see it."*
- **Rejected (own upload):** `--text-tertiary` with a `Rejected` pill and a second line in 12/400 `--danger-700` — `Reason: Wrong folder – upload to Security documents`. No menu. The row disappears after 30 days (PRD F11).
- **Deletion requested:** normal text, amber pill, still downloadable, no strikethrough. The file is live until the request is approved.
- **Integrity check failed** (approvers only): `Check failed` pill in danger colours, tooltip *"File didn't match what was uploaded. Reject and re-upload."* Covers PRD §10.
- **Inline rename:** the name becomes a 32px input holding the base name only, with the extension pinned as a `--text-tertiary` suffix. Enter saves, Esc cancels, blur saves. Errors render under the input.

Size and date columns must be wide enough that `4.2 MB` and `14 Jan 2026` never wrap.

### 5.5 Multi-file upload dialog

640px. Title: `Upload to Sharma Infra Ltd`.

- **Folder select** at the top, labelled `Folder`, pre-filled with the current folder, listing only folders where the user has Contribute.
- **Drop zone:** 120px, 1px dashed `--border-strong`, 8px radius. *"Drag files here or Choose files."* Helper: *"PDF, Word, Excel or CSV. Up to 2 GB each."* Dragging turns the border `--brand-600` and the fill `--brand-50`.
- Accepted types are exactly PRD F5: `.pdf .doc .docx .xls .xlsx .csv`. Images are **not** accepted; a dropped `.png` shows *"Not allowed: .png files can't be uploaded."*
- **Queue rows**, 48px, scrolling past 320px: type icon, middle-truncated name, size, a 4px progress bar (`--brand-600` on `#EEF0EE`), and a status line in 12px — one of `Preparing…` (hashing), `Uploading 42%`, `Waiting for approval`, `Failed – Retry` (danger, with a Retry ghost button), or the duplicate message below.
- **Duplicates are refused, not overridden** (PRD F5). The status line reads *"Already in Bank documents as 'HDFC stmt Apr.pdf'"* in warning colour and that row does not upload. There is no "Upload anyway" affordance.
- **Uploads start automatically when files are added.** One fewer click, and nothing is visible to other members until it is approved anyway. The footer therefore has no Upload button — only `Close` (secondary) and a left-aligned `3 of 14 uploaded` in `meta`. Closing mid-upload asks *"Uploads in progress will stop. Close anyway?"* with `Keep uploading` (primary) and `Stop and close`.
- Approver variant: the status line ends `Added` instead of `Waiting for approval`, matching the auto-approval rule in PRD F5.

### 5.6 Task list

Toolbar: search (`Search tasks`), Status filter, Assignee filter, Group by (None / Status / Assignee), Sort (Due date, Created, Updated). Right: `Create task` (primary).

Columns: checkbox · `Task` (key in 12/500 `--text-tertiary` plus title in 13/500) · `Status` pill · `Start` · `Due` · `Assignee` · `Reporter` · 16px paperclip with a count when attachments exist.

- **Priority** is a 8px dot left of the title — `#8A5A00` high, `#CDD2CD` medium, `#E3E6E3` low. **Not red**, per §2: a high-priority task is not an error. Priority has no column of its own and no row on the detail page.
- Overdue: the due date renders `--danger-700` with the word `Overdue` beside it. Colour is never the only signal.
- `needs_attention`: a `Needs attention` pill after the status pill.
- Grouped view: 32px `--surface-sunken` group headers with a count, collapsible.
- **Inline create row** at the bottom, 40px, `--surface-sunken`: a `+ Create task` ghost button that becomes an input (`What needs doing?`). Enter creates the task as Not started / Unassigned and keeps focus for the next one. Esc cancels.

Clicking a row opens the task detail as a **full page**, not a drawer and not a master-detail pane. Comments need the width and the URL has to be shareable.

### 5.7 Task detail

Two columns: main (fluid, min 560px) and a 320px right rail.

**Main column**

1. Key in 12/500 `--text-tertiary` (`SHRM-12`). No breadcrumb here — the page header already has it.
2. Title in 18/600, editable inline by permitted users (pencil on hover).
3. Action row: `Attach` (secondary, paperclip, menu: `Link a document from this deal` / `Upload a new file`) and `•••`. Status, assignee and priority controls do **not** appear here — they live in the rail, and duplicating a control in two places is how users end up unsure which one took effect.
4. `Description` section — label 12/500 `--text-tertiary`, sentence case, body 14/20. Editable users get a textarea with Save / Cancel; beneath it, `Edited by Meera Shah on 12 Jan 2026` in `meta`. Non-editors see read-only text with the tooltip *"Only Samir or the person who assigned this task can edit it."* (PRD F8.)
5. `Attachments` — 36px rows: neutral grey file icon, name, folder in `meta`, status pill when not active, download on click. A document the viewer lacks access to renders as a lock icon plus `Restricted document` in `--text-tertiary`, with **no name, no size and no link** (PRD F6). An archived one renders `Document deleted (archived)`.
6. `Activity` — underline tabs `All · Comments · History`. Comment composer on top: a 2-row textarea growing to 8, placeholder `Add a comment`, `Comment` primary-sm, Ctrl/Cmd+Enter submits. Comments: 24px avatar, name 13/500, time in `meta`, body 14/20, one level of `Reply` indented 32px. `Edit` and `Delete` show for the author within 15 minutes; a removed comment renders `Comment removed` in italic `--text-tertiary`. History rows are 12px `--text-secondary`.
7. Footer actions, right-aligned at the end of the column (not a fixed bar): `Request reassignment` (secondary) and the submit button.

**Submit button label** depends on state, not on configuration:
- No attachments in `pending` → `Mark as done`.
- One or more attachments in `pending` → `Submit for approval`, with helper text in the rail: *"Moves to Done when Samir approves 2 pending files."*

This matches PRD F8 exactly: the user presses one button and the system decides between `done` and `submitted`.

**Right rail** — bordered panel, 16px padding, sticky.

```
Status        [ ● In progress        ▾ ]

Details
Assignee      RK Ravi Kumar     Assign to me
Reporter      SB Samir Biyani
Assigned by   SB Samir Biyani
Start date    —
Due date      15 Jan 2026
Created       09 Jan 2026
Updated       14 Jan 2026, 10:22
```

Section labels sentence case, 12/500 `--text-tertiary`. Field labels in a 96px column, values 13/400. The status select is styled in its pill's colours and lists only transitions the current user is allowed to make. A pending reassignment shows an amber note under the assignee: *"Reassignment to Arjun Rao waiting for approval"* — and the assignee value does not change until approval (PRD F8).

### 5.8 Approvals queue

Page header: `Approvals`, then `23 waiting` in 13/400 `--text-tertiary`. No chip, no explanatory paragraph — the table explains itself.

Toolbar: Type filter, Deal filter, Requested-by filter.

**One action model, never two.**
- Nothing selected → the filter toolbar only. No action buttons anywhere on the page.
- One or more selected → the toolbar is replaced in place by a `--brand-50` bar: `12 selected · Approve selected · Reject selected · Clear selection`. The header checkbox selects every filtered row; past one page, a link offers `Select all 40 matching`.
- There are **no per-row Approve / Reject buttons**. There is also no `Preview` — in-browser preview is a PRD §3 non-goal.

Rows 36px. Columns: checkbox · `Type` · `Item` · `Deal` · `Requested by` · `Requested on` · `Note` · `•••`

- `Type` is a plain 12/500 text label — `Upload`, `Deletion`, `Reassign`, `Delete task`. No outlined chips.
- `Item` for a document: filename in 13/500 as a download link, folder beneath in `meta`. For a reassignment: `SHRM-12 Review term sheet` with `Ravi Kumar → Priya Nair` beneath.
- `Note` truncates with the full text on hover.
- The `•••` menu carries `Download` — without it Samir cannot inspect a file before deciding, which makes the whole screen a guess.

Reject dialog: *"Reject 3 requests?"*, an optional textarea labelled `Reason (shown to the requester)`, then `Cancel` / `Reject` (destructive).

After a decision rows fade out over 120ms and a toast reports the per-item result: `16 approved.` or `15 approved, 1 already handled by Samir` (PRD F7).

### 5.9 Permission matrix

Rows are users with a sticky 200px first column; columns are folders at 120px minimum. Each cell is a 28px segmented control: `None · View · Contribute`.

Selected segment fills: None `#EEF0EE` / View `#E8F0FA` / Contribute `#E5F4E1`, with matching text. Changed cells carry a 2px `--text-warning` left border until saved. A sticky footer appears on first change: `9 changes · Discard · Save changes`. Column header menu offers `Set everyone to…`.

Admin rows render `Full access` across every folder and are not editable.

This is the one container permitted to scroll horizontally, with the first column pinned.

### 5.10 Stage-change dialog

480px. Title: `Change stage — Sharma Infra Ltd`.

Current stage pill, an arrow, then radio cards for **only the transitions PRD §8 allows from the current stage**. Cards are 1px bordered, 6px radius, 56px tall, label plus a one-line consequence:

- **Running** — "Work has started. Tasks become available."
- **Successful** — "Deal closed successfully. Documents become read-only."
- **Dropped** — "Deal will not proceed. Documents become read-only. You can reopen it later."

**A reason is required on every transition**, not only on Dropped — PRD F3 mandates 5 to 1,000 characters on all of them, written to `deal_stage_history`. The textarea is labelled `Reason`, helper *"Recorded in the deal history."* There is no "simple confirm" variant.

Footer: `Cancel` and `Change stage` (primary, disabled until valid).

If the deal has pending approvals, an inline `--info-50` note reads: *"4 requests for this deal are still waiting. You can still approve them after the change."* (PRD §10.)

### 5.11 Empty states

Left-aligned text inside the table area. No illustration. Title 14/500, body 13 `--text-secondary`, at most one action.

| Where | Title | Body | Action |
|---|---|---|---|
| Deals → New (admin) | No new deals | Deals you create start here. | New deal |
| Deals → New (member) | No new deals | Samir adds new deals here. | — |
| Deals → Running | No running deals | Deals move here when work starts. | — |
| Deals → Old | No closed deals | Successful and dropped deals appear here. | — |
| Folder, has access, empty | No files in Bank documents | Upload statements, sanction letters and other bank records for this deal. | Upload files *(Contribute only)* |
| Folder, no access | You don't have access to Borrower details | Ask Samir if you need to see these files. | — |
| Tasks | No tasks yet | Create a task to hand off work on this deal. | Create task |
| My Tasks | Nothing assigned to you | Tasks assigned to you on running deals appear here. | — |
| Approvals | Nothing waiting for approval | New uploads, deletions and reassignments will appear here. | — |
| Archive | Archive is empty | Files you approve for deletion are kept here. | — |
| Activity | No activity yet | Actions on this deal will be recorded here. | — |
| Comments | No comments yet | Add one below. | — |
| Search, no results | No results for "sbi" | Check the spelling or clear filters. | Clear filters |

### 5.12 Toasts

Bottom-right, 360px, level-1 elevation, white, 3px left bar in the semantic colour. Success auto-dismisses at 4s. **Errors that need action are never toasts** — they render inline. Max 3 stacked. Include `Undo` wherever an undo exists (rename, for instance).

Copy is past tense and specific: `Renamed to 'SBI sanction letter.pdf'`, `Task created`, `Request sent to Samir`.

### 5.13 Confirmation dialogs

440px, only for destructive actions. The title is a question naming the object; the body states the consequence in one or two sentences; the buttons are `Cancel` (secondary) and a specific verb — never `OK` or `Yes`.

Two distinct dialogs that must not be conflated:

**Member requests deletion** (not destructive — it creates an approval request):
> **Request deletion of 'Term sheet v3.pdf'?**
> Samir will review this. If approved, the file moves to the Archive and stops appearing in Agreements.
> `Cancel` · `Request deletion` (primary)

**Admin purges from Archive** (destructive and final):
> **Permanently delete 'TS_Sharma_v1.pdf'?**
> The file will be removed from storage and cannot be recovered. The record of who uploaded and deleted it is kept.
> `Cancel` · `Delete file` (destructive)

No provider name appears in either — `OCI`, `S3` and `bucket` are banned from user-facing copy by §7.

### 5.14 Form fields

Input 36px, `--surface-sunken` fill, 1px `--border` → focus 1px `--border-strong` plus the focus ring, `px-3`, `body`. Label above in 14/500, 6px gap, 16px between fields. Helper 12px `--text-tertiary` beneath; an error replaces it in `--danger-700` and turns the border `--danger-700`.

Required fields carry no asterisk; optional ones get `(optional)` in `--text-tertiary` after the label — most fields are required, so marking the exceptions is quieter.

Validate on blur and on submit. One column only, max width 640px. Never disable submit for validation reasons except in short dialogs (stage change, reject).

---

## 6. Page Layouts

### 6.1 Login

`--canvas` full viewport with a 400px `--surface` panel, 8px radius, 1px border, 32px padding. Left-aligned contents, positioned at 40% from the left on wide screens.

```
[L] Lilkis Deal Room

Sign in

Email
[________________________]

Password
[________________________]  (show/hide)

[      Sign in      ]       ← full-width primary

Forgot your password? Ask Samir to reset it.
```

No subtitle. The product is not a compliance tool and the panel does not need a tagline. **`Forgot your password?` is static text, not a link** — PRD F1 has no self-service reset; the admin resets and the user is forced to change it on next login. No sign-up link, no social buttons.

Errors render inline above the button: *"Email or password is incorrect."* — identical wording for unknown email, wrong password and lockout (PRD F1), with *"Try again in 15 minutes."* appended when locked.

**Forced password change** reuses the panel: title `Choose a new password`, fields `New password` and `Confirm`, helper *"At least 10 characters."*

### 6.2 Deals home

Header: `Deals` with `New deal` (primary, admin only). No subtitle, no export.

Tabs: `New 2 · Running 3 · Old 14`, counts in 12/400 `--text-tertiary`. The `All · Successful · Dropped` segmented control appears **only while `Old` is active**, at the left of the toolbar below.

Columns: `Deal` · `Stage` · `Documents` · `Tasks` · `Last activity` · `Created` · `•••`

The `Deal` cell carries two lines — name in 13/500, then `SHRM · Sharma & Co Infra` in `meta`. This replaces separate code and borrower columns, which wrap badly as chips.

`Documents` is the count of active files the viewer can see — it excludes pending files and folders where the viewer has `None` (PRD F2). `Tasks` shows `done/total` and appears on the Running tab only.

There is **no amount column.** Facility amount is not in the schema and is open question §13 Q9.

### 6.3 Deal → Documents

Header: breadcrumb `Deals /`, title `Sharma Infra Ltd` plus stage pill; right, `Change stage` (admin, secondary) and `Upload files` (primary, shown when the viewer has Contribute on any folder and the deal is open).

Tabs: `Documents 28 · Tasks 5 · Activity 42`. The Tasks tab is absent on New and Old deals (PRD F8).

Old deals show an `--info-50` banner: *"This deal is closed. Files can be downloaded but not changed."*

Body: folder list (260px, §5.3) left, file table right. The file-table header is one line — folder name in 15/600 then the count in 13/400 `--text-tertiary`. No description paragraph, no per-folder buttons; upload lives in the page header only, one affordance per screen.

The folder is in the URL (`/deals/:id/documents/:folderId`) so links are shareable.

### 6.4 Deal → Tasks

Same header and tabs; the task list (§5.6) spans the full width.

### 6.5 Task detail

§5.7. Window title: `SHRM-12 Review term sheet – Lilkis`.

### 6.6 My Tasks

Header `My Tasks`. Grouped by status in the order Awaiting approval, In progress, Not started, Done (last 14 days, collapsed). An extra `Deal` column follows `Task`. Overdue sorts to the top of each group. A flat list is an acceptable demo-day cut (PRD §11).

### 6.7 Admin: Approvals

§5.8.

### 6.8 Admin: Folders

Header `Folders`, primary `Add folder`. Info line: *"Folders appear in every deal. Changes apply everywhere immediately."*

Table: drag handle (reorder) · `Name` (inline rename) · `Files across deals` · `Created` · `•••`.

Deleting a folder that holds files is **blocked, not confirmed** (PRD F4): *"Bank documents can't be deleted. 214 files in 6 deals are in this folder. Move or delete those files first."* with a single `Close`.

Add-folder dialog: `Name`, plus `Starting access for members` (radio View / None) with helper *"You can change access per person afterwards in Users & permissions."*

### 6.9 Admin: Users & permissions

Two tabs: `Users` and `Folder access` (§5.9).

Users table: `Name` · `Email` · `Role` · `Can approve` · `Status` · `Last login` · `•••` (Edit, Reset password, Deactivate/Reactivate). Header action is **`Add user`** — not "Invite user". No invitation email is sent; notifications are a PRD §3 non-goal and the label must not imply one.

Add-user dialog, 480px: Full name, Email, Role (radio Member / Admin), `Can approve requests` checkbox, Temporary password (generated 14 characters, with Copy and Regenerate), and `Copy folder access from` (a user, or Set manually). Helper: *"Give them this password directly. They'll choose a new one when they first sign in."*

Deactivated users remain in history and on assignments, tagged `(deactivated)` in `--text-tertiary` wherever their name appears (PRD §10).

### 6.10 Admin: Archive

Header `Archive`, helper *"Files approved for deletion. Kept until you remove them under retention settings."*

Columns: `Name` · `Deal` · `Folder` · `Deleted by` · `Approved by` · `Deleted on` · `Reason` · `•••` (Download, Restore, Delete permanently). Restore returns the file to its folder and is audited.

A retention link sits at the right of the toolbar: `Retention: Keep forever — Change`.

### 6.11 Admin: Activity

Filters: Deal, Person, Action, Date range. Rows 36px: absolute time in `meta`, actor avatar and name, then a sentence — *"Meera Shah uploaded 'SBI sanction letter.pdf' to Bank documents in Krishna Steel."* Read-only; no row actions. 50 rows per page.

This UI is first on the demo-day cut list (PRD §11), but the recording starts on day one regardless.

---

## 7. Microcopy

**Voice:** plain, specific, calm — a careful colleague. Second person, and name people: *"Samir needs to approve this."*

**Use:** Upload · Download · Rename · Request deletion · Approve · Reject · Pending approval · Awaiting approval · Deletion requested · Archive · Deal · Folder · Task · Assign · Reassign · Add user.

**Never use:** object · bucket · asset · entity · record · payload · presigned · sync · workflow · vault · ledger · immutable · checksum · audit trail · covenant · facility · escrow · custody · SEBI · OCI · S3 · Submit (as a bare button label) · Oops · Something went wrong · exclamation marks.

**Buttons** are a verb plus an object where ambiguous: `Upload files`, `Change stage`, `Approve selected`, `Request deletion`. Never `OK`.

**Errors** say what happened and what to do:
- *"This file is already in Bank documents as 'HDFC stmt Apr.pdf'."*
- *"You don't have access to this folder. Ask Samir."*
- *"File too large. Files must be under 2 GB."*
- *"Couldn't reach the server. Check your connection and try again."*

A mono reference code appears only on 5xx: `Reference: 7F3A-21`.

**Dates and numbers:** `15 Oct 2026`, `14:05`, `1.4 GB`, `23 files`. Indian digit grouping above 1,000 via `Intl.NumberFormat('en-IN')`. Store UTC, display IST (PRD §10).

**Names:** deals as entered; people by full name in tables, first name in sentences.

---

## 8. Accessibility

- WCAG 2.2 AA contrast. Every text token above clears 4.5:1 on its background except `--text-disabled`, which never carries required information. Primary buttons use `--brand-700` (5.5:1), never `--brand-600`.
- Focus is always visible: 2px `--brand-600` ring, 2px offset. Tab order follows visual order. Dialogs trap focus and return it to the trigger; Esc closes menus and dialogs.
- Status is never colour alone — every pill has a text label, and overdue carries the word `Overdue`.
- Real `<table>` semantics, `aria-sort` on sortable headers, checkboxes labelled `Select {name}`.
- Upload rows use `role="progressbar"` with `aria-valuenow`; completion is announced through a polite live region.
- Every icon-only button has an `aria-label`. Minimum target 24×24px; row `•••` buttons are 28×28.
- `lang="en-IN"`.

---

## 9. Responsive Behaviour

Desktop-first, targeting 1366×768 and 1440×900. Full experience at ≥1280px.

- **1024–1279px:** sidebar collapses to a 64px icon rail with tooltips. Task-detail rail narrows to 280px. Folder list narrows to 220px.
- **768–1023px:** the task rail moves above the description as a two-column grid. The folder list becomes a select above the file table. Tables hide Reporter, Start date and Created behind a `Columns` menu.
- **Below 768px:** read and download only, best effort. Nav moves to a top bar with a menu button. Upload, the permission matrix and bulk approvals show *"Use a laptop for this"* rather than a broken layout.

Never scroll the page body horizontally. Test at 1280, 1440 and 1920.
