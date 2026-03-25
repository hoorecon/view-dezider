# View Dezider — Detailed UAT Test Cases
### User Acceptance Testing Document (Detailed Edition)
**Version:** 2.0 | **Date:** March 2026 | **App:** View Dezider (Multi-user Decision Making App)
**Platform:** Mobile (iOS/Android via Expo Go) + Web Preview

---

## Table of Contents
1. Authentication & User Management (12 cases)
2. PRR Decision Framework — 10-Step Flow (20 cases)
3. Test123 Instant Decisions (6 cases)
4. Decision Journal (5 cases)
5. Self-Assessment (3 cases)
6. CLD — Causal Loop Diagram (8 cases)
7. Simple Solution Finder (7 cases)
8. Advanced Solution Matrix (9 cases)
9. Factor Data Web Search — DuckDuckGo (4 cases)
10. Collaboration — Shared Inbox & Notifications (11 cases)
11. Expert Call — Jitsi Video (7 cases)
12. Organization Management (12 cases)
13. WOWO Feature Flags — Admin (5 cases)
14. CTT — Centralized Task Tracker (20 cases)
15. GEM — Goals Execution Manager (15 cases)
16. TEPFI Resource Matrix (16 cases)
17. Google Calendar Scheduling (11 cases)
18. Lifestyle Dezider — Routine Manager (19 cases)
19. Lifestyle Analyzer — PRR-based Assessment (19 cases)
20. Dashboard & Navigation (12 cases)
21. Analytics (3 cases)
22. Templates (6 cases)
23. Cross-Module Integration Flows (10 cases)

**Total: 178 Test Cases**

---

## MODULE 1: AUTHENTICATION & USER MANAGEMENT

### TC-1.1: Register New User
**Navigation:** App Launch → Login Screen → Tap "Sign Up" link at bottom
**Steps:**
1. App opens to Login screen with email and password fields
2. Tap "Sign Up" text at the bottom of the screen
3. Screen transitions to Registration form showing: Full Name, Email, Password, Confirm Password fields
4. Enter Full Name: "John Doe"
5. Enter Email: "john.doe@example.com"
6. Enter Password: "SecurePass123"
7. Enter Confirm Password: "SecurePass123"
8. Tap "Create Account" button
**Expected:**
- Loading indicator shows briefly
- User is automatically logged in
- Screen redirects to Home Dashboard
- Dashboard shows "Welcome" greeting with user's name
- Bottom tab bar visible with Home and Profile tabs

### TC-1.2: Register with Existing Email
**Navigation:** Logout → Login Screen → Tap "Sign Up"
**Steps:**
1. Enter Full Name: "Jane Doe"
2. Enter Email: "john.doe@example.com" (same email as TC-1.1)
3. Enter Password: "AnotherPass123"
4. Enter Confirm Password: "AnotherPass123"
5. Tap "Create Account"
**Expected:**
- Error alert/message appears: "Email already registered" or similar
- User stays on registration screen
- Form fields remain filled (password may clear)

### TC-1.3: Register with Mismatched Passwords
**Navigation:** Login Screen → Tap "Sign Up"
**Steps:**
1. Enter Full Name: "Test User"
2. Enter Email: "test.mismatch@example.com"
3. Enter Password: "Password123"
4. Enter Confirm Password: "DifferentPass456"
5. Tap "Create Account"
**Expected:**
- Error message: "Passwords do not match"
- User stays on registration screen
- No account created

### TC-1.4: Register with Short Password
**Navigation:** Login Screen → Tap "Sign Up"
**Steps:**
1. Enter Full Name: "Short Pass User"
2. Enter Email: "short.pass@example.com"
3. Enter Password: "abc"
4. Enter Confirm Password: "abc"
5. Tap "Create Account"
**Expected:**
- Error message about password length requirement
- User stays on registration screen

### TC-1.5: Login with Valid Credentials
**Navigation:** App Launch → Login Screen
**Steps:**
1. Login screen shows Email and Password fields with "Sign In" button
2. Enter Email: "john.doe@example.com"
3. Enter Password: "SecurePass123"
4. Tap "Sign In" button
**Expected:**
- Loading indicator shows briefly
- User logged in successfully
- Redirected to Home Dashboard
- Dashboard loads with user's data (stats, quick actions)
- Bottom tab bar shows Home and Profile tabs

### TC-1.6: Login with Wrong Password
**Navigation:** App Launch → Login Screen
**Steps:**
1. Enter Email: "john.doe@example.com" (valid email)
2. Enter Password: "WrongPassword999"
3. Tap "Sign In"
**Expected:**
- Error alert: "Invalid credentials" or "Incorrect password"
- User stays on login screen
- Password field clears

### TC-1.7: Login with Non-existent Email
**Navigation:** App Launch → Login Screen
**Steps:**
1. Enter Email: "nonexistent.user@example.com"
2. Enter Password: "AnyPassword123"
3. Tap "Sign In"
**Expected:**
- Error alert: "User not found" or "Invalid credentials"
- User stays on login screen

### TC-1.8: View Profile
**Navigation:** Login → Home Dashboard → Tap "Profile" tab (bottom right)
**Steps:**
1. Successfully login
2. Tap the Profile tab icon in the bottom navigation bar
3. Profile screen loads
**Expected:**
- User's full name displayed at top
- User's email shown
- User's role shown (e.g., "user", "admin")
- Organization info shown if applicable
- Tool navigation links visible (CTT, GEM, TEPFI, Calendar, Lifestyle)
- Logout button at the bottom

### TC-1.9: Logout
**Navigation:** Home → Profile tab → Scroll to bottom
**Steps:**
1. Navigate to Profile tab
2. Scroll down to the bottom of the profile screen
3. Tap "Logout" button (red text with logout icon)
4. Confirm logout if prompted
**Expected:**
- User session cleared
- App navigates back to Login screen
- Previous session data not accessible
- Trying to access any authenticated screen redirects to login

### TC-1.10: Forgot Password Flow
**Navigation:** App Launch → Login Screen → Tap "Forgot Password"
**Steps:**
1. On login screen, tap "Forgot Password?" link
2. Enter registered email address
3. Tap "Reset Password" or "Send Reset Link"
**Expected:**
- Confirmation message: "Password reset instructions sent"
- User can navigate back to login screen

### TC-1.11: Register with Organization ID
**Navigation:** Login Screen → Tap "Sign Up"
**Steps:**
1. Fill all registration fields (Name, Email, Password, Confirm)
2. Enter Organization ID in the org_id field (must be a valid existing org ID)
3. Tap "Create Account"
**Expected:**
- Account created successfully
- User automatically assigned `org_member` role within that organization
- Profile tab shows organization affiliation
- User can see org-specific features

### TC-1.12: Session Persistence
**Navigation:** Login → Close App → Reopen App
**Steps:**
1. Successfully login with valid credentials
2. Close the app completely (not just background)
3. Wait 30 seconds
4. Reopen the app
**Expected:**
- App opens directly to Home Dashboard (not login screen)
- User remains authenticated
- All data accessible without re-login
- Token/session still valid

---

## MODULE 2: PRR DECISION FRAMEWORK (10-Step Flow)

### TC-2.1: Create New PRR Decision
**Navigation:** Home Dashboard → Tap "Start PRR Decision" card (blue card with compass icon)
**Steps:**
1. From Home Dashboard, locate the "Start PRR Decision" action card
2. Tap on it
3. New decision creation screen appears
4. Enter Decision Title: "Should I change my career?"
5. Enter Context: "Considering a career shift to product management"
6. Tap "Create" or "Next"
**Expected:**
- Decision created successfully
- Screen transitions to Step 1 of the PRR flow
- Step indicator shows "Step 1 of 10"
- Title and context are saved

### TC-2.2: Step 1 — Define Decision
**Navigation:** Continuing from TC-2.1 or open existing decision → Step 1
**Steps:**
1. Step 1 screen shows decision title and context fields
2. Optionally select Decision Case (e.g., Problem, Need, Aspiration)
3. Optionally assign a Life Area (Career, Finance, etc.)
4. Optionally assign to a Folder
5. Review entered information
6. Tap "Next" to proceed to Step 2
**Expected:**
- All fields editable and save on input
- Decision case selector shows options with icons
- Life area selection shows 10 areas with icons
- "Next" button enabled at bottom
- Navigates to Step 2

### TC-2.3: Step 2 — Identify Factors
**Navigation:** PRR Flow → Step 2 (Factors)
**Steps:**
1. Step 2 shows "Identify Factors" heading
2. Tap "Add Factor" button
3. Enter factor name: "Salary expectations"
4. Select category: "Primary" (Quantitative)
5. Tap "Add" to confirm
6. Repeat to add: "Work-life balance" (Primary), "Growth opportunities" (Secondary)
7. Verify all 3 factors listed
**Expected:**
- Each factor appears as a card with name, category badge
- Primary factors distinguished from Secondary
- Factors can be reordered
- Delete button (trash icon) on each factor
- Factor count shown
- "Next" button enabled

### TC-2.4: Step 2 — Add Sub-factors
**Navigation:** PRR Flow → Step 2 → Expand a factor
**Steps:**
1. On Step 2, tap on "Salary expectations" factor to expand it
2. Tap "Add Sub-factor"
3. Enter sub-factor name: "Base salary"
4. Add another sub-factor: "Bonus structure"
5. Set weight percentage for each sub-factor (e.g., 70%, 30%)
**Expected:**
- Sub-factors appear nested/indented under parent factor
- Weight percentages shown
- Sub-factors can be deleted independently
- Parent factor shows sub-factor count

### TC-2.5: Step 3 — Classify Factors
**Navigation:** PRR Flow → Step 3 (Classify)
**Steps:**
1. Navigate to Step 3
2. Review automatic classification of factors as Quantitative or Qualitative
3. Optionally change classification for any factor
4. Verify grouping
**Expected:**
- Factors grouped by Quantitative and Qualitative categories
- Each factor shows its classification badge
- User can toggle classification per factor
- Visual distinction between groups (colors/sections)

### TC-2.6: Step 4 — Prioritize Factors
**Navigation:** PRR Flow → Step 4 (Prioritize)
**Steps:**
1. Navigate to Step 4
2. Each factor shows a priority rating input (1-100)
3. Set "Salary expectations" priority to 85
4. Set "Work-life balance" priority to 90
5. Set "Growth opportunities" priority to 70
6. Observe factors reorder based on priority
**Expected:**
- Factors sorted by priority (highest first)
- Priority values saved and displayed
- Visual indicator of relative importance (bar/percentage)
- Total adds context to weighting

### TC-2.7: Step 5 — Identify Options
**Navigation:** PRR Flow → Step 5 (Options)
**Steps:**
1. Navigate to Step 5
2. Tap "Add Option"
3. Enter option name: "Stay in current role"
4. Tap "Add Option" again
5. Enter option name: "Switch to Product Management"
6. Optionally add: "Freelance consulting"
**Expected:**
- All options listed with names
- Minimum 2 options required to proceed (for standard decisions)
- Options can be edited and deleted
- Each option shows an edit/delete icon
- "Next" button enabled

### TC-2.8: Step 6 — Factor Data & Sources
**Navigation:** PRR Flow → Step 6 (Data)
**Steps:**
1. Navigate to Step 6
2. Each factor shown with a "Fetch Data" button
3. Tap "Fetch Data" on "Salary expectations"
4. Wait for DuckDuckGo search to complete
5. View returned data sources (URLs, snippets)
6. Optionally enter custom data for any factor
**Expected:**
- Loading spinner while fetching data
- Search results appear below the factor with titles, URLs, snippets
- Multiple data sources returned per factor
- Custom data entry field available
- Data persists when navigating away and back

### TC-2.9: Step 7 — Rate Options
**Navigation:** PRR Flow → Step 7 (Ratings)
**Steps:**
1. Navigate to Step 7
2. Matrix view shows: Rows = Factors, Columns = Options
3. For factor "Salary expectations" × Option "Stay in current role": Enter rating (e.g., 7/10)
4. For factor "Salary expectations" × Option "Switch to PM": Enter rating (e.g., 8/10)
5. Complete all factor-option rating combinations
**Expected:**
- Rating grid/matrix fully interactive
- Each cell accepts numeric rating input
- Ratings saved immediately on change
- Visual feedback (color coding based on rating value)
- All combinations must be rated before proceeding

### TC-2.10: Step 8 — CLD Analysis
**Navigation:** PRR Flow → Step 8 (CLD)
**Steps:**
1. Navigate to Step 8
2. Tap "Generate CLD" button
3. Wait for AI to analyze factors and generate Causal Loop Diagram
4. View generated diagram with nodes (factors) and links (relationships)
**Expected:**
- Loading indicator during AI generation
- Diagram renders with circular/network layout
- Nodes represent factors with labels
- Links show relationships between factors
- Links labeled as Reinforcing (R) or Balancing (B)
- Edit mode toggle visible
- Diagram is interactive (tap nodes/links)

