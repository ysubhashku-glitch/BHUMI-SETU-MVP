# 04 - UI and Interaction Inventory

**Investigation Target:** Landeed Web App (`web.landeed.com`)  
**Audit Date:** October 24, 2026  
**Auditor:** Bhumi Setu Engineering Intelligence  

---

## 1. UI Architecture & Design System Fingerprints

From the captured DOM, CSS chunks (`e73af9e0c46b18ba.css`, `67dd0aa8d9129d89.css`), and accessibility trees, the frontend implementation details were derived:

* **Framework:** Next.js (App Router, Version 14/15, Build `0.75.7`) with React 18/19.
* **Styling Paradigm:** Tailwind CSS utility tokens paired with CSS modules for map and chat drawers.
* **Component Primitives:** Radix UI / headless accessible primitives (Combobox, Dialog, Accordion, Tabs, Radio Group).
* **Mapping Engine:** Mapbox GL JS (`api.mapbox.com`, custom token `pk.eyJ1IjoiYWNjdGZvcm1wYng...`).
* **Analytics & Session Tracking:** Google Tag Manager (`G-SYHQ19B7R8`), Amplitude (`3cb740c047...`), Microsoft Clarity (`qiti52cnnk`), Meta Pixel (`302912975600063`).

---

## 2. Screen-by-Screen Inventory

### Screen 1: Web App Home / Unified Intelligence (`/`)
* **Purpose:** Primary portal entry point combining conversational query, geographic map, and quick intent launchers.
* **Layout:**
  - Header: Landeed logo, global search bar (`Search documents, services and tools`), "Ask Terra" button, "Sign In" button.
  - Viewport Body: Split or togglable Map Viewport (Mapbox) and Conversational Card.
  - Tabs: `Chat` (Selected) and `Map`.
  - Input: Multiline textarea with prompt placeholders.
  - Attachment: "Sign in to attach" button for uploading deed scans or tax bills.
  - Engine Badge: `Terra engine: Terra 3.5 Beta`.
  - Intent Chips:
    1. `Know Before You Buy`
    2. `Explore the Map`
    3. `Get Certified Proof`
    4. `Ancestral Records`
  - Collapsible Sidebar Menu: Home, Services, Docs & Tools, Pulse, Orders, Vault, Support, Language Preferences.

### Screen 2: State Services Catalog (`/services/[state]`)
* **Purpose:** Browse standard and customized land legal, consultation, and survey services.
* **Layout:**
  - Breadcrumb: `Home > Services`.
  - State Switcher: Dropdown button (`Current state Bihar`).
  - View Toggle: Grid View vs. List View.
  - Filter Sidebar:
    - *Intent:* Buying a property, Selling a property, Raising money on it, Family land & inheritance, Something's wrong, Keeping an eye on it, Building on it.
    - *Type of Work:* Legal & advisory, Problem resolution, Construction & survey.
    - *Service Type:* Standard vs. Expedited.
    - *Property Type:* Agricultural vs. Non-agricultural.
  - Card Components:
    - Service Title (e.g. `Bihar Legal Opinion`)
    - Short Description (e.g. `Expert assessment of property title and legal status`)
    - Badge: `Standard`
    - Action: Card click navigates to `/products/[state]/[slug]`.

### Screen 3: State Documents & Tools Catalog (`/docs-tools/[state]`)
* **Purpose:** Direct access to government document retrieval tools for a specific state.
* **Observed Bihar Documents (5 Total):**
  1. `MVR Land Rates`: Minimum Value Register (circle rate for stamp duty calculation).
  2. `Plot Map`: Bhu-Naksha cadastral map viewer by Mauza and plot number.
  3. `Mutation Status`: Dakhil-Kharij petition tracker by case number / applicant name.
  4. `Jamabandi`: Register-II revenue ownership ledger.
  5. `Bihar CERSAI Mortgage Report`: Central Registry mortgage search for equitable liens.
* **Card Attributes:** Tags for `Instant` (automated source retrieval) vs. `Standard` (manual search/attorney review).

### Screen 4: Record Query Form (`/bihar/jamabandi`)
* **Purpose:** Structured parameters form to query Bihar Jamabandi Register-II records.
* **Form Elements:**
  - `Village/Division`: Mandatory dialog trigger (`uid=5_21`).
  - `Search By Dropdown`: Switch between `Name`, `Khata Number`, `Plot/Khesra Number`, `Jamabandi Number`.
  - `Input Field`: Context-sensitive text input with placeholder (e.g. `eg. Ram Kumar` or `eg. 142`).
  - `Action Buttons`: `Reset` (Secondary) and `Search` (Primary CTA).
* **Supporting Context:**
  - Sample Document Preview Image (`/images/preview/bh/bh_jamabandi.png`).
  - Use-cases badges: *Verify Land Ownership, Check Khata Details, Property Transactions, Legal Documentation*.
  - FAQ Accordion: Explanatory collapsible accordions for citizens.

---

## 3. Form Validation and Error Handling Behavior

1. **Client-Side Validation:**
   - Village/Division selection is mandatory. If user clicks `Search` without selecting village, input borders highlight with a red alert and the dialog auto-opens.
   - Numeric fields (Khata, Plot, Jamabandi) enforce integer digits and reject special characters.
2. **Ambiguity Handling:**
   - When multiple Jamabandis match a single name, results are presented with father's name, village, and Jamabandi ID to avoid incorrect automated identity merging.
3. **Empty States:**
   - Displays clear guidance: *"No record found matching Khesra [X] in Mauza [Y]. Try searching by Khata Number or verify spelling."*
