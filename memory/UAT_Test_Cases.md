# View Dezider — Complete UAT Test Cases
### User Acceptance Testing Document
**Version:** 1.0 | **Date:** March 2026 | **App:** View Dezider (Multi-user Decision Making App)

---

## Table of Contents
1. [Authentication & User Management](#1-authentication--user-management)
2. [PRR Decision Framework (10-Step Flow)](#2-prr-decision-framework-10-step-flow)
3. [Test123 Instant Decisions](#3-test123-instant-decisions)
4. [Decision Journal](#4-decision-journal)
5. [Self-Assessment](#5-self-assessment)
6. [CLD (Causal Loop Diagram)](#6-cld-causal-loop-diagram)
7. [Simple Solution Finder](#7-simple-solution-finder)
8. [Advanced Solution Matrix](#8-advanced-solution-matrix)
9. [Factor Data Web Search (DuckDuckGo)](#9-factor-data-web-search)
10. [Collaboration (Shared Inbox, Notifications)](#10-collaboration)
11. [Expert Call (Jitsi Video)](#11-expert-call)
12. [Organization Management](#12-organization-management)
13. [WOWO Feature Flags (Admin)](#13-wowo-feature-flags)
14. [CTT — Centralized Task Tracker](#14-ctt--centralized-task-tracker)
15. [GEM — Goals Execution Manager](#15-gem--goals-execution-manager)
16. [TEPFI Resource Matrix](#16-tepfi-resource-matrix)
17. [Google Calendar Scheduling](#17-google-calendar-scheduling)
18. [Lifestyle Dezider (Routine Manager)](#18-lifestyle-dezider)
19. [Lifestyle Analyzer (PRR-based Assessment)](#19-lifestyle-analyzer)
20. [Dashboard & Navigation](#20-dashboard--navigation)
21. [Analytics](#21-analytics)
22. [Templates](#22-templates)
23. [Cross-Module Integration Flows](#23-cross-module-integration-flows)

---

## 1. Authentication & User Management

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 1.1 | Register new user | Go to Sign Up → Enter name, email, password, confirm password → Submit | Account created, redirected to dashboard |
| 1.2 | Register with existing email | Use same email as 1.1 | Error: "Email already registered" |
| 1.3 | Register with mismatched passwords | Enter different passwords | Error: Passwords do not match |
| 1.4 | Register with short password | Enter <6 char password | Error: Password too short |
| 1.5 | Login with valid credentials | Enter registered email + password → Sign In | Login successful, redirected to dashboard |
| 1.6 | Login with wrong password | Enter valid email + wrong password | Error: Invalid credentials |
| 1.7 | Login with non-existent email | Enter unregistered email | Error: User not found |
| 1.8 | View profile (GET /auth/me) | Navigate to Profile tab | Shows user name, email, role |
| 1.9 | Logout | Profile → Logout | Redirected to login screen, session cleared |
| 1.10 | Forgot password flow | Login → Forgot Password → Enter email → Submit | Confirmation message shown |
| 1.11 | Register with Organization ID | Sign Up → Enter org_id field | User gets `org_member` role in that org |
| 1.12 | Session persistence | Login → Close app → Reopen | User remains logged in |

---

## 2. PRR Decision Framework (10-Step Flow)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 2.1 | Create new PRR decision | Dashboard → Start PRR Decision → Enter title & context | Decision created, Step 1 shown |
| 2.2 | Step 1: Define Decision | Enter decision title, context, choose decision case | Saved, can proceed to Step 2 |
| 2.3 | Step 2: Identify Factors | Add factors (name, category: primary/secondary) | Factors listed, can add/remove |
| 2.4 | Step 2: Add sub-factors | Expand a factor → add sub-factor | Sub-factor appears nested under parent |
| 2.5 | Step 3: Classify Factors | Review factor classifications (Quantitative/Qualitative) | Factors grouped by classification |
| 2.6 | Step 4: Prioritize Factors | Drag/rate factors by importance (1-100) | Factors reordered by priority |
| 2.7 | Step 5: Identify Options | Add 2+ options for the decision | Options listed with names |
| 2.8 | Step 6: Factor Data & Sources | View factor data, click "Fetch Data" for web search | Data sources populated for each factor |
| 2.9 | Step 7: Rate Options | Rate each option against each factor | Ratings saved per option-factor pair |
| 2.10 | Step 8: CLD Analysis | Generate/view Causal Loop Diagram | CLD shows nodes and links |
| 2.11 | Step 9: Assessment | Choose assessment mode (LMH / Custom %) per factor | Assessment percentages calculated |
| 2.12 | Step 9: Final worth percentage | Complete all factor assessments | Option worth_percentage calculated |
| 2.13 | Step 10: Action Plan (MPPS) | Select preferred option → View MPPS action items | Action plan with improvements generated |
| 2.14 | Step 10: Export action plan | Click export/PDF | Action plan downloadable/viewable |
| 2.15 | Navigate between steps | Use Back/Next buttons through all 10 steps | Smooth navigation, data persists |
| 2.16 | Save and resume | Create decision → Leave → Come back later | Decision restored at last step |
| 2.17 | Delete decision | Decisions list → Delete | Decision removed from list |
| 2.18 | Clone decision | Decisions list → Clone | New copy created with all data |
| 2.19 | Decision with folder | Create decision in a folder | Appears in correct folder |
| 2.20 | Decision with life area | Set life area on decision | Life area tag shown on decision card |

---

## 3. Test123 Instant Decisions

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 3.1 | Create Test123 session | Dashboard → Test123 → Enter question | Session created |
| 3.2 | Add options | Enter 2+ option names | Options listed |
| 3.3 | Quick rate options | Rate each option 1-10 | Ratings saved |
| 3.4 | View result | Complete rating | Winner shown with scores |
| 3.5 | List Test123 sessions | View Test123 history | All sessions listed |
| 3.6 | Resume incomplete session | Open unfinished session | Resumes from last state |

---

## 4. Decision Journal

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 4.1 | Create journal entry | Profile → Journal → New Entry → Write | Entry saved with timestamp |
| 4.2 | View journal entries | Navigate to Journal list | All entries shown chronologically |
| 4.3 | Edit journal entry | Open entry → Edit → Save | Changes persisted |
| 4.4 | Delete journal entry | Open entry → Delete | Entry removed from list |
| 4.5 | Journal with decision link | Create entry linked to a decision | Link shown on entry |

---

## 5. Self-Assessment

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 5.1 | Take assessment | Navigate to Assessment → Answer questions | Questions presented one by one |
| 5.2 | Complete assessment | Answer all questions → Submit | Score/results calculated |
| 5.3 | View assessment history | Assessment → History | Past assessments listed with dates and scores |

---

## 6. CLD (Causal Loop Diagram)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 6.1 | Auto-generate CLD | In PRR Step 8 → Generate CLD | AI generates nodes and links from factors |
| 6.2 | View CLD diagram | Open CLD tab in decision | Visual diagram with nodes and connecting links |
| 6.3 | Edit mode: Add node | Toggle Edit → Add Node → Enter name | New node appears in diagram |
| 6.4 | Edit mode: Remove node | Select node → Delete | Node and its links removed |
| 6.5 | Edit mode: Add link | Select source → Select target → Confirm | New link drawn between nodes |
| 6.6 | Edit mode: Remove link | Select link → Delete | Link removed |
| 6.7 | Toggle link type | Tap link → Toggle Reinforcing/Balancing | Link type changes (R/B label, color) |
| 6.8 | View link list | Open link list panel | All links shown with source → target |

---

## 7. Simple Solution Finder

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 7.1 | Create Solution Finder | Tools → Solution Finder → New | Form opens with title, problem, SMART goal |
| 7.2 | Fill basic info | Enter title, problem statement, SMART goal | Saved, proceed to analysis |
| 7.3 | Add action items | Add solution action items with priorities | Items listed with priority tags |
| 7.4 | View Solution Finder list | Navigate to Solution Finder list | All entries shown |
| 7.5 | Edit Solution Finder | Open entry → Edit | Changes saved |
| 7.6 | Delete Solution Finder | Open entry → Delete | Entry removed |
| 7.7 | WOWO gating | Admin disables Solution Finder flag | Menu item hidden from non-admin users |

---

## 8. Advanced Solution Matrix

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 8.1 | Create Solution Matrix | Tools → Solution Matrix → New | Multi-step form opens |
| 8.2 | Define SMART goal | Enter area of life, SMART goal | Saved |
| 8.3 | Self layer analysis | Fill 7 sub-areas for Self layer | Data saved per sub-area |
| 8.4 | Micro layer analysis | Fill 7 sub-areas for Micro layer | Data saved |
| 8.5 | Macro layer analysis | Fill 7 sub-areas for Macro layer | Data saved |
| 8.6 | Add action items | Add action items with assignments | Items listed |
| 8.7 | View Solution Matrix list | Navigate to list | All matrices shown |
| 8.8 | Edit/delete Solution Matrix | Edit/delete operations | Changes/deletion persisted |
| 8.9 | WOWO gating | Admin disables Solution Matrix flag | Menu hidden |

---

## 9. Factor Data Web Search

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 9.1 | Fetch factor data | PRR Step 6 → Click "Fetch Data" on a factor | DuckDuckGo search results shown |
| 9.2 | View data sources | Expand factor data | URLs and snippets displayed |
| 9.3 | Search with specific query | Enter custom search query for factor | Relevant results returned |
| 9.4 | Handle no results | Search for obscure query | Graceful "no results" message |

---

## 10. Collaboration

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 10.1 | Share decision step | PRR → Share Step → Search user → Send | Step shared to recipient |
| 10.2 | View shared inbox | Dashboard → Shared Inbox | Received shared steps listed |
| 10.3 | View sent items | Shared Inbox → Sent tab | Sent shared steps listed |
| 10.4 | Contribute to shared step | Open shared step → Add contribution → Submit | Contribution saved |
| 10.5 | Merge contribution | Owner opens shared step → Merge contributions | Contributions merged into original decision |
| 10.6 | Notifications received | User B shares step with User A | User A gets notification |
| 10.7 | View notifications | Dashboard → Bell icon | Notification list shown |
| 10.8 | Mark notification read | Tap notification | Read status updated |
| 10.9 | Mark all read | Notifications → Mark All Read | All notifications marked as read |
| 10.10 | Delete notification | Swipe/delete notification | Notification removed |
| 10.11 | Unread count badge | Receive notifications | Badge count on bell icon updates |

---

## 11. Expert Call (Jitsi Video)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 11.1 | View expert list | Profile → Manage Experts | Expert list shown |
| 11.2 | Add expert | Add expert with name, specialization, contact | Expert saved |
| 11.3 | Edit expert | Edit expert details | Changes saved |
| 11.4 | Delete expert | Delete expert | Expert removed |
| 11.5 | Start call session | Open decision → Call Expert → Select expert | Jitsi room created, call URL generated |
| 11.6 | View call history | Profile → Call Sessions | Past call sessions listed |
| 11.7 | End call session | End ongoing call | Session marked as ended with duration |

---

## 12. Organization Management

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 12.1 | Create organization | Profile → Create Organization → Enter name, slug | Org created, creator gets `org_super_admin` |
| 12.2 | View org branding | Visit org settings | Logo URL, primary/accent colors shown |
| 12.3 | Update org branding | Change logo, colors → Save | Branding updated |
| 12.4 | View org members | Admin → Org Members | List of all members with roles |
| 12.5 | Promote member to org_admin | Super Admin → Select member → Promote to org_admin | Role updated |
| 12.6 | Promote member to org_co_admin | Super Admin → Promote to co_admin | Only org_super_admin can do this |
| 12.7 | Co-admin promotes to org_admin | Co-admin → Promote member | Success (co_admin can manage org_admin) |
| 12.8 | Co-admin tries to create co_admin | Co-admin → Promote to co_admin | Error: Only super_admin can create co_admin |
| 12.9 | Org_admin cannot modify higher role | Org_admin → Try to modify co_admin | Error: Cannot modify equal/higher role |
| 12.10 | Self-modification denied | Any admin → Try to change own role | Error: Cannot change your own role |
| 12.11 | Remove member from org | Admin → Remove member | Member's org_id and org_role cleared |
| 12.12 | Member registers with org_id | New user registers with org_id | Gets `org_member` role automatically |

---

## 13. WOWO Feature Flags

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 13.1 | View feature flags (admin) | Admin → Profile → Feature Flags | Toggle list for all features |
| 13.2 | Enable Solution Finder | Toggle ON → Save | Solution Finder visible to all org users |
| 13.3 | Disable Solution Matrix | Toggle OFF → Save | Solution Matrix hidden from non-admin |
| 13.4 | Non-admin sees only enabled | Login as regular user | Only enabled features visible |
| 13.5 | Public flags endpoint | Access /feature-flags/public | Returns flags without auth |

---

## 14. CTT — Centralized Task Tracker

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 14.1 | Navigate to CTT | Dashboard → Task Tracker card | CTT dashboard opens |
| 14.2 | Create task (one-time) | CTT → + button → Fill form → Create | Task created with all fields |
| 14.3 | All fields populated | Create task with: Task, Sub-Task, Priority, Status, Deadline, Task Owners, Life Area, Decision Type, Company, Division, Team, Project, Dependencies (ID/ED/IH/EH), Duration, From/To Time | All fields saved and displayed |
| 14.4 | Create routine task | Create task → Enable Routine toggle → Select frequency | Task marked as routine with frequency |
| 14.5 | Filter by status | Click status filter chip (Open/Active/Done/Blocked) | Only matching tasks shown |
| 14.6 | Filter by life area | Click life area filter (Career, Finance, etc.) | Filtered by area |
| 14.7 | Filter by routine/one-time | Toggle All Types / One-time / Routine | Correct tasks shown |
| 14.8 | Quick status change | On task card → Tap status button (Open/Active/Done/Blocked) | Status updated immediately |
| 14.9 | Day-wise status grid | Switch to Day Grid view → Tap day cell on a task | Status cycles: empty → done → in_progress → blocked → cancelled → empty |
| 14.10 | Board view | Switch to Board view | Tasks grouped by Life Area in columns |
| 14.11 | List view | Switch to List view | Tasks in card list format |
| 14.12 | Edit task | Tap task card → Modify fields → Update | Changes saved |
| 14.13 | Delete task | Tap trash icon → Confirm | Task deleted |
| 14.14 | Import from PRR/Solutions | CTT → Import button | Action items from Decisions (Step 10), Solution Finders, Solution Matrices pulled into CTT |
| 14.15 | Import deduplication | Click Import again | "No new items" message (already imported) |
| 14.16 | Stats dashboard | View CTT header + stats row | Shows Total, Open, Active, Done, Blocked counts |
| 14.17 | Google Calendar link | Task card → Calendar icon | Google Calendar URL opens with task details |
| 14.18 | Priority color coding | Create tasks with different priorities | Critical=Red, High=Yellow, Medium=Blue, Low=Gray |
| 14.19 | Source type badges | After importing, check task cards | Shows "PRR Decision" / "Solution Finder" / "Solution Matrix" badge |
| 14.20 | Navigate from Profile | Profile → Task Tracker (CTT) | Opens CTT dashboard |

---

## 15. GEM — Goals Execution Manager

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 15.1 | Navigate to GEM | Dashboard → Goals (GEM) | GEM dashboard opens |
| 15.2 | Create goal | GEM → + → Fill: Title, Description, Life Area, Goal Type (Problem/Need/Aspiration), Priority, Status, Target Date, SMART Goal, Progress % | Goal created |
| 15.3 | Goal type selection | Select Problem / Need / Aspiration | Color-coded selection saved |
| 15.4 | Life area selection | Select from 10 life areas | Area saved with icon |
| 15.5 | Progress tracking | Set progress slider to 50% | Progress bar shows 50% |
| 15.6 | Filter by life area | Click area filter | Only matching goals shown |
| 15.7 | Filter by goal type | Click type filter | Only matching types shown |
| 15.8 | Link goal to decision | Goal → Link → Select decision | Decision linked to goal |
| 15.9 | Link goal to solution finder | Goal → Link → Select finder | Finder linked |
| 15.10 | Link goal to solution matrix | Goal → Link → Select matrix | Matrix linked |
| 15.11 | Launch PRR from goal | Goal → Launch Action → Start Decision | New PRR decision created from goal context |
| 15.12 | Edit goal | Open goal → Edit fields → Update | Changes saved |
| 15.13 | Delete goal | Open goal → Delete | Goal removed |
| 15.14 | GEM Dashboard stats | View dashboard | Shows Problems/Needs/Aspirations count, Avg Progress |
| 15.15 | Navigate from Profile | Profile → Goals (GEM) | Opens GEM dashboard |

---

## 16. TEPFI Resource Matrix

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 16.1 | Navigate to TEPFI | Dashboard → TEPFI Matrix | TEPFI dashboard opens |
| 16.2 | View matrix overview | Dashboard → Matrix tab | 5×3 grid: Time/Effort/People/Finance/Infrastructure × Self/Micro/Macro with avg scores |
| 16.3 | Create TEPFI assessment | + → Enter title, life area | Form opens with 5 dimension accordions |
| 16.4 | Fill Time dimension | Expand Time → For each layer (Self/Micro/Macro): Set score (0-10 slider), description, notes | Scores saved, mini-score dots update |
| 16.5 | Fill Effort dimension | Expand Effort → Fill all 3 layers | Data saved |
| 16.6 | Fill People dimension | Expand People → Fill all 3 layers | Data saved |
| 16.7 | Fill Finance dimension | Expand Finance → Fill all 3 layers | Data saved |
| 16.8 | Fill Infrastructure dimension | Expand Infrastructure → Fill all 3 layers | Data saved |
| 16.9 | Score color coding | Set scores at various levels | 8-10=Green, 6-7=Blue, 4-5=Yellow, 2-3=Orange, 0-1=Red |
| 16.10 | View entries list | Switch to Entries tab | All assessments shown with mini-matrix and completion % |
| 16.11 | Filter by life area | Click area filter | Only matching entries shown |
| 16.12 | Edit TEPFI entry | Open entry → Edit → Save | Changes saved |
| 16.13 | Delete TEPFI entry | Delete entry | Entry removed |
| 16.14 | Import from Solution Matrix | TEPFI → Import from matrix | Maps Solution Matrix layers to TEPFI dimensions |
| 16.15 | Dashboard aggregate | Multiple entries → Check overview matrix | Shows averaged scores across all entries |
| 16.16 | Navigate from Profile | Profile → TEPFI Matrix | Opens TEPFI dashboard |

---

## 17. Google Calendar Scheduling

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 17.1 | Navigate to Calendar View | Dashboard → Calendar & Scheduling | Calendar timeline opens |
| 17.2 | View upcoming tasks | Calendar view with tasks that have deadlines | Tasks grouped by date in timeline |
| 17.3 | Time range filter | Click 7d / 14d / 30d / 60d / 90d | Timeline adjusts to show selected range |
| 17.4 | Single task calendar export | Click calendar icon on a task | Google Calendar opens with task title, priority, life area, dates |
| 17.5 | Batch export | Click "Export All" | Alert shows count of exportable tasks, opens first in Google Calendar |
| 17.6 | Date formatting | Export task with From/To time | Google Calendar event has correct start/end time |
| 17.7 | Export task with deadline only | Export task with only deadline (no from/to) | All-day event in Google Calendar |
| 17.8 | Empty calendar | No tasks with deadlines | "No Upcoming Deadlines" empty state |
| 17.9 | Today indicator | View timeline | Today's date highlighted in blue |
| 17.10 | Past date styling | View timeline with past dates | Past dates shown with reduced opacity |
| 17.11 | Navigate from Profile | Profile → Calendar & Scheduling | Opens calendar view |

---

## 18. Lifestyle Dezider (Routine Manager)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 18.1 | Navigate to Lifestyle | Dashboard → Lifestyle Dezider | Lifestyle dashboard opens |
| 18.2 | Create routine (daily) | + → Name: "Morning Meditation", Frequency: Daily, Life Area: Spirituality, Priority: High, Category: Primary | Routine created |
| 18.3 | Create routine (weekly) | + → Name: "Exercise Review", Frequency: Weekly | Routine created |
| 18.4 | Create routine (monthly) | + → Name: "Budget Review", Frequency: Monthly | Routine created |
| 18.5 | Create routine (hourly) | + → Name: "Water Intake", Frequency: Hourly | Routine created |
| 18.6 | Create routine (fortnightly) | + → Name: "Bi-weekly Review", Frequency: Fortnightly | Routine created |
| 18.7 | All routine fields | Fill: Name, Description, Life Area, Frequency, Time Slot, Priority, Category, Expected Value, Unit | All fields saved |
| 18.8 | Factor category selection | Select Primary Factor / Secondary Factor | Category saved (used in PRR assessment) |
| 18.9 | Edit routine | Open routine → Edit → Save | Changes saved |
| 18.10 | Delete routine | Routine card → Trash → Confirm | Routine deleted |
| 18.11 | Deactivate routine | Edit → Toggle Active OFF | Routine marked inactive, excluded from assessments |
| 18.12 | Filter by frequency | Click frequency filter chips | Only matching routines shown |
| 18.13 | Import from CTT | Header → Import | CTT routine tasks imported with deduplication |
| 18.14 | Import deduplication | Click Import again | "No new routines" message |
| 18.15 | View assessments tab | Switch to Assessments tab | Past lifestyle assessments listed |
| 18.16 | Dashboard stats | View frequency breakdown | Shows count per frequency type |
| 18.17 | Effectiveness card | View latest effectiveness score | Score + color + label (Excellent/Good/Fair/Needs Attention) |
| 18.18 | Sparkline trend | Multiple assessments done | Mini bar chart shows recent scores |
| 18.19 | Navigate from Profile | Profile → Lifestyle Dezider | Opens lifestyle dashboard |

---

## 19. Lifestyle Analyzer (PRR-based Assessment)

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 19.1 | Start Daily assessment | Lifestyle → Daily button | PRR decision created with daily+hourly routines as factors, single option "My Lifestyle" |
| 19.2 | Start Weekly assessment | Lifestyle → Weekly button | Includes daily+weekly+hourly routines as factors |
| 19.3 | Start Monthly assessment | Lifestyle → Monthly button | Includes ALL routines as factors |
| 19.4 | Verify factors are routines | Open created PRR decision → Step 2 | Factors match active routine names |
| 19.5 | Verify single option | Open PRR decision → Step 5 | Only one option: "My Lifestyle" |
| 19.6 | Complete full PRR flow | Go through all 10 PRR steps for the lifestyle decision | Classification → Prioritization → Rating → Assessment (LMH/Custom%) → Final % |
| 19.7 | Assessment with LMH mode | Step 9 → Select Low/Medium/High for each factor | Percentage calculated per LMH selection |
| 19.8 | Assessment with Custom % | Step 9 → Enter custom percentage per factor | Custom % applied |
| 19.9 | Final effectiveness score | Complete assessment → View option worth_percentage | Score = Lifestyle effectiveness % |
| 19.10 | View assessment history | Lifestyle → Assessments tab | All lifestyle PRR decisions listed with scores |
| 19.11 | Assessment completion status | View assessment card | Shows "Complete" / "In Progress" + factor completion count |
| 19.12 | Navigate to analytics | Lifestyle → Analytics button (bar chart icon) | Opens analytics screen |
| 19.13 | Analytics: average effectiveness | View analytics overview | Average score across all completed assessments |
| 19.14 | Analytics: trend chart | View trend section | Bar chart showing scores over time |
| 19.15 | Analytics: streak tracking | Multiple consecutive 60%+ assessments | Streak count displayed |
| 19.16 | Analytics: area breakdown | View area breakdown | Per-life-area progress bars with percentages |
| 19.17 | Analytics: period filter | Toggle Daily/Weekly/Monthly/All | Analytics filtered by period |
| 19.18 | Error: no routines | Delete all routines → Start assessment | Error: "No active routines found" |
| 19.19 | Resume assessment | Start assessment → Leave → Come back | PRR decision preserved, can continue |

---

## 20. Dashboard & Navigation

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 20.1 | Home dashboard loads | Login → Dashboard tab | Shows all sections: Quick Actions, Solution Tools, Task Tracker, Management Tools, Calendar, Lifestyle |
| 20.2 | CTT card with live stats | Dashboard → CTT card | Shows Total/Active/Done/Blocked/Routines counts |
| 20.3 | GEM card | Dashboard → Goals (GEM) card | Navigates to GEM |
| 20.4 | TEPFI card | Dashboard → TEPFI Matrix card | Navigates to TEPFI |
| 20.5 | Calendar card | Dashboard → Calendar & Scheduling card | Navigates to Calendar View |
| 20.6 | Lifestyle card | Dashboard → Lifestyle Dezider card | Navigates to Lifestyle |
| 20.7 | PRR Quick Action | Dashboard → Start PRR Decision | Opens new PRR flow |
| 20.8 | Test123 Quick Action | Dashboard → Test123 | Opens instant decision |
| 20.9 | Profile tab navigation | Bottom tab → Profile | Shows profile with all tool links |
| 20.10 | All Profile tool links | Profile → Each tool link | All navigate correctly: CTT, GEM, TEPFI, Calendar, Lifestyle, Org Members, Experts, etc. |
| 20.11 | Back button navigation | Open any tool → Press back | Returns to previous screen |
| 20.12 | Pull-to-refresh | Pull down on any list screen | Data refreshes |

---

## 21. Analytics

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 21.1 | View folder analytics | Dashboard → Analytics | Folder-level analytics shown |
| 21.2 | Decision analytics | Open specific folder analytics | Decision count, completion rates |
| 21.3 | Stats overview | Dashboard → View stats | Total decisions, completed, journal entries |

---

## 22. Templates

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 22.1 | Save decision as template | Decision → Save as Template | Template created |
| 22.2 | View templates | Templates list | All saved templates shown |
| 22.3 | Use template | Select template → Use | New decision created from template |
| 22.4 | Admin approve template | Admin → Approve template | Template visible to all users |
| 22.5 | Import template | Import shared template | Template added to user's collection |
| 22.6 | Decision templates list | View pre-built templates | System templates available |

---

## 23. Cross-Module Integration Flows

| # | Test Case | Steps | Expected Result |
|---|-----------|-------|-----------------|
| 23.1 | PRR → CTT flow | Complete PRR (Step 10 actions) → CTT → Import | PRR action items appear in CTT with source_type="decision" |
| 23.2 | Solution Finder → CTT flow | Create Solution Finder with actions → CTT → Import | Actions appear with source_type="solution_finder" |
| 23.3 | Solution Matrix → CTT flow | Create Solution Matrix with actions → CTT → Import | Actions appear with source_type="solution_matrix" |
| 23.4 | CTT → Lifestyle flow | Create routine tasks in CTT → Lifestyle → Import from CTT | CTT routines appear as Lifestyle routines |
| 23.5 | Lifestyle → PRR flow | Create routines → Start Lifestyle Assessment → Complete PRR | Routines become PRR factors, assessment produces effectiveness % |
| 23.6 | GEM → PRR flow | Create goal → Launch Decision from goal | PRR decision created with goal context |
| 23.7 | Solution Matrix → TEPFI flow | Create Solution Matrix → TEPFI → Import from Matrix | TEPFI entry created with mapped Self/Micro/Macro data |
| 23.8 | CTT → Calendar flow | Create tasks with deadlines → Calendar View | Tasks appear in timeline grouped by date |
| 23.9 | CTT → Google Calendar | Task with deadline → Calendar icon | Google Calendar event created with task details |
| 23.10 | Full lifecycle | Create GEM Goal → Launch PRR Decision → Complete with actions → Import to CTT → Mark routines → Import to Lifestyle → Run Assessment | End-to-end flow across all modules |

---

## Effectiveness Color Legend (Used Across App)

| Score Range | Color | Label |
|-------------|-------|-------|
| 80%+ | 🟢 Green | Excellent |
| 60-79% | 🔵 Blue | Good |
| 40-59% | 🟡 Yellow | Fair |
| <40% | 🔴 Red | Needs Attention |

---

## Priority Color Legend

| Priority | Color |
|----------|-------|
| Critical | 🔴 Red (#EF4444) |
| High | 🟡 Amber (#F59E0B) |
| Medium | 🔵 Blue (#3B82F6) |
| Low | ⚪ Gray (#6B7280) |

---

**Total Test Cases: 178**

*Document generated for View Dezider UAT — covering all 23 modules across Authentication, PRR Framework, Tools, Collaboration, Organization, Task Tracking, Goal Management, Resource Matrix, Calendar, and Lifestyle Management.*