### TC-2.11: Step 9 — Assessment (LMH & Custom %)
**Navigation:** PRR Flow → Step 9 (Assessment)
**Steps:**
1. Navigate to Step 9
2. For each factor, select assessment mode:
   - Option A: LMH (Low/Medium/High) → Maps to predefined percentages
   - Option B: Custom % → Enter exact percentage
3. For "Salary expectations": Select "High" (maps to ~80%)
4. For "Work-life balance": Select "Medium" (maps to ~50%)
5. For "Growth opportunities": Enter Custom 75%
**Expected:**
- Each factor row shows LMH toggle buttons + Custom % input
- LMH buttons are color-coded (Low=Red, Medium=Yellow, High=Green)
- Selecting LMH auto-fills percentage
- Custom % overrides LMH selection
- Running calculation updates in real-time

### TC-2.12: Step 9 — Final Worth Percentage
**Navigation:** PRR Flow → Step 9 → Complete all assessments
**Steps:**
1. Complete assessment for ALL factors across ALL options
2. View the summary at bottom of Step 9
3. Each option shows its calculated "Worth Percentage"
**Expected:**
- Worth percentage calculated using: Factor Priority × Assessment % × Weight
- Higher percentage = better option for that assessment
- Clear visual comparison between options
- Percentage shown with 1 decimal precision (e.g., 72.5%)
- Best option highlighted or marked

### TC-2.13: Step 10 — Action Plan (MPPS)
**Navigation:** PRR Flow → Step 10 (MPPS Action Plan)
**Steps:**
1. Navigate to Step 10
2. Select preferred/chosen option (e.g., "Switch to Product Management")
3. View MPPS (Most Preferred Possible Solution) action items
4. View improvement suggestions
5. View projected worth percentage
6. Set timeframe for implementation
**Expected:**
- Chosen option highlighted
- Action items listed with priorities
- Improvement areas identified (factors where rating was low)
- Projected worth shown after improvements
- Timeframe selector available
- Action items exportable to CTT

### TC-2.14: Step 10 — Export Action Plan
**Navigation:** PRR Flow → Step 10 → Tap export/PDF button
**Steps:**
1. On Step 10, locate the export/download button
2. Tap to generate action plan document
**Expected:**
- PDF or document generated with:
  - Decision title and context
  - Chosen option
  - All action items with priorities
  - Factor ratings summary
  - Worth percentages
- Document viewable/downloadable

### TC-2.15: Navigate Between Steps
**Navigation:** PRR Flow → Use Back/Next buttons
**Steps:**
1. Start at Step 1
2. Tap "Next" to go to Step 2
3. Tap "Next" through Steps 3, 4, 5
4. Tap "Back" to return to Step 4
5. Tap "Back" to Step 3
6. Tap "Next" all the way to Step 10
**Expected:**
- Smooth transitions between all steps
- Data persists across forward/backward navigation
- Step indicator updates correctly (e.g., "Step 4 of 10")
- No data loss when going back and forth
- All previously entered data intact

### TC-2.16: Save and Resume Decision
**Navigation:** Create decision → Leave midway → Return later
**Steps:**
1. Create a new decision and complete Steps 1-5
2. Tap Back arrow to leave the PRR flow
3. Navigate to Home Dashboard
4. Find the decision in the decisions list (PRR tab)
5. Tap to open it
**Expected:**
- Decision appears in the list with title and status "in_progress"
- Opening it resumes at the last completed step (or Step 1 with all data)
- All previously entered data (title, factors, options) preserved
- Can continue from where left off

### TC-2.17: Delete Decision
**Navigation:** PRR tab → Decisions list → Long press or tap delete
**Steps:**
1. Navigate to PRR tab with decisions list
2. Find the decision to delete
3. Tap delete/trash icon on the decision card
4. Confirm deletion in the alert dialog
**Expected:**
- Confirmation dialog: "Are you sure you want to delete this decision?"
- After confirming, decision removed from list
- Decision no longer appears in any search or filter
- Cannot be recovered

### TC-2.18: Clone Decision
**Navigation:** PRR tab → Decisions list → Clone option
**Steps:**
1. Navigate to decisions list
2. Find decision to clone
3. Tap clone/duplicate button
4. Confirm cloning
**Expected:**
- New decision created with "(Clone)" appended to title
- All data copied: factors, options, ratings, assessments
- New decision ID generated
- Original decision unchanged
- Clone appears in the list

### TC-2.19: Decision with Folder
**Navigation:** Create decision → Assign folder
**Steps:**
1. Create a new PRR decision
2. In Step 1, select or create a folder (e.g., "Career Decisions")
3. Save and proceed
4. Go back to decisions list
**Expected:**
- Decision tagged with folder name
- Filter by folder shows only decisions in that folder
- Folder analytics reflect this decision

### TC-2.20: Decision with Life Area
**Navigation:** Create decision → Step 1 → Select Life Area
**Steps:**
1. Create a new PRR decision
2. In Step 1, tap Life Area selector
3. Choose "Career" from the 10 life areas
4. Save
**Expected:**
- Life area tag shown on decision card (Career icon + label)
- Decision filterable by life area
- Analytics group by life area includes this decision

---

## MODULE 3: TEST123 INSTANT DECISIONS

### TC-3.1: Create Test123 Session
**Navigation:** Home Dashboard → Tap "Test123" quick action card
**Steps:**
1. From Home Dashboard, tap the "Test123" card (quick decision icon)
2. Test123 screen opens
3. Enter question: "Which restaurant for dinner?"
**Expected:**
- New Test123 session created
- Question field accepts text input
- Session ID generated

### TC-3.2: Add Options
**Navigation:** Continuing from TC-3.1
**Steps:**
1. Tap "Add Option"
2. Enter: "Italian Restaurant"
3. Tap "Add Option"
4. Enter: "Japanese Restaurant"
5. Tap "Add Option"
6. Enter: "Mexican Restaurant"
**Expected:**
- All 3 options listed
- Each option editable
- Option can be removed

### TC-3.3: Quick Rate Options
**Navigation:** Continuing from TC-3.2
**Steps:**
1. For "Italian Restaurant": Set rating to 7
2. For "Japanese Restaurant": Set rating to 9
3. For "Mexican Restaurant": Set rating to 6
**Expected:**
- Rating inputs accept 1-10 values
- Ratings saved per option
- Visual feedback on rating (e.g., color intensity)

### TC-3.4: View Result
**Navigation:** Continuing from TC-3.3
**Steps:**
1. After all options rated, view the result section
2. Winner displayed prominently
**Expected:**
- "Japanese Restaurant" shown as winner (highest score: 9)
- All options ranked by score
- Visual distinction for winner (gold/highlighted)
- Scores shown next to each option

### TC-3.5: List Test123 Sessions
**Navigation:** Test123 → View history
**Steps:**
1. Navigate to Test123 section
2. View list of past sessions
**Expected:**
- All previous Test123 sessions listed chronologically (newest first)
- Each shows question and winner
- Tap to open full details

### TC-3.6: Resume Incomplete Session
**Navigation:** Test123 → History → Tap incomplete session
**Steps:**
1. Create a new Test123 session, add options but DON'T rate
2. Leave the screen
3. Return to Test123 history
4. Tap the incomplete session
**Expected:**
- Session opens with previously entered question and options
- Ratings can be entered/completed
- Session status shows "incomplete" or "in progress"

---

## MODULE 4: DECISION JOURNAL

### TC-4.1: Create Journal Entry
**Navigation:** Profile Tab → Journal section → Tap "New Entry"
**Steps:**
1. Navigate to Profile tab
2. Find Journal section or navigate to Journal screen
3. Tap "New Entry" or "+" button
4. Enter journal content: "Today I reflected on my career decision..."
5. Tap "Save"
**Expected:**
- Entry saved with current timestamp
- Entry appears at top of journal list
- Content fully preserved

### TC-4.2: View Journal Entries
**Navigation:** Profile → Journal
**Steps:**
1. Navigate to Journal screen
2. Scroll through entries
**Expected:**
- All entries listed in reverse chronological order (newest first)
- Each entry shows: preview of content, date, time
- Pull-to-refresh works

### TC-4.3: Edit Journal Entry
**Navigation:** Journal → Tap entry → Edit
**Steps:**
1. Open an existing journal entry
2. Tap Edit button
3. Modify the content
4. Tap "Save"
**Expected:**
- Content editable in text field
- Changes saved successfully
- Updated timestamp or "edited" indicator shown

### TC-4.4: Delete Journal Entry
**Navigation:** Journal → Tap entry → Delete
**Steps:**
1. Open a journal entry
2. Tap Delete button
3. Confirm deletion
**Expected:**
- Confirmation dialog appears
- After confirming, entry removed from list
- List refreshes

### TC-4.5: Journal with Decision Link
**Navigation:** Journal → New Entry → Link Decision
**Steps:**
1. Create a new journal entry
2. Link it to an existing PRR decision
3. Save
**Expected:**
- Decision link shown on journal entry
- Tapping the link navigates to the decision
- Journal entry appears in decision context

---

## MODULE 5: SELF-ASSESSMENT

### TC-5.1: Take Assessment
**Navigation:** Dashboard or Profile → Assessment → Start
**Steps:**
1. Navigate to Assessment section
2. Tap "Start Assessment"
3. First question appears
**Expected:**
- Assessment questions presented one at a time
- Multiple choice or rating scale for each
- Progress indicator (e.g., "Question 3 of 10")

### TC-5.2: Complete Assessment
**Navigation:** Continuing from TC-5.1
**Steps:**
1. Answer all assessment questions
2. Submit the assessment
**Expected:**
- Results/score calculated and displayed
- Score breakdown by category (if applicable)
- Results saved to history
- Visual representation of score (chart/bar)

### TC-5.3: View Assessment History
**Navigation:** Assessment → History
**Steps:**
1. Navigate to Assessment History
2. View past assessments
**Expected:**
- All past assessments listed with dates and scores
- Tapping an entry shows full results
- Trend visible if multiple assessments taken

---

## MODULE 6: CLD — CAUSAL LOOP DIAGRAM

### TC-6.1: Auto-generate CLD
**Navigation:** PRR Flow → Step 8 → Tap "Generate CLD"
**Steps:**
1. Open a decision with factors defined (Steps 1-7 complete)
2. Navigate to Step 8 (CLD)
3. Tap "Generate CLD" button
4. Wait for AI processing
**Expected:**
- Loading indicator during generation (may take a few seconds)
- Diagram rendered with:
  - Nodes = factors (displayed as labeled circles/boxes)
  - Links = relationships between factors (arrows)
  - Link types: Reinforcing (R) / Balancing (B) labeled on links
- Diagram is scrollable/zoomable

### TC-6.2: View CLD Diagram
**Navigation:** PRR Flow → Step 8 → View tab
**Steps:**
1. After CLD generated, view the diagram
2. Observe node positions, link directions, labels
**Expected:**
- Clean visual layout with no overlapping labels
- Nodes colored or styled distinctly
- Link arrows show direction of causality
- R/B labels visible on links
- Diagram fits screen with scroll/zoom capability

### TC-6.3: Edit Mode — Add Node
**Navigation:** Step 8 → Toggle "Edit Mode" ON → Add Node
**Steps:**
1. Toggle Edit Mode switch to ON
2. Tap "Add Node" button
3. Enter node name: "Market demand"
4. Confirm
**Expected:**
- New node appears in the diagram
- Node labeled "Market demand"
- Node is draggable/repositionable
- Edit mode controls visible (Add Node, Add Link)

### TC-6.4: Edit Mode — Remove Node
**Navigation:** Step 8 → Edit Mode ON → Select node → Delete
**Steps:**
1. In Edit Mode, tap on a node to select it
2. Node becomes highlighted/selected
3. Tap "Delete" or trash icon
4. Confirm deletion
**Expected:**
- Node removed from diagram
- All links connected to that node also removed
- Diagram reflows without the node

### TC-6.5: Edit Mode — Add Link
**Navigation:** Step 8 → Edit Mode ON → Add Link
**Steps:**
1. In Edit Mode, tap "Add Link" or start connecting
2. Tap source node (e.g., "Salary expectations")
3. Tap target node (e.g., "Work-life balance")
4. Select link type: Reinforcing or Balancing
**Expected:**
- New arrow drawn from source to target
- Link type label (R or B) displayed
- Link color reflects type (R=green, B=red or similar)

### TC-6.6: Edit Mode — Remove Link
**Navigation:** Step 8 → Edit Mode ON → Select link → Delete
**Steps:**
1. In Edit Mode, tap on a link to select it
2. Tap Delete button
**Expected:**
- Link removed from diagram
- Connected nodes remain
- Diagram updates

### TC-6.7: Toggle Link Type
**Navigation:** Step 8 → Edit Mode ON → Tap link
**Steps:**
1. Tap on an existing link
2. Toggle between Reinforcing and Balancing
**Expected:**
- Link label changes from R to B (or vice versa)
- Link color/style updates accordingly
- Change persists when toggling edit mode off

