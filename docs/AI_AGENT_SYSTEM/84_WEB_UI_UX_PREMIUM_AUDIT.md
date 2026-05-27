# Web UI/UX Premium Design Audit

**Date:** 2026-05-26
**Branch:** feature/packages-update
**Pages audited:** 10

## 1. Executive Score

| Area | Score /10 |
|------|-----------|
| Overall UI | 6.1 |
| CRM UX | 6.5 |
| Agent Control Center | 5.0 |
| Security UI | 6.0 |
| Campaign UI | N/A (no dedicated page yet) |
| Mobile | 5.5 |
| Visual consistency | 4.5 |

## 2. Page-by-Page Audit

### /dashboard (dashboard.html) — 250 lines
- **Status:** Functional, visually solid
- **Strengths:** 5 KPI cards, pipeline funnel, score distribution, revenue summary, recommendations
- **Problems:** All inline styles (Tailwind loaded but unused), no charts (CSS div bars), no date range selector, no trend indicators, no drill-down links
- **Priority:** MEDIUM
- **Fix:** Convert to Tailwind, add period selector, link KPIs to detail pages

### /leads (leads.html) — 246 lines
- **Status:** Functional with pagination
- **Strengths:** Desktop table + mobile card view, empty states, pagination
- **Problems:** Search/filter buttons disabled (decorative), rows not clickable, column sort missing, stage badge logic duplicated between desktop/mobile
- **Priority:** MEDIUM
- **Fix:** Enable search, make rows clickable, extract badge component

### /pipeline (pipeline.html) — 175 lines
- **Status:** Cleanest visual design
- **Strengths:** 5-column kanban, color-coded stages, lead cards with score/area/phone
- **Problems:** Cards not clickable, no drag-drop (read-only not communicated clearly), horizontal scroll on mobile
- **Priority:** LOW
- **Fix:** Make cards linkable, add "read-only" indicator, stack columns on mobile

### /analytics (analytics.html) — 290 lines
- **Status:** Feature-rich
- **Strengths:** Period selector tabs, 5 KPI cards, source/funnel/score/revenue sections
- **Problems:** No real charts (CSS bars only), period selector reloads page, revenue no currency format, duplicates dashboard content
- **Priority:** MEDIUM
- **Fix:** Add chart library or better CSS bars, AJAX period switch

### /agent (agent.html) — 540 lines (LARGEST)
- **Status:** Functionally rich but rough UX
- **Strengths:** Status header, timeline, presets, settings table, approval queue, observation reports
- **Problems:** Browser confirm()/prompt() for critical actions, language mix (Uz/En), no auto-refresh, alert() for help/rollback, massive inline JS, no mobile support
- **Priority:** HIGH
- **Fix:** Replace browser dialogs with modals, consistent language, auto-refresh, responsive layout

### /crm (crm_contacts.html) — 377 lines
- **Status:** Most feature-rich page
- **Strengths:** Live polling 15s, 6 alert badges, browser notifications, sound alerts, keyboard shortcuts, quick filters, hide stopped toggle
- **Problems:** No server-side search, table columns bare (no hover/sort), small tap targets on mobile, no pagination indicator
- **Priority:** MEDIUM
- **Fix:** Add server search, column headers sortable, larger touch targets

### /crm/{id} (crm_contact_detail.html) — 161 lines (SMALLEST)
- **Status:** Weakest page — needs most work
- **Strengths:** Profile card, message timeline, operator reply section, operator checklist, SLA badge placeholder
- **Problems:** Fixed 300px grid (breaks on mobile), SLA/nextAction elements never populated (dead UI), alert('Saqlandi') for notes, tags section placeholder only, no back button, messages show raw direction/sender_type strings
- **Priority:** HIGH
- **Fix:** Responsive grid, populate SLA via JS, human-readable labels, back nav, real tag management

### /admin/security (security.html) — 136 lines
- **Status:** Cleanest code (pure Tailwind)
- **Strengths:** Responsive grid, severity badges, 7 sections, conditional empty states
- **Problems:** Not in sidebar (unreachable via nav), no active_page set, no time-period selector, no refresh
- **Priority:** MEDIUM
- **Fix:** Add to sidebar, set active_page, add period filter

### /login (login.html) — 52 lines
- **Status:** Functional but flawed
- **Strengths:** Clean Tailwind form, error handling, session-disabled notice
- **Problems:** Renders with full sidebar (auth boundary leak), no logo/branding, hidden labels (accessibility)
- **Priority:** HIGH
- **Fix:** Separate layout without sidebar, add logo, visible labels

### Base layout (base.html) — 323 lines
- **Status:** Solid foundation
- **Strengths:** Mobile sidebar with hamburger, active menu state, Inter font, sticky topbar
- **Problems:** HTML entity icons (inconsistent rendering), missing Security/Campaigns sidebar links, topbar title fallback incomplete (Agent/CRM fall to generic), no user identity/logout in topbar, no breadcrumbs
- **Priority:** HIGH
- **Fix:** SVG icons, complete sidebar, user avatar/logout, breadcrumbs

