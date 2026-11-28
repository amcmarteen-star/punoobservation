# Module 7, Step A: onboarding audit

Report only. Nothing is changed yet.

Marks: **K** keep · **C** change · **A** add · **R** remove.

## 1. Tour today (`partials/_tour.html`, version 2)

Today the tour has 5 branches, not 8 roles. The member, pending and
leader cases all use the "else" branch. Leader gets 1 extra step.
Most branches are longer than 6 steps.

### Shared steps (every role)

| Step | Mark | Note |
|---|---|---|
| Welcome | C | Merge into step 1 of each role tour |
| Dashboard: "Charts of the reforestation work…" | C | Wrong for members and officers. Say what their dashboard shows. Mention the clickable tiles |
| Help on every page (?) | K | |
| Notifications (bell) | C | Move into role steps where it matters (requests, reports) |
| My Account: "password and text size" | C | Also barangay and contact details (they prefill requests) |
| You're all set | R | Merge into the Help step |
| v2 "Set your barangay" (non-staff) | C | Keep for Individual and Pending only |

### Field Officer (now 4 role steps + 6 shared = 10)

| Step | Mark | Note |
|---|---|---|
| Monitoring Report | C | Add: photo preview shows the GPS check before you send |
| My Reports | K | |
| Site Visits | C | Add: "Not suitable" needs a reason and a suggested place |
| GIS Map | C | Mention the toolbar search |
| Dashboard tiles jump to "To do" | A | |

### CENRO Administrator (4 + 6 = 10)

| Step | Mark | Note |
|---|---|---|
| Review Requests | C | Groups: Needs your action, At organization (read-only), Finished |
| Review Reports | K | |
| Site Visits | K | |
| CENRO Overview | C | Shorten |
| Dashboard story, waiting chips, tiles | A | |
| Simulated / approximate labels | A | One step, on the dashboard map |

### Provincial Administrator (2 + 6 = 8)

| Step | Mark | Note |
|---|---|---|
| Provincial Overview | K | |
| Boundary Publications | K | |
| Dashboard story, Simulated tile | A | |

### System Administrator (3 + 6 = 9)

| Step | Mark | Note |
|---|---|---|
| User Management | C | Add: System role vs Partner organization columns; Users have no jurisdiction |
| Reference Dataset | K | |
| Audit Log | K | |

### "Else" branch: Individual / Pending / Member / Leader (3 + 6, leader 4 + 6)

| Step | Mark | Note |
|---|---|---|
| GIS Map | C | Add search; approximate markers |
| Species Recommendation | C | Place picker; no purpose filter claim |
| Request Reforestation Site | C | Split by role: Individual and Pending cannot request yet; members' requests go to the leader first; contact fields are prefilled |
| v2 My Organization (leader) | C | Split into: invite link · approve members · forward / return / reject |
| Pending: "waiting for your leader" | A | |
| Member: request timeline | A | |
| Dashboard tiles / map (org sites, your barangay ringed) | A | |

## 2. FAQ today (`partials/faq/`, 20 files)

| Page / entry | Mark | Note |
|---|---|---|
| **Dashboard** (admin charts only) | C | Shown to every role, but answers only admin charts. Add member, leader and officer sections |
| What does the dashboard show? | C | Story, waiting chips, tiles, at most 6 charts |
| Why only some municipalities? / load time / how up to date | K | |
| Delivery rate | C | Field counts only; tile is plain until counts exist |
| Survival / missing municipality ("Too few sites") | K | |
| Cost per hectare / Where to plant next / Most recommended | K | |
| "What do the dashboard numbers mean?" (tiles jump to their section) | A | |
| "What is simulated data?" | A | |
| **GIS map**: How do I find a site? | C | Add toolbar search (place picker and Site box) |
| Area and District | C | "None" is now "No borders" |
| Satellite / outlines / heat map | K | |
| Is a site's tree at its real location? | C | Hollow pin with "N sites" = barangay centre; solid = real position |
| "Why is a location approximate?" | A | |
| Monitoring History / boundaries / species | K | |
| How do I request a site from the map? | C | Request panel collapses, drags (desktop), remembers its place |
| **Requests**: request type / mark on map / size / estimate / documents | K | |
| "Why can't I request a site?" | A | Individual and Pending blocks, with what to do |
| Who reviews my request? | C | Members: your leader first, then CENRO |
| What do the statuses mean? | C | Missing Pending Org Approval, Returned, Pending CENRO |
| "What does Returned for revision mean?" | A | |
| Cancel / edit | C | Returned can be revised and resent |
| Contact fields prefilled from My Account | A | |
| **Review Requests**: which / status / notified / where / change / cancel | C | Groups; Pending CENRO; At organization is read-only |
| **Request detail** | K | Check "Why can't I change status" covers At organization |
| **Create site / Site visits** | K | |
| "What does Not suitable do?" | A | Closes the site, rejects the request, tells the requester the suggested place |
| **Reports**: photo entries | C | Add the preview and GPS check before sending |
| "Why was my photo marked No GPS?" | A | |
| My reports / report detail / review reports | K | |
| **Recommendations**: Purpose filter | C | No species are classified yet (0 category rows). Say it appears once species are tagged |
| "Why can't I find my barangay?" | C | Place picker search |
| Other recommendation entries | K | |
| **My Account** | C | Add Full name and Contact number, barangay. "Can I change my role?" → Users have no jurisdiction |
| **Notifications** | C | Add membership notices and org request actions |
| **Sites** | K | |
| **User Management**: roles | C | User, not Normal User (done). Add partner organization positions and "leaders are appointed by CENRO" |
| **Provincial overview / Publications / Reference / Audit** | K | |
| **No FAQ**: My Organization (members), Organizations list, Join page | A | "How do I invite members?", "I don't have an invite link", "My approval is taking long", approve/remove, forward/return/reject |

## 3. Messages to rewrite in Step B (say what to do next)

Not yet listed in full. I will collect every `flash(...)` and empty state
during Step B and report the changed ones. Known now:

- Request page blocks (Individual / Pending)
- "No requests…" / "No sites…" empty states
- Org join with a bad or old link
- Review Requests: "Nothing here."

## 4. Labels

- No "Normal User" left in visible text. Only code comments remain.
- "Individual", "Pending Member", "Partner Org Member" and "Partner Org Leader" come from `app/utils/roles.py`.
- The tour does not use these labels yet. Change it in Step B.