### TC-6.8: View Link List
**Navigation:** Step 8 → Link List tab/panel
**Steps:**
1. Tap "Link List" or expand the links panel
2. View all relationships
**Expected:**
- All links listed as: "Source → Target (R/B)"
- Each link shows: source node name, target node name, type
- List corresponds to the visual diagram
- Links can be edited/deleted from the list

---

## MODULE 7: SIMPLE SOLUTION FINDER

### TC-7.1: Create Solution Finder
**Navigation:** Home Dashboard → Scroll to "Solution Tools" → Tap "Solution Finder"
**Steps:**
1. From Dashboard, locate "Solution Tools" section (WOWO gated — must be enabled)
2. Tap "Solution Finder" card
3. Solution Finder list screen opens
4. Tap "+" or "New" button
**Expected:**
- Solution Finder creation form opens
- Fields visible: Title, Problem Statement, SMART Goal
- Form is scrollable

### TC-7.2: Fill Basic Info
**Navigation:** Continuing from TC-7.1
**Steps:**
1. Enter Title: "Reduce team attrition"
2. Enter Problem Statement: "High turnover in engineering team"
3. Enter SMART Goal: "Reduce attrition by 50% in 6 months"
4. Tap "Save" or "Next"
**Expected:**
- All fields saved
- Entry created in the database
- Can proceed to add analysis/action items

### TC-7.3: Add Action Items
**Navigation:** Solution Finder entry → Action Items section
**Steps:**
1. Open the Solution Finder entry
2. Navigate to Action Items section
3. Tap "Add Action Item"
4. Enter: "Conduct stay interviews with each team member"
5. Set priority: High
6. Add another: "Implement flexible work policy" with priority: Medium
**Expected:**
- Action items listed with priority tags
- Priority color-coded (High=Yellow, Medium=Blue)
- Items can be reordered, edited, deleted

### TC-7.4: View Solution Finder List
**Navigation:** Dashboard → Solution Finder card → List screen
**Steps:**
1. Navigate to Solution Finder from Dashboard
2. View list of all Solution Finders
**Expected:**
- All entries listed with title, date
- Most recent first
- Pull-to-refresh available
- Tap to open individual entry

### TC-7.5: Edit Solution Finder
**Navigation:** Solution Finder list → Tap entry → Edit
**Steps:**
1. Open an existing Solution Finder
2. Modify the title or problem statement
3. Save changes
**Expected:**
- Changes reflected immediately
- "Updated" timestamp changes
- List shows updated content

### TC-7.6: Delete Solution Finder
**Navigation:** Solution Finder list → Tap entry → Delete
**Steps:**
1. Open a Solution Finder entry
2. Tap Delete button
3. Confirm deletion
**Expected:**
- Confirmation dialog appears
- Entry removed from list after confirmation
- Associated action items also deleted

### TC-7.7: WOWO Gating
**Navigation:** Admin disables flag → Regular user checks
**Steps:**
1. Login as admin user
2. Go to Profile → Feature Flags settings
3. Toggle OFF "Solution Finder"
4. Save
5. Login as a regular (non-admin) user
6. Check Dashboard
**Expected:**
- "Solution Finder" card/link NOT visible on Dashboard for regular user
- Admin can still access it
- Re-enabling the flag makes it visible again

---

## MODULE 8: ADVANCED SOLUTION MATRIX

### TC-8.1: Create Solution Matrix
**Navigation:** Dashboard → Solution Tools → "Solution Matrix" card → Tap "+"
**Steps:**
1. From Dashboard, tap "Solution Matrix" card
2. Solution Matrix list opens
3. Tap "+" or "New" button
4. Creation form opens
**Expected:**
- Multi-step form displayed
- First step asks for Area of Life and SMART Goal

### TC-8.2: Define SMART Goal
**Navigation:** Solution Matrix creation → Step 1
**Steps:**
1. Select Area of Life: "Career"
2. Enter SMART Goal: "Get promoted to Senior Developer by Dec 2026"
3. Tap "Next"
**Expected:**
- Area and goal saved
- Proceed to layer analysis
- Progress indicator shows step completion

### TC-8.3: Self Layer Analysis
**Navigation:** Solution Matrix → Self Layer step
**Steps:**
1. Self layer form shows 7 sub-areas
2. For each sub-area, enter analysis, score, notes
3. Example sub-areas: Time, People, Finance, Capacity, Infrastructure, etc.
4. Fill all 7 sub-areas
**Expected:**
- Each sub-area has description/notes field and optional score
- Data auto-saves or saves on blur
- All 7 sub-areas editable
- "Self" layer header/indicator shown

### TC-8.4: Micro Layer Analysis
**Navigation:** Solution Matrix → Next → Micro Layer
**Steps:**
1. Proceed to Micro layer (immediate circle: family, team)
2. Fill 7 sub-areas for Micro context
**Expected:**
- Same structure as Self layer but contextual to Micro environment
- "Micro" layer indicator shown
- Previous Self layer data preserved

### TC-8.5: Macro Layer Analysis
**Navigation:** Solution Matrix → Next → Macro Layer
**Steps:**
1. Proceed to Macro layer (broader society, industry)
2. Fill 7 sub-areas for Macro context
**Expected:**
- Same structure for Macro environment
- All 3 layers (Self, Micro, Macro) data preserved
- "Macro" layer indicator shown

### TC-8.6: Add Action Items
**Navigation:** Solution Matrix → Action Items step
**Steps:**
1. Navigate to Action Items section
2. Add action items with assignments
3. Enter: "Complete AWS certification" assigned to "Self"
4. Enter: "Request budget for training" assigned to "Manager"
**Expected:**
- Action items listed with assignee
- Can be exported to CTT later

### TC-8.7: View Solution Matrix List
**Navigation:** Dashboard → Solution Matrix card
**Steps:**
1. Navigate to Solution Matrix list
2. View all entries
**Expected:**
- All matrices listed with title/goal, area of life, date
- Newest first
- Tap to open

### TC-8.8: Edit/Delete Solution Matrix
**Navigation:** Solution Matrix list → Tap entry → Edit or Delete
**Steps:**
1. Open an existing matrix
2. Edit: Modify goal text → Save → Verify changes
3. Delete: Tap delete → Confirm → Verify removal
**Expected:**
- Edit: Changes saved, reflected in list
- Delete: Entry removed after confirmation

### TC-8.9: WOWO Gating
**Navigation:** Admin toggles Solution Matrix flag
**Steps:**
1. Same as TC-7.7 but for Solution Matrix flag
**Expected:**
- Solution Matrix hidden when flag is OFF for non-admin users
- Visible when flag is ON

---

## MODULE 9: FACTOR DATA WEB SEARCH (DuckDuckGo)

### TC-9.1: Fetch Factor Data
**Navigation:** PRR Flow → Step 6 → Tap "Fetch Data" on a factor
**Steps:**
1. Open a decision at Step 6
2. Click "Fetch Data" button next to a factor (e.g., "Salary expectations")
3. Wait for search results
**Expected:**
- Loading spinner shown during search
- DuckDuckGo search executed for the factor name
- Results returned with: title, URL, snippet
- Multiple results (3-5) displayed

### TC-9.2: View Data Sources
**Navigation:** Step 6 → Expand factor data
**Steps:**
1. After data fetched, expand the factor's data section
2. View all sources
**Expected:**
- Each source shows: clickable title, URL, text snippet
- URLs are valid and accessible
- Data organized clearly

### TC-9.3: Search with Specific Query
**Navigation:** Step 6 → Custom search input
**Steps:**
1. Instead of auto-search, enter a custom query
2. Example: "average product manager salary 2026"
3. Submit search
**Expected:**
- Custom query used instead of just factor name
- More relevant results returned
- Results displayed in same format

### TC-9.4: Handle No Results
**Navigation:** Step 6 → Search very obscure query
**Steps:**
1. Enter a very obscure/nonsensical query
2. Submit search
**Expected:**
- Graceful handling — no crash
- Message: "No results found" or similar
- User can try again with different query

---

## MODULE 10: COLLABORATION (Shared Inbox & Notifications)

### TC-10.1: Share Decision Step
**Navigation:** PRR Flow → Any step → Share button
**Steps:**
1. Open a decision at any step (e.g., Step 2)
2. Tap "Share" button
3. Search for another user by name/email
4. Select user and confirm share
**Expected:**
- User search returns matching users
- Step data shared to selected user
- Confirmation: "Step shared successfully"
- Recipient receives notification

### TC-10.2: View Shared Inbox (Received)
**Navigation:** Home Dashboard → Tap "Shared Inbox" card
**Steps:**
1. From Dashboard, tap "Shared Inbox" quick action
2. View received shared steps
**Expected:**
- List of received shared steps shown
- Each item shows: sender name, decision title, step number, date
- Unread items highlighted
- Tap to view details

### TC-10.3: View Sent Items
**Navigation:** Shared Inbox → Switch to "Sent" tab
**Steps:**
1. Open Shared Inbox
2. Switch to Sent tab
**Expected:**
- List of shared steps you sent
- Shows: recipient name, decision title, step, date
- Status (viewed/pending)

### TC-10.4: Contribute to Shared Step
**Navigation:** Shared Inbox → Received → Open shared step → Contribute
**Steps:**
1. Open a received shared step
2. View the step data (e.g., factors)
3. Tap "Contribute" button
4. Add your input/contribution
5. Submit
**Expected:**
- Contribution form opens
- Can add text/data
- Contribution saved and linked to the shared step
- Sender receives notification of contribution

### TC-10.5: Merge Contribution
**Navigation:** Shared Inbox → Sent → Open step with contributions → Merge
**Steps:**
1. Open a sent shared step that has contributions
2. View contributions from other users
3. Tap "Merge" on a contribution
4. Confirm merge
**Expected:**
- Contribution data merged into the original decision
- Original decision updated with merged content
- Contribution marked as "merged"

### TC-10.6: Notification on Share
**Navigation:** User B checks notifications after User A shares
**Steps:**
1. User A shares a step with User B
2. User B opens the app
3. User B checks notification bell icon
**Expected:**
- Bell icon shows unread count badge (e.g., "1")
- Notification in list: "User A shared Step 2 of 'Career Decision' with you"
- Tapping notification opens the shared step

### TC-10.7: View Notifications List
**Navigation:** Dashboard → Tap bell icon (top right)
**Steps:**
1. Tap the notification bell icon on Dashboard
2. Notification list opens
**Expected:**
- All notifications listed (newest first)
- Types: shared steps, contributions, system alerts
- Unread items visually distinct (bold or highlighted)
- Each shows: icon, message, timestamp

### TC-10.8: Mark Notification Read
**Navigation:** Notifications → Tap a notification
**Steps:**
1. Open notifications list
2. Tap an unread notification
**Expected:**
- Notification marked as read
- Visual style changes (no longer bold/highlighted)
- Unread count decreases
- Content opens (e.g., shared step)

### TC-10.9: Mark All Read
**Navigation:** Notifications → "Mark All Read" button
**Steps:**
1. Open notifications list with multiple unread notifications
2. Tap "Mark All Read" button
**Expected:**
- All notifications marked as read
- Unread count goes to 0
- Bell badge disappears

### TC-10.10: Delete Notification
**Navigation:** Notifications → Swipe/delete a notification
**Steps:**
1. Open notifications list
2. Tap delete icon on a notification
3. Confirm if prompted
**Expected:**
- Notification removed from list
- List updates

### TC-10.11: Unread Count Badge
**Navigation:** Receive notifications → Check Dashboard bell
**Steps:**
1. Have another user share steps with you (creating notifications)
2. Open the app and view Dashboard
3. Observe the bell icon
**Expected:**
- Red badge with number on bell icon
- Number matches actual unread count
- Badge updates in real-time when notifications read
- Badge disappears when all read

---

## MODULE 11: EXPERT CALL (Jitsi Video)

### TC-11.1: View Expert List
**Navigation:** Profile tab → Scroll to Experts → Tap "Manage Experts"
**Steps:**
1. Navigate to Profile tab
2. Scroll to find expert management section
3. Tap to view experts
**Expected:**
- Expert list screen opens
- Shows all added experts with name, specialization
- "Add Expert" button visible

### TC-11.2: Add Expert
**Navigation:** Experts → Tap "+" or "Add Expert"
**Steps:**
1. Tap "Add Expert" button
2. Enter Name: "Dr. Sarah Chen"
3. Enter Specialization: "Career Counseling"
4. Enter Contact info
5. Save
**Expected:**
- Expert added to list
- Shows name, specialization, contact
- Can be selected for calls later

### TC-11.3: Edit Expert
**Navigation:** Experts → Tap expert → Edit
**Steps:**
1. Tap on an existing expert
2. Modify specialization: "Career & Leadership Counseling"
3. Save
**Expected:**
- Changes reflected in expert list
- Updated information persisted