## 3. Top 20 Design Issues

| # | Issue | Page | Severity | Impact | Fix |
|---|-------|------|----------|--------|-----|
| 1 | Login shows sidebar (auth leak) | login | HIGH | Security/trust | Separate layout |
| 2 | Security page unreachable | security | HIGH | Feature invisible | Add sidebar link |
| 3 | Contact detail not responsive | crm detail | HIGH | Mobile broken | CSS grid fix |
| 4 | Dead SLA/nextAction elements | crm detail | HIGH | Misleading UI | Populate via API |
| 5 | Browser dialogs for critical actions | agent | HIGH | Poor UX | Modal components |
| 6 | Inline styles on 8/10 pages | all | MEDIUM | Unmaintainable | Tailwind migration |
| 7 | HTML entity icons | base | MEDIUM | Inconsistent render | SVG icon set |
| 8 | No breadcrumbs anywhere | all | MEDIUM | Navigation loss | Add breadcrumb component |
| 9 | No user identity/logout in header | base | MEDIUM | No session awareness | Add user menu |
| 10 | Missing sidebar links (Security, Campaigns) | base | MEDIUM | Features hidden | Update sidebar |
| 11 | Topbar title fallback incomplete | base | LOW | Wrong title on Agent/CRM | Fix if chain |
| 12 | Disabled search/filter on leads | leads | MEDIUM | Misleading | Enable or remove |
| 13 | No chart library | dashboard/analytics | MEDIUM | Data viz weak | Add lightweight charts |
| 14 | Language mix (Uz+En) in agent | agent | LOW | Inconsistency | Standardize to Uzbek |
| 15 | alert() for note save success | crm detail | LOW | Poor UX | Toast notification |
| 16 | Tags section placeholder only | crm detail | LOW | Incomplete feature | Wire tag API |
| 17 | No loading spinners | all | LOW | No feedback | Add skeleton/spinner |
| 18 | Pipeline cards not clickable | pipeline | LOW | No drill-down | Add link |
| 19 | No dark mode | all | LOW | Modern expectation | Future phase |
| 20 | Table columns not sortable | crm/leads | LOW | Operator friction | Client-side sort |

## 4. Recommended Design System

### Colors
- Primary: Indigo 600 (#4f46e5) — buttons, links, active states
- Background: Slate 50 (#f8fafc) — page background
- Cards: White (#fff) with border slate 200, shadow-sm, radius-lg
- Danger: Red 600, Warning: Amber 500, Success: Green 600, Info: Blue 500

### Typography
- Font: Inter (already loaded)
- H1: 24px/600, H2: 18px/600, H3: 15px/600
- Body: 14px/400, Small: 12px/400, Micro: 11px/400

### Components
- Card: bg-white rounded-xl shadow-sm border p-4/p-6
- Badge: px-2 py-0.5 rounded-full text-xs font-medium
- Button primary: bg-indigo-600 text-white px-4 py-2 rounded-lg
- Button danger: bg-red-600 text-white (with confirm modal)
- Button secondary: border border-slate-300 bg-white
- Table: divide-y divide-slate-200, hover:bg-slate-50

### Status Badge Colors
- critical/hot: bg-red-100 text-red-800
- danger/overdue: bg-orange-100 text-orange-800
- warning/due_soon: bg-amber-100 text-amber-800
- success/won: bg-green-100 text-green-800
- info/new: bg-blue-100 text-blue-800
- neutral/viewer: bg-slate-100 text-slate-600

## 5. Redesign Roadmap

| Step | Scope | Effort | Impact |
|------|-------|--------|--------|
| BX | Design System Foundation (Tailwind components, shared partials) | Medium | Foundation for all |
| BY | Base Layout + Sidebar/Header Redesign (icons, nav, user menu) | Medium | Every page improves |
| BZ | CRM Inbox Premium (responsive table, better filters, UX) | Medium | Operator daily use |
| CA | Contact Detail Timeline (responsive, live SLA, tags, reply UX) | High | Most complex view |
| CB | Agent Control Center (modals, auto-refresh, responsive) | Medium | Admin critical |
| CC | Campaign/Security/Admin Polish | Low | Final consistency |

## 6. Do-Not-Break List

- No behavior changes
- No send enables
- No flag changes
- No route breaking
- All 3979 tests must pass
- Existing JS polling/notification must survive
- Keyboard shortcuts must survive

## 7. Quick Wins (no redesign needed)

1. Add Security + Campaigns to sidebar in base.html
2. Fix topbar title fallback for Agent/CRM pages
3. Set active_page on security.html
4. Add back link on crm_contact_detail.html
5. Fix login.html to not extend base.html (use minimal layout)

## 8. Final Recommendation

**Start with:** Step BX (Design System Foundation) — create shared Tailwind partials/components that all pages can adopt incrementally. Then Step BY (Base Layout) fixes the sidebar/header issues that affect every page. After that, prioritize Step BZ (CRM Inbox) and Step CA (Contact Detail) since operators use those daily.

**Estimated total redesign:** 6 steps (BX through CC)