### TC-11.4: Delete Expert
**Navigation:** Experts → Tap expert → Delete
**Steps:**
1. Tap delete on an expert
2. Confirm deletion
**Expected:**
- Expert removed from list
- Cannot be selected for future calls

### TC-11.5: Start Call Session
**Navigation:** Decision → Expert Call → Select expert
**Steps:**
1. Open a decision
2. Navigate to Expert Call feature
3. Select an expert from the list
4. Tap "Start Call"
**Expected:**
- Jitsi Meet room created
- Call URL generated
- Video call interface opens (or link to open in browser)
- Call session recorded in history

### TC-11.6: View Call History
**Navigation:** Profile → Call Sessions/History
**Steps:**
1. Navigate to call sessions
2. View list of past calls
**Expected:**
- All call sessions listed with: expert name, date, duration
- Completed calls show duration
- Ongoing calls show "Active" status

### TC-11.7: End Call Session
**Navigation:** During active call → End button
**Steps:**
1. During an active call, tap "End Call"
2. Confirm ending
**Expected:**
- Call session marked as ended
- Duration calculated and saved
- Session moves to history with "completed" status

---

## MODULE 12: ORGANIZATION MANAGEMENT

### TC-12.1: Create Organization
**Navigation:** Profile tab → Create Organization
**Steps:**
1. Navigate to Profile tab
2. Tap "Create Organization"
3. Enter Org Name: "TechCorp"
4. Enter Slug: "techcorp"
5. Tap "Create"
**Expected:**
- Organization created
- Creator automatically assigned `org_super_admin` role
- Org appears in profile with name and slug
- Org ID generated

### TC-12.2: View Org Branding
**Navigation:** Profile → Admin → Organization Settings
**Steps:**
1. Navigate to Organization Settings as admin
2. View branding fields
**Expected:**
- Logo URL field shown (current logo if set)
- Primary Color picker/field
- Accent Color picker/field
- Organization name and slug shown

### TC-12.3: Update Org Branding
**Navigation:** Org Settings → Edit branding → Save
**Steps:**
1. Enter Logo URL: "https://example.com/logo.png"
2. Set Primary Color: "#1E3A5F"
3. Set Accent Color: "#059669"
4. Tap "Save"
**Expected:**
- Branding settings saved
- Changes reflected across the app for org members
- Logo displays in applicable areas

### TC-12.4: View Org Members
**Navigation:** Profile → Admin → Org Members
**Steps:**
1. Navigate to Org Members screen
2. View member list
**Expected:**
- All organization members listed
- Each member shows: name, email, org_role
- Roles displayed as badges: org_super_admin, org_co_admin, org_admin, org_member
- Current user's role highlighted

### TC-12.5: Promote Member to org_admin
**Navigation:** Org Members → Select member → Change Role
**Steps:**
1. As org_super_admin, tap on a member with `org_member` role
2. Select "Promote to org_admin"
3. Confirm
**Expected:**
- Member's role changes to `org_admin`
- Role badge updates in the list
- Member now has admin privileges in the org

### TC-12.6: Promote Member to org_co_admin
**Navigation:** Org Members → Select member → Promote to co_admin
**Steps:**
1. As org_super_admin, tap on a member
2. Select "Promote to org_co_admin"
3. Confirm
**Expected:**
- Only `org_super_admin` can perform this action
- Member's role changes to `org_co_admin`
- Co-admin can now manage org_admin level members

### TC-12.7: Co-admin Promotes to org_admin
**Navigation:** Login as co_admin → Org Members → Promote member
**Steps:**
1. Login as user with `org_co_admin` role
2. Navigate to Org Members
3. Select an `org_member`
4. Promote to `org_admin`
**Expected:**
- Promotion successful
- Co-admin can manage org_admin and below

### TC-12.8: Co-admin Cannot Create Co-admin
**Navigation:** Login as co_admin → Try to promote to co_admin
**Steps:**
1. Login as `org_co_admin`
2. Try to promote any member to `org_co_admin`
**Expected:**
- Error: "Only org_super_admin can create co_admin" (403 Forbidden)
- Member's role remains unchanged

### TC-12.9: Org_admin Cannot Modify Higher Role
**Navigation:** Login as org_admin → Try to modify co_admin or super_admin
**Steps:**
1. Login as `org_admin`
2. Try to change role of a user who is `org_co_admin`
**Expected:**
- Error: "Cannot modify equal or higher role" (403 Forbidden)
- No changes made

### TC-12.10: Self-modification Denied
**Navigation:** Any admin → Try to change own role
**Steps:**
1. Login as any admin (super_admin, co_admin, or admin)
2. Navigate to Org Members
3. Try to change your own role
**Expected:**
- Error: "Cannot change your own org role" (400 Bad Request)
- Own role unchanged

### TC-12.11: Remove Member from Organization
**Navigation:** Org Members → Select member → Remove
**Steps:**
1. As admin, select a member
2. Tap "Remove from Organization"
3. Confirm
**Expected:**
- Member's org_id set to null
- Member's org_role set to null
- Member disappears from org members list
- Member can no longer access org features

### TC-12.12: Member Registers with org_id
**Navigation:** New user registration with org_id
**Steps:**
1. New user registers with org_id field filled with valid org ID
2. Complete registration
**Expected:**
- User created with `org_member` role
- User appears in org members list
- User can see org-specific content

---

## MODULE 13: WOWO FEATURE FLAGS (Admin)

### TC-13.1: View Feature Flags (Admin Only)
**Navigation:** Profile tab → Admin section → Feature Flags / Settings
**Steps:**
1. Login as admin/super_admin
2. Navigate to Profile → Admin → Settings/Feature Flags
3. View toggle list
**Expected:**
- Feature flag toggles visible: solution_finder, solution_matrix
- Each flag shows current state (ON/OFF)
- Only admin can see this section

### TC-13.2: Enable Solution Finder
**Navigation:** Feature Flags → Toggle solution_finder ON → Save
**Steps:**
1. Toggle "Solution Finder" to ON
2. Tap "Save"
3. Login as regular user
**Expected:**
- Save confirmation shown
- Regular user can now see "Solution Finder" in Dashboard
- Solution Finder card visible in Solution Tools section

### TC-13.3: Disable Solution Matrix
**Navigation:** Feature Flags → Toggle solution_matrix OFF → Save
**Steps:**
1. Toggle "Solution Matrix" to OFF
2. Save
3. Check as regular user
**Expected:**
- Solution Matrix card HIDDEN from regular user's Dashboard
- Admin can still access it
- No error when navigating elsewhere

### TC-13.4: Non-admin Sees Only Enabled Features
**Navigation:** Login as regular user → Check Dashboard
**Steps:**
1. Login as a non-admin org member
2. View Home Dashboard
**Expected:**
- Only features with flags set to ON are visible
- No toggle controls visible
- Hidden features completely absent (not grayed out)

### TC-13.5: Public Flags Endpoint
**Navigation:** API test — GET /api/feature-flags/public
**Steps:**
1. Access the public flags endpoint without authentication
**Expected:**
- Returns current flag states
- No auth required
- Used by frontend to show/hide features before login

---

## MODULE 14: CTT — CENTRALIZED TASK TRACKER

### TC-14.1: Navigate to CTT
**Navigation:** Home Dashboard → Scroll to "Task Tracker" section → Tap CTT card
**Steps:**
1. From Home Dashboard, scroll to the "Task Tracker" section
2. Blue gradient card reads "Centralized Task Tracker"
3. Tap the card
**Expected:**
- CTT Dashboard opens with header: "Task Tracker (CTT)"
- Stats row shows: Total, Open, Active, Done, Blocked
- View mode toggles visible: List, Board, Day Grid
- Filter chips visible: status filters + frequency filters
- Life area filter row visible
- If no tasks: empty state with "Create Task" and "Import Items" buttons

### TC-14.2: Create Task (One-time)
**Navigation:** CTT Dashboard → Tap "+" button in header (or "Create Task" in empty state)
**Steps:**
1. Tap "+" (add) button in the blue header area
2. New Task form opens with header "New Task"
3. Enter Task: "Complete quarterly report"
4. Enter Sub-Task: "Gather data from all departments"
5. Select Priority: "High" (tap yellow chip)
6. Select Status: "Open" (tap gray chip)
7. Tap "Create Task" button at bottom
**Expected:**
- Task created successfully
- Redirected back to CTT Dashboard
- New task appears in the list
- Task shows: title, priority color bar, status badge

### TC-14.3: All Fields Populated
**Navigation:** CTT → "+" → Fill all fields
**Steps:**
1. Create new task
2. Fill Task: "Design new feature"
3. Fill Sub-Task: "Wireframes for dashboard"
4. Select Priority: "Critical"
5. Select Status: "Open"
6. Expand "Classification" section → Select Life Area: "Career" → Decision Type: "Need"
7. Expand "Scheduling" section → Deadline: "2026-04-15" → From: "2026-04-15 09:00" → To: "2026-04-15 17:00" → Duration: "8h" → Task Owner: "Self, John"
8. Expand "Organization" section → Company: "TechCorp" → Project: "Dashboard V2" → Division: "Engineering" → Team: "Frontend"
9. Expand "Dependencies" section → Internal Dep: "API ready" → External Dep: "Client approval" → Internal Help: "Backend team" → External Help: "UX consultant" → Remarks: "High priority for Q2"
10. Tap "Create Task"
**Expected:**
- All fields saved correctly
- Task card shows: priority bar, status pill, life area tag, decision type tag, deadline, project, task owners
- Tapping the card shows all details

### TC-14.4: Create Routine Task
**Navigation:** CTT → "+" → Enable Routine
**Steps:**
1. Create new task
2. Fill Task: "Daily standup meeting"
3. Expand "Routine Settings" section
4. Toggle "Make this a Routine Task" to ON
5. Select Frequency: "Daily"
6. Select Life Area: "Career"
7. Tap "Create Task"
**Expected:**
- Task created with routine indicator
- Task card shows "Daily" routine badge (yellow)
- Task filterable by "Routine" toggle
- is_routine = true in data

### TC-14.5: Filter by Status
**Navigation:** CTT Dashboard → Tap status filter chips
**Steps:**
1. On CTT Dashboard with multiple tasks (open, in_progress, done)
2. Tap "Open" filter chip
3. Observe list
4. Tap "Active" filter chip
5. Tap "All" to reset
**Expected:**
- "Open" → Only tasks with status "open" shown
- "Active" → Only "in_progress" tasks shown
- "All" → All tasks shown
- Active filter chip highlighted with dark background
- Task count updates

### TC-14.6: Filter by Life Area
**Navigation:** CTT Dashboard → Scroll to life area filter row → Tap area
**Steps:**
1. Tap "Career" in the life area filter row
2. Observe filtered list
3. Tap "Finance" 
4. Tap "All Areas" to reset
**Expected:**
- Only tasks with matching life_area shown
- Active area chip highlighted with primary color
- Empty state if no tasks in that area
- "All Areas" resets the filter

### TC-14.7: Filter by Routine/One-time
**Navigation:** CTT Dashboard → Tap type filter (All Types / One-time / Routine)
**Steps:**
1. Tap "Routine" chip
2. Only routine tasks shown
3. Tap "One-time" chip
4. Only non-routine tasks shown
5. Tap "All Types" to reset
**Expected:**
- Correct filtering by is_routine field
- Counts match
- Active chip highlighted

### TC-14.8: Quick Status Change
**Navigation:** CTT Dashboard → List view → Task card → Quick action buttons
**Steps:**
1. View a task card in list view
2. At the bottom of the card, locate quick action buttons: Open, Active, Done, Blocked
3. Task currently "Open" → Tap "Active" button
4. Observe status change
5. Tap "Done" button
**Expected:**
- Status updates immediately without opening edit form
- Active button gets filled background with its color
- Stats row updates (e.g., Open count decreases, Active count increases)
- Status pill on card changes

### TC-14.9: Day-wise Status Grid
**Navigation:** CTT Dashboard → Switch to "Day Grid" view mode
**Steps:**
1. Tap "Day Grid" view toggle (calendar icon)
2. View task cards with day-wise grid showing 7 days
3. For a task, tap on today's date cell
4. Observe status cycle
5. Tap again to cycle through: empty → done (green ✓) → in_progress (blue clock) → blocked (red ×) → cancelled (gray ban) → empty
**Expected:**
- 7-day grid visible on each task card (yesterday through 5 days ahead)
- Today's date highlighted in blue
- Weekday labels (Mon, Tue, etc.) above date numbers
- Tapping cell cycles through statuses
- Cell background color changes with status
- Status icons appear in cells

### TC-14.10: Board View
**Navigation:** CTT Dashboard → Switch to "Board" view mode
**Steps:**
1. Tap "Board" view toggle (albums icon)
2. View Kanban-style board
**Expected:**
- Tasks grouped in columns by Life Area
- Each column has header: area icon, name, task count
- Columns are horizontally scrollable
- Task cards within columns are compact (title, priority dot, status dot, deadline)
- Tapping a card opens task detail/edit

### TC-14.11: List View
**Navigation:** CTT Dashboard → Switch to "List" view mode
**Steps:**
1. Tap "List" view toggle (list icon)
2. View task cards in list
**Expected:**
- Tasks displayed as full cards with all details
- Vertically scrollable
- Each card shows: priority bar, status pill, source badge, title, sub-task, meta tags (life area, decision type, deadline, project, owners)
- Quick action buttons at bottom of each card

### TC-14.12: Edit Task
**Navigation:** CTT Dashboard → Tap task card → Edit form
**Steps:**
1. Tap on a task card
2. Edit form opens with all current values pre-filled
3. Change Priority from "High" to "Medium"
4. Change Status from "Open" to "In Progress"
5. Tap "Update Task"
**Expected:**
- Form shows current values in all fields
- Changes saved on update
- Redirected back to CTT list
- Task card reflects new priority color and status

### TC-14.13: Delete Task
**Navigation:** CTT Dashboard → Task card → Trash icon
**Steps:**
1. On a task card, tap the trash icon (top right)
2. Confirmation dialog: "Are you sure you want to delete [task name]?"
3. Tap "Delete"
**Expected:**
- Task removed from list
- Stats update (total count decreases)
- Task cannot be recovered

### TC-14.14: Import from PRR/Solutions
**Navigation:** CTT Dashboard → Header → "Import" button
**Steps:**
1. First, ensure you have completed PRR decisions with action items (Step 10) and/or Solution Finders/Matrices with action items
2. On CTT Dashboard, tap "Import" button in the header
3. Wait for import process
**Expected:**
- Loading indicator during import
- Alert: "X new action items imported from your Decisions, Solution Finders & Matrices"
- Imported tasks appear in CTT list with source badges:
  - "PRR Decision" badge for decision action items
  - "Solution Finder" badge for finder actions
  - "Solution Matrix" badge for matrix actions
- Imported tasks pre-filled with life_area, project, and owner from source

### TC-14.15: Import Deduplication
**Navigation:** CTT Dashboard → "Import" button (again)
**Steps:**
1. After TC-14.14, tap "Import" again
**Expected:**
- Alert: "No new items to import. All action items are already tracked."
- No duplicate tasks created
- Import count = 0

### TC-14.16: Stats Dashboard
**Navigation:** CTT Dashboard → View header + stats row
**Steps:**
1. Open CTT Dashboard with multiple tasks in various states
2. View the header subtitle and stats row
**Expected:**
- Header shows: "X tasks | Y done | Z routines"
- Stats row scrollable horizontally with cards:
  - Total (primary color)
  - Open (gray) with count
  - Active (blue) with count
  - Done (green) with count
  - Blocked (red) with count
- Numbers match actual task counts

### TC-14.17: Google Calendar Link
**Navigation:** CTT Dashboard → Task card → Calendar button (blue)
**Steps:**
1. Find a task card with a deadline set
2. Tap the blue calendar button (rightmost in quick actions)
3. Observe browser/calendar opening
**Expected:**
- Google Calendar new event page opens in browser
- Event pre-filled with:
  - Title = Task name
  - Date = Task deadline
  - Description = Project, Priority, Life Area, Remarks
- If From/To time set: Event has specific time slot
- If only deadline: All-day event

### TC-14.18: Priority Color Coding
**Navigation:** CTT Dashboard → View tasks with different priorities
**Steps:**
1. Create tasks with each priority level
2. View them in list
**Expected:**
- Critical: Red priority bar (#EF4444)
- High: Amber/Yellow priority bar (#F59E0B)
- Medium: Blue priority bar (#3B82F6)
- Low: Gray priority bar (#6B7280)
- Priority bar is the colored strip on the left side of the task card

### TC-14.19: Source Type Badges
**Navigation:** CTT Dashboard → After import → View task cards
**Steps:**
1. After importing items (TC-14.14)
2. View imported task cards
**Expected:**
- Manually created tasks: No source badge
- PRR imports: Purple "PRR Decision" badge with analytics icon
- Solution Finder imports: Teal "Solution Finder" badge with search icon
- Solution Matrix imports: Pink "Solution Matrix" badge with grid icon
- GEM imports: Amber "GEM Goal" badge with flag icon

### TC-14.20: Navigate from Profile
**Navigation:** Profile tab → Scroll to tools → Tap "Task Tracker (CTT)"
**Steps:**
1. Navigate to Profile tab
2. Scroll to find "Task Tracker (CTT)" link
3. Tap it
**Expected:**
- CTT Dashboard opens
- Same functionality as navigating from Home Dashboard
- Back button returns to Profile

---

## MODULE 15: GEM — GOALS EXECUTION MANAGER

### TC-15.1: Navigate to GEM
**Navigation:** Home Dashboard → "Management Tools" section → Tap "Goals (GEM)"
**Steps:**
1. From Home Dashboard, scroll to "Management Tools" section
2. Tap "Goals (GEM)" card (teal gradient with flag icon)
**Expected:**
- GEM Dashboard opens with teal gradient header: "Goals Execution Manager"
- Summary cards: Problems (count), Needs (count), Aspirations (count), Avg Progress (%)
- Life area filter chips
- Goal type filter chips
- Empty state if no goals

### TC-15.2: Create Goal
**Navigation:** GEM Dashboard → Tap "+" button in header
**Steps:**
1. Tap "+" button
2. Goal creation form opens
3. Enter Title: "Get promoted to Senior Developer"
4. Enter Description: "Achieve senior-level technical expertise and leadership"
5. Select Life Area: "Career" (tap career chip in grid)
6. Select Goal Type: "Aspiration" (green chip)
7. Select Priority: "High"
8. Select Status: "Active"
9. Enter Target Date: "2026-12-31"
10. Enter SMART Goal: "Achieve senior dev title by Dec 2026 through certification and leadership projects"
11. Set Progress: 25% (drag slider to 25)
12. Tap "Save Goal"
**Expected:**
- Goal created successfully
- Redirected to GEM Dashboard
- Goal appears as card with: title, type badge (Aspiration in green), life area tag, progress bar at 25%, target date

### TC-15.3: Goal Type Selection
**Navigation:** GEM → New Goal → Goal Type section
**Steps:**
1. In goal creation form, view Goal Type section
2. Tap "Problem" → Observe red styling
3. Tap "Need" → Observe yellow styling
4. Tap "Aspiration" → Observe green styling
**Expected:**
- Problem: Red background + icon (#EF4444)
- Need: Yellow/amber background + bulb icon (#D97706)
- Aspiration: Green background + rocket icon (#059669)
- Only one type selectable at a time

### TC-15.4: Life Area Selection
**Navigation:** GEM → New Goal → Life Area grid
**Steps:**
1. View the 10 life area chips in a grid
2. Tap "Career" → It highlights
3. Tap "Finance" → Career deselects, Finance highlights
4. Tap "Finance" again → Deselects (none selected)
**Expected:**
- 10 life areas shown as chips with icons: Career, Finance, Relationships, Health, Assets, Knowledge, Social Image, Contributions, Hobbies, Spirituality
- Single selection (toggle)
- Selected chip: primary color background with white text
- Unselected: light background with primary color text

### TC-15.5: Progress Tracking
**Navigation:** GEM → Open goal → Adjust progress slider
**Steps:**
1. Open an existing goal
2. Drag progress slider from 25% to 50%
3. Save
**Expected:**
- Slider smoothly adjusts from 0-100%
- Current percentage displayed as text (e.g., "Progress: 50%")
- On goal card, progress bar fills to 50%
- Progress bar color: based on percentage

### TC-15.6: Filter by Life Area
**Navigation:** GEM Dashboard → Tap life area filter
**Steps:**
1. With multiple goals in different areas
2. Tap "Career" filter
3. Observe filtered list
**Expected:**
- Only career goals shown
- Filter chip highlighted
- Summary cards update for filtered view

### TC-15.7: Filter by Goal Type
**Navigation:** GEM Dashboard → Tap type filter
**Steps:**
1. Tap "Aspirations" filter
2. Only aspiration-type goals shown
**Expected:**
- Correct filtering by goal_type
- Type filter chip highlighted

### TC-15.8: Link Goal to Decision
**Navigation:** GEM → Open goal → Link section → Link Decision
**Steps:**
1. Open a goal
2. Navigate to Link section
3. Tap "Link Decision"
4. Select an existing PRR decision
5. Confirm link
**Expected:**
- Decision linked to goal
- Link appears under the goal
- Linked count updates

### TC-15.9: Link Goal to Solution Finder
**Navigation:** GEM → Goal → Link → Solution Finder
**Steps:**
1. Same flow as TC-15.8 but linking a Solution Finder
**Expected:**
- Solution Finder linked to goal
- Link type = "solution_finder"

### TC-15.10: Link Goal to Solution Matrix
**Navigation:** GEM → Goal → Link → Solution Matrix
**Steps:**
1. Same flow but linking a Solution Matrix
**Expected:**
- Matrix linked to goal
- Link type = "solution_matrix"

### TC-15.11: Launch PRR from Goal
**Navigation:** GEM → Open goal → "Launch Action" section → Start Decision
**Steps:**
1. Open a goal
2. Scroll to "Launch Action" buttons
3. Tap "Start Decision" (creates a new PRR decision seeded from goal)
**Expected:**
- New PRR decision created with goal context as the decision context
- Decision title pre-filled based on goal
- Navigated to PRR flow
- Goal linked to the new decision automatically

### TC-15.12: Edit Goal
**Navigation:** GEM → Open goal → Edit → Save
**Steps:**
1. Open an existing goal
2. Modify title, progress, or other fields
3. Tap "Update Goal"
**Expected:**
- Changes saved
- Goal card updates in dashboard
- Updated_at timestamp changes

### TC-15.13: Delete Goal
**Navigation:** GEM → Open goal → Delete button
**Steps:**
1. Open goal
2. Tap delete button (trash icon)
3. Confirm "Delete this goal?"
**Expected:**
- Goal removed from dashboard
- Goal count decreases in summary cards
- Links cleaned up

### TC-15.14: GEM Dashboard Stats
**Navigation:** GEM Dashboard → View summary cards
**Steps:**
1. Open GEM Dashboard with multiple goals of different types
2. View summary cards at the top
**Expected:**
- "Problems" card shows count of problem-type goals
- "Needs" card shows count of need-type goals
- "Aspirations" card shows count of aspiration-type goals
- "Avg Progress" card shows average across all goals

### TC-15.15: Navigate from Profile
**Navigation:** Profile → Tap "Goals (GEM)" link
**Steps:**
1. Profile tab → Tap GEM link with green flag icon
**Expected:**
- GEM Dashboard opens
- Back button returns to Profile

---

## MODULE 16: TEPFI RESOURCE MATRIX

### TC-16.1: Navigate to TEPFI
**Navigation:** Home Dashboard → "Management Tools" → Tap "TEPFI Matrix"
**Steps:**
1. From Dashboard, tap "TEPFI Matrix" card (purple gradient with cube icon)
**Expected:**
- TEPFI Dashboard opens with purple gradient header
- View toggles: Matrix / Entries
- Life area filters
- 5×3 matrix overview (if data exists) or empty state

### TC-16.2: View Matrix Overview
**Navigation:** TEPFI Dashboard → "Matrix" tab (default)
**Steps:**
1. With at least 1 TEPFI entry created
2. View the matrix grid
**Expected:**
- Grid shows: 5 rows (Time, Effort, People, Finance, Infrastructure) × 3 columns (Self, Micro, Macro)
- Column headers show layer icons (person, people-circle, globe)
- Row headers show dimension icons (time, flash, people, cash, construct)
- Each cell shows a score circle with number
- Score circles color-coded: 8-10=Green, 6-7=Blue, 4-5=Yellow, 2-3=Orange, 0-1=Red
- Scores are AVERAGES across all entries

### TC-16.3: Create TEPFI Assessment
**Navigation:** TEPFI Dashboard → Tap "+" in header
**Steps:**
1. Tap "+" button
2. Assessment form opens: "New TEPFI Assessment"
3. Enter Title: "Career Development Resources Q1"
4. Select Life Area: "Career"
**Expected:**
- Form shows title input and life area selector
- Below: 5 collapsible dimension sections (Time, Effort, People, Finance, Infrastructure)
- First dimension expanded by default

### TC-16.4: Fill Time Dimension
**Navigation:** TEPFI Entry form → Time section (expanded)
**Steps:**
1. Time section shows 3 layer cards: Self, Micro, Macro
2. For Self layer:
   - Drag Score slider to 7 (label updates: "Score (0-10): 7")
   - Enter Description: "8 hours daily focused work time"
   - Enter Notes: "Good allocation, could optimize meetings"
3. For Micro layer:
   - Score: 5
   - Description: "Team meetings take 2 hours daily"
4. For Macro layer:
   - Score: 3
   - Description: "Industry events once per quarter"
**Expected:**
- Slider moves smoothly from 0-10
- Score text updates in real-time
- Slider track colored with dimension color (blue for Time)
- Description and notes saved per layer
- Quick score summary dots appear in the dimension header (7, 5, 3 dots)

### TC-16.5 through TC-16.8: Fill Effort/People/Finance/Infrastructure
**Navigation:** TEPFI Entry form → Expand each dimension
**Steps:**
1. For each of the remaining 4 dimensions, expand the section
2. Fill Self, Micro, Macro layers with scores and descriptions
3. Observe dimension header updates with score dots
**Expected:**
- Same interaction pattern as TC-16.4
- Each dimension has its own color: Effort=Yellow, People=Green, Finance=Purple, Infrastructure=Red
- Score dots in collapsed headers show all 3 layer scores
- When collapsing a section, the next auto-expands (optional)

### TC-16.9: Score Color Coding
**Navigation:** TEPFI Entry form → Set various scores
**Steps:**
1. Set different scores: 1, 3, 5, 7, 9
2. Observe color changes
**Expected:**
- 8-10: Green circle (#10B981)
- 6-7: Blue circle (#3B82F6)
- 4-5: Yellow circle (#F59E0B)
- 2-3: Orange circle (#F97316)
- 0-1: Red circle (#EF4444)

### TC-16.10: View Entries List
**Navigation:** TEPFI Dashboard → Switch to "Entries" tab
**Steps:**
1. Tap "Entries" view toggle
2. View entry cards
**Expected:**
- Each entry card shows:
  - Life area badge with icon
  - Status badge (active/draft)
  - Title
  - Mini 5×3 matrix grid with colored score cells
  - Completion percentage bar at bottom
- Tap card opens the entry for editing

### TC-16.11: Filter by Life Area
**Navigation:** TEPFI Dashboard → Tap area filter
**Steps:**
1. Tap "Career" filter chip
2. View filtered list
**Expected:**
- Only career-related entries shown
- Matrix overview recalculates for filtered entries

### TC-16.12: Edit TEPFI Entry
**Navigation:** TEPFI Entries → Tap entry → Edit
**Steps:**
1. Tap an entry card to open it
2. Modify a score (e.g., Time/Self from 7 to 8)
3. Tap "Update"
**Expected:**
- Changes saved
- Matrix overview updates with new average
- Entry card reflects new scores

### TC-16.13: Delete TEPFI Entry
**Navigation:** TEPFI Entries → Tap entry → Delete (trash icon)
**Steps:**
1. Open entry → Delete button or list → trash icon
2. Confirm deletion
**Expected:**
- Entry removed
- Matrix overview recalculates without deleted entry

### TC-16.14: Import from Solution Matrix
**Navigation:** TEPFI → Import from Solution Matrix
**Steps:**
1. Ensure a Solution Matrix exists with Self/Micro/Macro data
2. Use the import API (POST /api/tepfi/import-from-matrix/{matrix_id})
**Expected:**
- TEPFI entry created with mapped data from Solution Matrix
- Title prefixed with "From: [matrix SMART goal]"
- Layers (Self, Micro, Macro) mapped from matrix sub-areas
- Deduplication: Cannot import same matrix twice

### TC-16.15: Dashboard Aggregate
**Navigation:** TEPFI Dashboard → Matrix view with multiple entries
**Steps:**
1. Create 2-3 TEPFI entries with different scores
2. View Matrix overview
**Expected:**
- Scores in the 5×3 grid are AVERAGES across all entries
- More entries = more accurate averages
- Dashboard shows total_entries count

### TC-16.16: Navigate from Profile
**Navigation:** Profile → TEPFI Matrix link
**Steps:**
1. Profile tab → Tap "TEPFI Matrix" (purple cube icon)
**Expected:**
- TEPFI Dashboard opens
- Back button returns to Profile

---

## MODULE 17: GOOGLE CALENDAR SCHEDULING

### TC-17.1: Navigate to Calendar View
**Navigation:** Home Dashboard → Tap "Calendar & Scheduling" card
**Steps:**
1. From Dashboard, tap "Calendar & Scheduling" card (blue gradient)
**Expected:**
- Calendar View opens with blue gradient header
- Shows: "X upcoming tasks in next 30 days"
- Time range filter: 7d, 14d, 30d, 60d, 90d
- "Export All" button in header

### TC-17.2: View Upcoming Tasks
**Navigation:** Calendar View → View timeline
**Steps:**
1. With CTT tasks that have deadlines set
2. View the timeline
**Expected:**
- Tasks grouped by date
- Each date group has:
  - Date box showing: weekday (Mon), day number (25), month (Mar)
  - Horizontal line divider
  - Task count (e.g., "2 tasks")
- Tasks under each date show: priority dot, task name, status pill, project
- Dates sorted chronologically

### TC-17.3: Time Range Filter
**Navigation:** Calendar View → Tap range chips
**Steps:**
1. Default shows 30 days
2. Tap "7d" → View narrows to 7 days
3. Tap "90d" → View expands to 90 days
4. Tap "14d" → View shows 14 days
**Expected:**
- Timeline updates to show tasks within selected range
- Active chip highlighted in blue
- Header subtitle updates: "X upcoming tasks in next Yd days"
- Task count changes per range

### TC-17.4: Single Task Calendar Export
**Navigation:** Calendar View → Task row → Tap calendar icon
**Steps:**
1. Find a task in the timeline
2. Tap the blue open/calendar icon on the right side
3. Browser opens
**Expected:**
- Google Calendar new event page opens
- Title = Task name
- Description includes: Project, Priority, Life Area, Notes
- Date set from task deadline

### TC-17.5: Batch Export
**Navigation:** Calendar View → Header → Tap "Export All"
**Steps:**
1. Tap "Export All" button in the header
2. Wait for generation
**Expected:**
- Alert: "X tasks ready. Each will open in Google Calendar."
- Options: "Cancel" and "Open First"
- Tapping "Open First" opens Google Calendar with the first task
- Works for all non-done tasks with deadlines

### TC-17.6: Date Formatting with From/To Time
**Navigation:** Task with specific time → Export
**Steps:**
1. Create CTT task with: from_time="2026-04-15 09:00", to_time="2026-04-15 11:00"
2. Export to Google Calendar
**Expected:**
- Google Calendar event shows: 9:00 AM - 11:00 AM on April 15
- Not an all-day event
- Time correctly formatted

### TC-17.7: Export with Deadline Only
**Navigation:** Task with only deadline → Export
**Steps:**
1. Create CTT task with: deadline="2026-04-20" (no from/to time)
2. Export to Google Calendar
**Expected:**
- Google Calendar creates all-day event on April 20
- No specific time set

### TC-17.8: Empty Calendar
**Navigation:** Calendar View → No tasks with deadlines
**Steps:**
1. Open Calendar View when no tasks have deadlines
**Expected:**
- Empty state icon (calendar outline)
- Text: "No Upcoming Deadlines"
- Subtitle: "Tasks with deadlines will appear here in a timeline view"

### TC-17.9: Today Indicator
**Navigation:** Calendar View → Today's date
**Steps:**
1. Open Calendar View with task(s) due today
2. Find today's date in timeline
**Expected:**
- Today's date box has BLUE background (#4285F4)
- White text on blue background
- Visually distinct from other dates

### TC-17.10: Past Date Styling
**Navigation:** Calendar View → Past dates
**Steps:**
1. Open Calendar View with overdue tasks
2. Find past date entries
**Expected:**
- Past date boxes have reduced opacity (0.6)
- Tasks still visible but dimmed
- Clear visual distinction from future dates

### TC-17.11: Navigate from Profile
**Navigation:** Profile → Calendar & Scheduling link
**Steps:**
1. Profile tab → Tap "Calendar & Scheduling" (blue calendar icon)
**Expected:**
- Calendar View opens
- Back button returns to Profile

---

## MODULE 18: LIFESTYLE DEZIDER (Routine Manager)

### TC-18.1: Navigate to Lifestyle
**Navigation:** Home Dashboard → Scroll down → Tap "Lifestyle Dezider" card
**Steps:**
1. From Dashboard, scroll to find "Lifestyle Dezider" card (green gradient with leaf icon)
2. Tap the card
**Expected:**
- Lifestyle Dashboard opens with green gradient header
- "Import" button and "+" button in header
- Effectiveness card with score circle
- Daily/Weekly/Monthly assessment buttons
- Stats row with active routine count and frequency breakdown
- Routines/Assessments tab toggle

### TC-18.2: Create Routine (Daily)
**Navigation:** Lifestyle Dashboard → Tap "+" button in header
**Steps:**
1. Tap "+" button
2. Routine form opens: "New Routine"
3. Enter Routine Name: "Morning Meditation"
4. Enter Description: "20 minutes guided meditation using Headspace app"
5. Select Frequency: "Daily" (blue chip)
6. Select Life Area: "Spirituality" (leaf icon)
7. Select Priority: "High" (yellow chip)
8. Select Factor Category: "Primary Factor" (radio button)
9. Enter Time Slot: "6:00 AM - 6:20 AM"
10. Enter Expected Value: "20"
11. Enter Unit: "minutes"
12. Ensure "Active" toggle is ON
13. Tap "Create Routine"
**Expected:**
- Routine created, redirected to Lifestyle Dashboard
- Routine appears in list with: blue "Daily" badge, spirituality area pill, high priority bar
- Stats update: Active count +1, Daily count +1

### TC-18.3: Create Routine (Weekly)
**Navigation:** Lifestyle → "+" → Weekly
**Steps:**
1. Create routine: "Weekly Exercise Plan Review"
2. Frequency: "Weekly" (green chip)
3. Life Area: "Health"
4. Priority: "Medium"
5. Category: "Secondary Factor"
6. Save
**Expected:**
- Green "Weekly" badge on routine card
- Health area pill shown
- Stats: Weekly count +1

### TC-18.4: Create Routine (Monthly)
**Navigation:** Lifestyle → "+" → Monthly
**Steps:**
1. Create routine: "Monthly Budget Review"
2. Frequency: "Monthly" (purple chip)
3. Life Area: "Finance"
4. Save
**Expected:**
- Purple "Monthly" badge
- Finance area pill

### TC-18.5: Create Routine (Hourly)
**Navigation:** Lifestyle → "+" → Hourly
**Steps:**
1. Create: "Water Intake Check"
2. Frequency: "Hourly" (red chip)
3. Life Area: "Health"
4. Save
**Expected:**
- Red "Hourly" badge on card

### TC-18.6: Create Routine (Fortnightly)
**Navigation:** Lifestyle → "+" → Fortnightly
**Steps:**
1. Create: "Bi-weekly Team Retrospective"
2. Frequency: "Fortnightly" (amber chip)
3. Life Area: "Career"
4. Save
**Expected:**
- Amber "Fortnightly" badge on card

### TC-18.7: All Routine Fields
**Navigation:** Verify all fields saved correctly
**Steps:**
1. Open the routine created in TC-18.2
2. Verify all fields preserved
**Expected:**
- Name: "Morning Meditation"
- Description: "20 minutes guided..."
- Frequency: Daily
- Life Area: Spirituality
- Priority: High
- Category: Primary
- Time Slot: "6:00 AM - 6:20 AM"
- Expected Value: "20"
- Unit: "minutes"
- Active: ON

### TC-18.8: Factor Category Selection
**Navigation:** Routine form → Factor Category section
**Steps:**
1. In routine form, view Factor Category section
2. Tap "Primary Factor" → Radio button filled, green highlight
3. Tap "Secondary Factor" → Primary deselects, Secondary selects
**Expected:**
- "Primary Factor" description: "Core routine critical to your lifestyle"
- "Secondary Factor" description: "Supporting routine that enhances quality"
- Single selection (radio behavior)
- This category determines how the routine is classified as a factor in PRR Lifestyle Assessment

### TC-18.9: Edit Routine
**Navigation:** Lifestyle Dashboard → Tap routine card → Edit form
**Steps:**
1. Tap a routine card in the list
2. Edit form opens with pre-filled values
3. Change frequency from "Daily" to "Weekly"
4. Tap "Update Routine"
**Expected:**
- Changes saved
- Card updates with new frequency badge
- Stats recalculate

### TC-18.10: Delete Routine
**Navigation:** Lifestyle Dashboard → Routine card → Trash icon
**Steps:**
1. On routine card, tap trash icon
2. Alert: 'Delete "Morning Meditation"?'
3. Tap "Delete"
**Expected:**
- Routine removed from list
- Stats update: active count -1
- Routine no longer available for assessments

### TC-18.11: Deactivate Routine
**Navigation:** Routine form → Toggle Active OFF → Save
**Steps:**
1. Open routine
2. Scroll to Active toggle
3. Switch to OFF
4. Save
**Expected:**
- "Inactive" red badge appears on routine card
- Routine NOT included in lifestyle assessments
- Routine still visible in list (but marked inactive)
- Active count decreases in stats

### TC-18.12: Filter by Frequency
**Navigation:** Lifestyle Dashboard → Routines tab → Frequency filter chips
**Steps:**
1. Tap "Daily" filter chip → Only daily routines shown
2. Tap "Weekly" → Only weekly shown
3. Tap "All" → All routines shown
**Expected:**
- Correct filtering
- Active chip highlighted with green background and white text
- List updates

### TC-18.13: Import from CTT
**Navigation:** Lifestyle Dashboard → Header → "Import" button
**Steps:**
1. Ensure CTT has routine tasks (is_routine=true)
2. Tap "Import" button in header
3. Wait for import
**Expected:**
- Alert: "X routine(s) imported from CTT"
- Imported routines appear in list
- Source linked (source_ctt_task_id set)
- Frequency, life area, priority mapped from CTT task

### TC-18.14: Import Deduplication
**Navigation:** Lifestyle → "Import" again
**Steps:**
1. After TC-18.13, tap "Import" again
**Expected:**
- Alert: "No new routines to import. All CTT routines are already tracked."
- imported count = 0

### TC-18.15: View Assessments Tab
**Navigation:** Lifestyle Dashboard → Tap "Assessments" tab
**Steps:**
1. Tap "Assessments" tab toggle (right side)
2. View assessment history
**Expected:**
- Tab highlighted with green background
- Assessment cards shown with:
  - Effectiveness dot (color-coded)
  - Assessment title
  - Period badge (daily/weekly/monthly)
  - Date
  - Factors count (e.g., "5/8 factors")
  - Score percentage
  - "Complete" or "In Progress" label

### TC-18.16: Dashboard Stats
**Navigation:** Lifestyle Dashboard → View stats row
**Steps:**
1. With multiple routines created
2. View stats row below effectiveness card
**Expected:**
- Scrollable stat cards showing:
  - "Active" with total count (dark border)
  - One card per frequency with count: "Daily: 3", "Weekly: 1", etc.
  - Color-coded borders matching frequency colors

### TC-18.17: Effectiveness Card
**Navigation:** Lifestyle Dashboard → View top card
**Steps:**
1. After completing at least one assessment
2. View the effectiveness card
**Expected:**
- "Latest Effectiveness" label
- Large score number with color: 80%+=Green, 60-79%=Blue, 40-59%=Yellow, <40%=Red
- Status label: "Excellent", "Good", "Fair", or "Needs Attention"
- Circle indicator on the right with score

### TC-18.18: Sparkline Trend
**Navigation:** Lifestyle Dashboard → Effectiveness card (after 2+ assessments)
**Steps:**
1. Complete multiple assessments
2. View sparkline in effectiveness card
**Expected:**
- "Recent" label with mini bar chart
- Bars represent recent assessment scores
- Bar heights proportional to scores
- Bar colors match effectiveness color scheme
- Most recent on the right

### TC-18.19: Navigate from Profile
**Navigation:** Profile → Lifestyle Dezider link
**Steps:**
1. Profile tab → Tap "Lifestyle Dezider" (green leaf icon)
**Expected:**
- Lifestyle Dashboard opens
- Back button returns to Profile

---

## MODULE 19: LIFESTYLE ANALYZER (PRR-based Assessment)

### TC-19.1: Start Daily Assessment
**Navigation:** Lifestyle Dashboard → Effectiveness card → Tap "Daily" button
**Steps:**
1. Ensure at least 1 active daily or hourly routine exists
2. In the effectiveness card, tap "Daily" button (with "today" icon)
3. Wait for assessment creation
**Expected:**
- Loading briefly while PRR decision is created
- Navigated to PRR flow (prr/[decision_id])
- Decision title: "Lifestyle Assessment (Daily) - [Today's Date]"
- Context mentions: "Lifestyle effectiveness assessment (daily)..."

### TC-19.2: Verify Factors are Routines (Daily)
**Navigation:** Continuing from TC-19.1 → Step 2 (Factors)
**Steps:**
1. In the created lifestyle PRR decision, navigate to Step 2
2. View the factors list
**Expected:**
- Factors = Only active routines with frequency "hourly" or "daily"
- Weekly, fortnightly, monthly routines NOT included
- Each factor name matches a routine name (e.g., "Morning Meditation", "Water Intake Check")
- Factor category matches routine category (primary/secondary)

### TC-19.3: Start Weekly Assessment
**Navigation:** Lifestyle Dashboard → Tap "Weekly" button
**Steps:**
1. Tap "Weekly" button (with "calendar" icon)
2. Wait for PRR decision creation
**Expected:**
- PRR decision created with factors = hourly + daily + weekly routines
- Fortnightly and monthly routines NOT included
- More factors than daily assessment

### TC-19.4: Start Monthly Assessment
**Navigation:** Lifestyle Dashboard → Tap "Monthly" button
**Steps:**
1. Tap "Monthly" button (with "calendar-number" icon)
2. Wait for PRR decision creation
**Expected:**
- PRR decision created with ALL active routines as factors
- Includes hourly, daily, weekly, fortnightly, monthly
- Most comprehensive assessment

### TC-19.5: Verify Single Option
**Navigation:** Lifestyle Assessment PRR → Step 5 (Options)
**Steps:**
1. In the lifestyle PRR decision, navigate to Step 5
2. View options
**Expected:**
- Only ONE option: "My Lifestyle"
- Cannot add more options (this is a single-option assessment)
- Option name clearly indicates self-assessment nature

### TC-19.6: Complete Full PRR Flow
**Navigation:** Lifestyle Assessment → Steps 1 through 10
**Steps:**
1. Step 1: Review decision title and context (pre-filled)
2. Step 2: Verify factors (routines) — already populated
3. Step 3: Classify factors (quantitative/qualitative)
4. Step 4: Prioritize factors (rate 1-100 importance)
5. Step 5: Verify "My Lifestyle" option
6. Step 6: Optionally fetch data for factors
7. Step 7: Rate "My Lifestyle" against each factor
8. Step 8: View CLD (optional)
9. Step 9: Assessment — LMH or Custom % for each factor
10. Step 10: View final effectiveness score
**Expected:**
- Complete flow works end-to-end
- All 10 steps accessible
- Data saves at each step
- Final worth_percentage = Lifestyle Effectiveness Score

### TC-19.7: Assessment with LMH Mode
**Navigation:** Lifestyle Assessment → Step 9
**Steps:**
1. Navigate to Step 9
2. For factor "Morning Meditation": Select "High" (H)
3. For factor "Water Intake": Select "Medium" (M)
4. For factor "Exercise Review": Select "Low" (L)
**Expected:**
- High → Maps to high percentage (e.g., ~80%)
- Medium → Maps to medium percentage (e.g., ~50%)
- Low → Maps to low percentage (e.g., ~20%)
- LMH buttons color-coded
- Running total updates

### TC-19.8: Assessment with Custom %
**Navigation:** Lifestyle Assessment → Step 9 → Custom mode
**Steps:**
1. For a factor, switch to Custom % mode
2. Enter 72%
**Expected:**
- Custom percentage applied instead of LMH
- Value accepted (0-100 range)
- Overrides any LMH selection

### TC-19.9: Final Effectiveness Score
**Navigation:** Lifestyle Assessment → Complete Step 9 → View result
**Steps:**
1. Complete assessment for all factors
2. View the option "My Lifestyle" worth_percentage
**Expected:**
- Effectiveness % calculated:
  - Formula: Weighted average of (Factor Priority × Factor Assessment %)
  - Score is the lifestyle effectiveness percentage
- Displayed prominently (e.g., "72.5%")
- Color-coded: Green 80%+, Blue 60-79%, Yellow 40-59%, Red <40%

### TC-19.10: View Assessment History
**Navigation:** Lifestyle Dashboard → Assessments tab
**Steps:**
1. After completing one or more assessments
2. Switch to "Assessments" tab
**Expected:**
- All lifestyle assessments listed with:
  - Color dot (effectiveness color)
  - Title (e.g., "Lifestyle Assessment (Daily) - 24 Mar 2026")
  - Period badge (daily=blue, weekly=green, monthly=purple)
  - Date
  - Factors completion (e.g., "5/5 factors")
  - Effectiveness percentage
  - "Complete" or "In Progress" label
- Tap to open and review/continue the PRR decision

### TC-19.11: Assessment Completion Status
**Navigation:** Assessments tab → Check completion indicators
**Steps:**
1. Start an assessment but don't complete it → View in Assessments tab
2. Complete an assessment → View in Assessments tab
**Expected:**
- Incomplete: "In Progress" label, factors show "3/5 factors"
- Complete: "Complete" label, factors show "5/5 factors", effectiveness % shown

### TC-19.12: Navigate to Analytics
**Navigation:** Lifestyle Dashboard → Tap bar-chart icon button (next to tabs)
**Steps:**
1. On Lifestyle Dashboard, locate the analytics button (bar chart icon, right side of tabs)
2. Tap it
**Expected:**
- Lifestyle Analytics screen opens with green gradient header
- Period filter: Daily/Weekly/Monthly/All
- Overview, trend, area breakdown, legend sections

### TC-19.13: Analytics — Average Effectiveness
**Navigation:** Lifestyle Analytics → Overview card
**Steps:**
1. With multiple completed assessments
2. View the overview card
**Expected:**
- "Average Effectiveness" label
- Large percentage number (average across completed assessments)
- Color-coded circle indicator
- Status label (Excellent/Good/Fair/Needs Attention)
- Below: "X completed", "Y day streak", "Z total" meta info

### TC-19.14: Analytics — Trend Chart
**Navigation:** Lifestyle Analytics → Trend section
**Steps:**
1. Scroll to "Effectiveness Trend" section
2. View bar chart
**Expected:**
- Horizontal bar chart showing scores over time
- Each bar represents one assessment
- Bar height proportional to effectiveness %
- Bar color matches effectiveness color
- Date label under each bar (MM-DD format)
- Incomplete assessments shown in gray
- Horizontally scrollable if many assessments

### TC-19.15: Analytics — Streak Tracking
**Navigation:** Lifestyle Analytics → Overview meta row
**Steps:**
1. Complete 3 consecutive daily assessments with 60%+ effectiveness
2. View analytics overview
**Expected:**
- "3 day streak" with flame icon
- Streak counts consecutive assessments where effectiveness ≥ 60%
- Streak resets if an assessment falls below 60%
- Streak = 0 if latest assessment is below threshold

### TC-19.16: Analytics — Life Area Breakdown
**Navigation:** Lifestyle Analytics → "By Life Area" section
**Steps:**
1. With assessments covering routines in multiple life areas
2. View area breakdown section
**Expected:**
- Each life area with routines shows:
  - Area icon (e.g., briefcase for Career)
  - Area name
  - Progress bar (width proportional to average score)
  - Percentage number
- Areas sorted by score (highest first)
- Progress bar color matches effectiveness color

### TC-19.17: Analytics — Period Filter
**Navigation:** Lifestyle Analytics → Period toggles
**Steps:**
1. Tap "Daily" → Shows only daily assessment analytics
2. Tap "Weekly" → Shows weekly analytics
3. Tap "Monthly" → Shows monthly analytics
4. Tap "All" → Shows aggregate across all periods
**Expected:**
- Trend chart updates for selected period
- Average recalculates
- Area breakdown may change based on period
- Active toggle highlighted with green background

### TC-19.18: Error — No Active Routines
**Navigation:** Delete all routines → Try to start assessment
**Steps:**
1. Delete all routines (or deactivate all)
2. Tap "Daily" assessment button
**Expected:**
- Error alert: "No active routines found. Add routines to your Lifestyle Dezider first."
- User stays on Lifestyle Dashboard
- No empty PRR decision created

### TC-19.19: Resume Incomplete Assessment
**Navigation:** Start assessment → Leave → Return
**Steps:**
1. Start a daily assessment (creates PRR decision)
2. Complete Steps 1-5 but leave before Step 9
3. Go back to Lifestyle Dashboard → Assessments tab
4. Tap the incomplete assessment
**Expected:**
- PRR decision opens
- All previously entered data preserved
- Can continue from where left off
- Status shows "In Progress" until fully completed

---

## MODULE 20: DASHBOARD & NAVIGATION

### TC-20.1: Home Dashboard Loads
**Navigation:** Login → Dashboard tab
**Steps:**
1. Login successfully
2. Dashboard tab selected (bottom left)
**Expected:**
- Dashboard loads with all sections visible on scroll:
  - Quick Actions: "Start PRR Decision", "Test123"
  - Collaborate & Insights: "Shared Inbox", "Notifications", "Analytics"
  - Solution Tools (WOWO gated): Solution Finder, Solution Matrix
  - Task Tracker: CTT card with stats
  - Management Tools: Goals (GEM), TEPFI Matrix
  - Calendar & Scheduling card
  - Lifestyle Dezider card

### TC-20.2: CTT Card with Live Stats
**Navigation:** Dashboard → View CTT card
**Steps:**
1. After creating CTT tasks
2. View the CTT card on Dashboard
**Expected:**
- Blue gradient card showing:
  - Title: "Centralized Task Tracker"
  - Subtitle: "Track all action items..."
  - Stats row: Total | Active | Done | Blocked | Routines
  - Numbers update based on actual task data
- Tap navigates to CTT Dashboard

### TC-20.3 through TC-20.6: Feature Card Navigation
**Steps for each:** Tap the respective card on Dashboard
**Expected:**
- TC-20.3: Goals (GEM) → GEM Dashboard opens
- TC-20.4: TEPFI Matrix → TEPFI Dashboard opens
- TC-20.5: Calendar & Scheduling → Calendar View opens
- TC-20.6: Lifestyle Dezider → Lifestyle Dashboard opens
- Each opens the correct screen with proper header
- Back button returns to Dashboard

### TC-20.7: PRR Quick Action
**Navigation:** Dashboard → Tap "Start PRR Decision"
**Steps:**
1. Tap "Start PRR Decision" quick action
**Expected:**
- New decision creation flow begins
- Can enter title and context

### TC-20.8: Test123 Quick Action
**Navigation:** Dashboard → Tap "Test123"
**Steps:**
1. Tap "Test123" quick action
**Expected:**
- Test123 instant decision screen opens

### TC-20.9: Profile Tab Navigation
**Navigation:** Bottom tab bar → Tap Profile (right tab)
**Steps:**
1. Tap Profile icon in bottom tab bar
**Expected:**
- Profile screen shows with user info
- All tool links present: CTT, GEM, TEPFI, Calendar, Lifestyle
- Admin section (if admin): Experts, Templates, Settings, Org Members
- Logout button at bottom

### TC-20.10: All Profile Tool Links
**Navigation:** Profile → Test each tool link
**Steps:**
1. Tap "Task Tracker (CTT)" → CTT opens → Back
2. Tap "Goals (GEM)" → GEM opens → Back
3. Tap "TEPFI Matrix" → TEPFI opens → Back
4. Tap "Calendar & Scheduling" → Calendar opens → Back
5. Tap "Lifestyle Dezider" → Lifestyle opens → Back
**Expected:**
- Each link opens the correct screen
- Back button returns to Profile each time
- No navigation errors

### TC-20.11: Back Button Navigation
**Navigation:** Open any deep screen → Press back
**Steps:**
1. Dashboard → CTT → Create Task → Back → Back (should be on Dashboard)
2. Profile → GEM → Create Goal → Back → Back (should be on Profile)
**Expected:**
- Back button consistently returns to previous screen
- No broken navigation stacks
- Eventually returns to Dashboard or Profile (root tabs)

### TC-20.12: Pull-to-Refresh
**Navigation:** Any list screen → Pull down
**Steps:**
1. On CTT Dashboard, pull the list down
2. On GEM Dashboard, pull down
3. On Lifestyle Dashboard, pull down
**Expected:**
- Refresh indicator appears
- Data re-fetches from server
- New/updated content appears
- Refresh indicator disappears

---

## MODULE 21: ANALYTICS

### TC-21.1: View Folder Analytics
**Navigation:** Dashboard → Analytics quick action
**Steps:**
1. Tap "Analytics" in Collaborate & Insights section
2. View folder-level analytics
**Expected:**
- Folders listed with decision counts
- Aggregate statistics per folder
- Visual representations (charts/cards)

### TC-21.2: Decision Analytics
**Navigation:** Analytics → Select specific folder
**Steps:**
1. Tap on a folder in analytics
2. View folder-specific analytics
**Expected:**
- Decision count in folder
- Completion rates
- Average scores
- Timeline of decisions

### TC-21.3: Stats Overview
**Navigation:** Dashboard → Stats shown in header/overview area
**Steps:**
1. View Dashboard
2. Check stats cards (decisions, completed, journal entries)
**Expected:**
- Total decisions count
- Completed decisions count
- Total journal entries
- Numbers accurate and up-to-date

---

## MODULE 22: TEMPLATES

### TC-22.1: Save Decision as Template
**Navigation:** PRR Decision → Options menu → Save as Template
**Steps:**
1. Open a completed PRR decision
2. Find "Save as Template" option
3. Confirm
**Expected:**
- Template created from the decision
- Template preserves: title structure, factors, options structure
- Success message shown

### TC-22.2: View Templates
**Navigation:** Profile → Admin → Templates section
**Steps:**
1. Navigate to templates list
**Expected:**
- All saved templates listed
- Each shows: title, creator, date, approval status
- System templates also visible

### TC-22.3: Use Template
**Navigation:** Templates → Select → Use
**Steps:**
1. Tap on a template
2. Tap "Use Template"
3. New decision created
**Expected:**
- New PRR decision created with template's structure
- Factors pre-populated from template
- Options structure copied
- User can modify everything
- Decision linked to template

### TC-22.4: Admin Approve Template
**Navigation:** Admin → Templates → Approve
**Steps:**
1. As admin, view templates list
2. Find an unapproved template
3. Tap "Approve"
**Expected:**
- Template status changes to "approved"
- Template becomes visible to all org users
- Approved badge shown

### TC-22.5: Import Template
**Navigation:** Templates → Import
**Steps:**
1. Find a shared/public template
2. Tap "Import"
**Expected:**
- Template added to user's collection
- Can be used like personal templates

### TC-22.6: Decision Templates List
**Navigation:** View pre-built system templates
**Steps:**
1. Navigate to templates section
2. View system/pre-built templates
**Expected:**
- System templates available (if any configured)
- Clearly marked as "System" or "Default"
- Can be used but not edited/deleted

---

## MODULE 23: CROSS-MODULE INTEGRATION FLOWS

### TC-23.1: PRR → CTT Flow
**Navigation:** Complete PRR Decision → CTT → Import
**Steps:**
1. Create a PRR decision, go through all 10 steps
2. In Step 10, ensure action items are defined
3. Navigate to CTT Dashboard
4. Tap "Import" button
5. Verify imported tasks
**Expected:**
- Action items from Step 10 appear as CTT tasks
- Source badge: "PRR Decision" (purple)
- Life area mapped from decision
- Project/owner info carried over
- task.source_type = "decision"

### TC-23.2: Solution Finder → CTT Flow
**Navigation:** Create Solution Finder with actions → CTT Import
**Steps:**
1. Create Solution Finder with action items
2. Navigate to CTT → Tap "Import"
3. Check imported tasks
**Expected:**
- Solution Finder actions appear in CTT
- Source badge: "Solution Finder" (teal)
- task.source_type = "solution_finder"

### TC-23.3: Solution Matrix → CTT Flow
**Navigation:** Create Solution Matrix with actions → CTT Import
**Steps:**
1. Create Solution Matrix with action items
2. Navigate to CTT → Import
**Expected:**
- Matrix actions appear in CTT
- Source badge: "Solution Matrix" (pink)
- task.source_type = "solution_matrix"

### TC-23.4: CTT → Lifestyle Flow
**Navigation:** Create routine tasks in CTT → Lifestyle Import
**Steps:**
1. In CTT, create tasks with is_routine=true and frequency set
2. Navigate to Lifestyle Dezider
3. Tap "Import" in header
4. Verify imported routines
**Expected:**
- CTT routine tasks become Lifestyle routines
- Frequency, life area, priority mapped correctly
- source_ctt_task_id linked
- Can be used in lifestyle assessments

### TC-23.5: Lifestyle → PRR Flow
**Navigation:** Create routines → Start Lifestyle Assessment → Complete PRR
**Steps:**
1. Create 5+ active routines in Lifestyle Dezider
2. Tap "Daily" assessment button
3. PRR decision created → Go through Steps 1-10
4. Complete assessment with LMH/Custom % ratings
5. View final effectiveness score
**Expected:**
- PRR decision has routines as factors
- Single option "My Lifestyle"
- Full 10-step flow works
- Final worth_percentage = effectiveness score
- Assessment appears in Lifestyle Assessments tab
- Analytics update with new data point

### TC-23.6: GEM → PRR Flow
**Navigation:** Create GEM Goal → Launch Decision
**Steps:**
1. Create a goal in GEM (e.g., "Get Promoted")
2. Open the goal
3. Tap "Start Decision" in Launch Actions
4. PRR flow begins
**Expected:**
- New PRR decision created with goal context
- Decision title related to goal
- Goal linked to the new decision
- Full PRR flow available

### TC-23.7: Solution Matrix → TEPFI Flow
**Navigation:** Create Solution Matrix → TEPFI Import
**Steps:**
1. Create a Solution Matrix with Self/Micro/Macro layer data
2. Navigate to TEPFI
3. Use import API: POST /api/tepfi/import-from-matrix/{matrix_id}
**Expected:**
- TEPFI entry created from matrix data
- Self/Micro/Macro layers mapped to TEPFI layers
- Matrix sub-areas (time, people, finance, capacity, infrastructure) mapped to TEPFI dimensions
- Title: "From: [SMART Goal]"
- linked_solution_matrix_id set

### TC-23.8: CTT → Calendar Flow
**Navigation:** Create CTT tasks with deadlines → View Calendar
**Steps:**
1. Create 3 CTT tasks with different deadlines (today, next week, next month)
2. Navigate to Calendar View
**Expected:**
- All 3 tasks appear in timeline grouped by their deadline dates
- Today's task under today's date (blue highlight)
- Next week's task under that date
- Dates sorted chronologically
- Can export each to Google Calendar

### TC-23.9: CTT → Google Calendar
**Navigation:** CTT task with deadline → Calendar export
**Steps:**
1. Find a CTT task with deadline and time set
2. Tap the blue calendar button on the task card
3. Google Calendar opens in browser
**Expected:**
- Google Calendar new event page with:
  - Title = Task name
  - Date/time = From task deadline/time
  - Description = Priority, Life Area, Project, Remarks
- Event can be saved to user's Google Calendar

### TC-23.10: Full Lifecycle Integration
**Navigation:** GEM Goal → PRR Decision → Action Items → CTT → Calendar + Lifestyle → Assessment
**Steps:**
1. **GEM**: Create goal "Improve Health" (Life Area: Health, Type: Need)
2. **GEM → PRR**: Launch Decision from goal → Complete full 10-step PRR flow
3. **PRR → CTT**: In Step 10, define action items (e.g., "Join gym", "Start diet plan")
4. **CTT Import**: Navigate to CTT → Import → Verify action items imported with "PRR Decision" badge
5. **CTT**: Set deadlines on imported tasks. Mark "Join gym" as routine (daily frequency)
6. **CTT → Calendar**: Open Calendar View → Verify tasks with deadlines appear in timeline
7. **CTT → Google Calendar**: Export a task to Google Calendar → Verify event created
8. **CTT → Lifestyle**: Navigate to Lifestyle → Import from CTT → "Join gym" routine imported
9. **Lifestyle**: Add more routines manually (e.g., "Morning jog", "Meditation")
10. **Lifestyle → Assessment**: Start Daily Assessment → Complete PRR flow with routines as factors → Get effectiveness score
11. **Verify**: Check GEM goal → Should show linked decision. Check Lifestyle Analytics → Should show new data point
**Expected:**
- Complete end-to-end flow across ALL modules
- Data flows correctly: GEM → PRR → CTT → Calendar + Lifestyle → Assessment
- No data loss between modules
- All source tracking maintained (badges, links)
- Analytics reflect the complete journey
- This validates the entire system integration

---

## REFERENCE: EFFECTIVENESS COLOR LEGEND

| Score Range | Color | Label | Hex Code |
|-------------|-------|-------|----------|
| 80%+ | 🟢 Green | Excellent | #10B981 |
| 60-79% | 🔵 Blue | Good | #3B82F6 |
| 40-59% | 🟡 Yellow | Fair | #F59E0B |
| <40% | 🔴 Red | Needs Attention | #EF4444 |

## REFERENCE: PRIORITY COLOR LEGEND

| Priority | Color | Hex Code |
|----------|-------|----------|
| Critical | 🔴 Red | #EF4444 |
| High | 🟡 Amber | #F59E0B |
| Medium | 🔵 Blue | #3B82F6 |
| Low | ⚪ Gray | #6B7280 |

## REFERENCE: FREQUENCY COLOR LEGEND

| Frequency | Color | Hex Code |
|-----------|-------|----------|
| Hourly | 🔴 Red | #EF4444 |
| Daily | 🔵 Blue | #3B82F6 |
| Weekly | 🟢 Green | #10B981 |
| Fortnightly | 🟡 Amber | #F59E0B |
| Monthly | 🟣 Purple | #8B5CF6 |

## REFERENCE: ORG ROLE HIERARCHY

```
org_super_admin (Level 3) — Can manage ALL roles
    └── org_co_admin (Level 2) — Can manage org_admin & org_member
        └── org_admin (Level 1) — Can manage org_member only
            └── org_member (Level 0) — No management access
```

---

**Total Test Cases: 178**
**Modules Covered: 23**
**End of UAT Document**

*Generated for View Dezider — Multi-user Decision Making App with PRR Framework*
