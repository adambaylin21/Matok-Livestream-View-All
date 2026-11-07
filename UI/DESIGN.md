---
name: Broadcast Terminal System
colors:
  surface: '#faf8ff'
  surface-dim: '#d2d9f4'
  surface-bright: '#faf8ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3ff'
  surface-container: '#eaedff'
  surface-container-high: '#e2e7ff'
  surface-container-highest: '#dae2fd'
  on-surface: '#131b2e'
  on-surface-variant: '#434655'
  inverse-surface: '#283044'
  inverse-on-surface: '#eef0ff'
  outline: '#737686'
  outline-variant: '#c3c6d7'
  surface-tint: '#0053db'
  primary: '#004ac6'
  on-primary: '#ffffff'
  primary-container: '#2563eb'
  on-primary-container: '#eeefff'
  inverse-primary: '#b4c5ff'
  secondary: '#b61722'
  on-secondary: '#ffffff'
  secondary-container: '#da3437'
  on-secondary-container: '#fffbff'
  tertiary: '#005e6e'
  on-tertiary: '#ffffff'
  tertiary-container: '#00788c'
  on-tertiary-container: '#d7f6ff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dbe1ff'
  primary-fixed-dim: '#b4c5ff'
  on-primary-fixed: '#00174b'
  on-primary-fixed-variant: '#003ea8'
  secondary-fixed: '#ffdad7'
  secondary-fixed-dim: '#ffb3ad'
  on-secondary-fixed: '#410004'
  on-secondary-fixed-variant: '#930013'
  tertiary-fixed: '#acedff'
  tertiary-fixed-dim: '#4cd7f6'
  on-tertiary-fixed: '#001f26'
  on-tertiary-fixed-variant: '#004e5c'
  background: '#faf8ff'
  on-background: '#131b2e'
  surface-variant: '#dae2fd'
typography:
  headline-xl:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 38px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.02em
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-md:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  label-lg:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-md:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: Space Grotesk
    fontSize: 10px
    fontWeight: '700'
    lineHeight: 12px
    letterSpacing: 0.08em
  telemetry-num:
    fontFamily: Geist
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 18px
    letterSpacing: -0.02em
spacing:
  gutter: 0.5rem
  gutter-md: 0.75rem
  margin: 0.75rem
  margin-md: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1rem
  space-xl: 1.5rem
---

## Brand & Style

This design system delivers a real-time command center interface optimized for high-density, multi-stream monitoring on mobile and compact touch displays. Built upon an experimental broadcast-terminal aesthetic, the system rejects soft consumer tropes in favor of structural precision, zero-radius geometry, and razor-sharp typographic hierarchy.

### Personality & Tone
- **Mission-Critical Precision:** Every pixel, edge, and label exists to communicate instantaneous operational status without visual hesitation.
- **Instrumental Utilitarianism:** Form factors mirror broadcast rack-mount monitors and master control switchers—austere, calibrated, and unapologetically engineered.
- **Controlled High Energy:** Neutral, light-mode work surfaces set a disciplined baseline, punctuated by vivid platform signatures and high-urgency status signals.

### Target Audience & Psychological Intent
Crafted for multi-channel live producers, e-commerce studio directors, and live ops engineers who simultaneously supervise concurrent video streams across diverse commercial channels (TikTok, Shopee, native RTMP). The interface instills uncompromised focus, fast anomaly detection, and rapid triage capability under real-time operational stress.

## Colors

The palette establishes an ultra-clean day-mode control room. Contrast is prioritized through strict surface-to-ink ratios, framing high-chroma streaming badges against crisp architectural grounds.

### Foundation & Surfaces
- **Canvas Base:** `#F8FAFC` (Slate 50) provides a low-strain, glare-reduced workspace foundation.
- **Surface Crisp White:** `#FFFFFF` frames active video viewports, operational cards, and modal control drawers.
- **Surface Inactive / Recessed:** `#F1F5F9` (Slate 100) indicates muted feeds, inactive tracks, and telemetry troughs.
- **Structural Partition Borders:** `#E2E8F0` (Slate 200) serves as the primary structural boundary rule, ensuring crisp element segregation.

### Typography & Ink
- **Display & Headings:** `#0F172A` (Slate 900) delivers deep, uncompromised contrast for vital broadcast metrics and channel handles.
- **Body & Telemetry Data:** `#334155` (Slate 700) maintains crisp legibility for secondary bitrates, frame dropped stats, and timestamps.
- **Muted & Metadata Labels:** `#64748B` (Slate 500) supports peripheral captions, channel indexes, and technical specs.

### Functional & Signal Accents
- **Command Primary:** `#2563EB` (Cobalt Blue) marks selected feeds, active switcher routings, primary triggers, and focused state borders.
- **Signal Red / Live Beacon:** `#EF4444` (Vibrant Signal Red) is reserved strictly for active on-air states, critical stream drops, and audio clipping alerts.
- **Platform Marketplace Orange:** `#F97316` designates Shopee Live sync status and product inventory telemetry.
- **Platform Network Cyan:** `#06B6D4` designates TikTok Live feed ingestion and real-time interaction velocity metrics.
- **Operational Green:** `#10B981` signals stable bitrate, synchronous audio-video lock, and healthy CDN connections.

## Typography

The typographic hierarchy pairs the mechanical, technical character of **Space Grotesk** for primary headings, callouts, and system codes with the austere, razor-sharp density of **Geist** for dense analytical data and functional copy.

### Architectural Rules
- **Monospace Alignment on Numerics:** When rendering telemetry values (bitrate, FPS, dropped frame percentages, concurrent viewer tallies), numeric figures must employ tabular numbering (`font-variant-numeric: tabular-nums`) to prevent layout shift during high-frequency data refresh.
- **Caps for Status & Channel Flags:** All real-time telemetry markers, operational indicators (`LIVE`, `OFFLINE`, `WARN`, `AUDIO PEAK`), and platform designations must use uppercase rendering in `label-sm` or `label-md` to enforce immediate recognition.
- **Tight Headings:** `Space Grotesk` uses tight tracking to reinforce the physical, engineered aesthetic of precision instrument switchboards.

## Layout & Spacing

To maximize usable screen surface for live video pipelines, the spatial architecture adopts a high-density, grid-locked distribution model.

### Spatial Grid System
- **Mobile Grid (Primary Form Factor):** 4-column fluid matrix structured around an 8px base grid, collapsing to 4px subdivisions for stream controls and VU meters.
- **Split Screen Multi-View:** Dual-stream views divide viewport vertically (`1x2`), quad-stream views lock to a `2x2` matrix with strict `0.5rem` (`8px`) separation rules.
- **Margins & Safe Zones:** Canvas margins default to `0.75rem` (`12px`) on mobile viewports to preserve maximum viewport ratio for stream feeds while accommodating thumb-accessible edge triggers.

### Reflow & Breakpoints
- **Mobile Compact (< 380px):** Single-column prioritized feed with horizontal mini-ticker rail for secondary streams.
- **Mobile Standard (381px - 440px):** 2-column quad-grid default. Aspect ratios locked strictly to 9:16 or 1:1 view window frames.
- **Tablet / Expanded Switcher (441px - 768px):** Multi-tile matrix (up to 6 feeds simultaneous) with dedicated bottom telemetry drawer.

## Elevation & Depth

This design system deliberately excludes ambient blurs, frosted glass, and soft diffused drop shadows. Spatial depth is expressed strictly through structural outlines, border prioritization, and tonal layering.

### Depth Archetype
- **Zero-Shadow Construction:** No visual element utilizes box shadows for ambient elevation. The interface is purposefully planar to maintain broadcast monitor clarity under varying mobile ambient light conditions.
- **Layer 0 (Canvas Backplane):** `#F8FAFC` slate canvas.
- **Layer 1 (Stream Enclosures & Panels):** Solid `#FFFFFF` surfaces defined by a crisp `1px solid #E2E8F0` border.
- **Layer 2 (Selected Feed Focus):** Active monitored feed indicated by replacing the neutral border with an emphatic `2px solid #2563EB` structural highlight.
- **Layer 3 (Overlays & Heads-Up Displays):** Live telemetry tags, audio meters, and platform pills float over live video frames on semi-opaque high-density grounds (`rgba(15, 23, 42, 0.88)` or `#FFFFFF` with `1px` high-contrast stroke).
- **Z-Index Layering:** Modals and bottom switcher sheets clip to the viewport boundary with a hard `2px solid #0F172A` perimeter rule rather than feathered shadow masks.

## Shapes

The shape system is strictly non-rounded (`0px` corner radius). Every container, thumbnail, badge, interactive button, input field, and visual meter terminates at clean 90-degree right angles.

### Shape Identity Directives
- **Zero-Bevel Rigor:** Curves are eliminated across all UI surfaces. Feeds, badges, toggles, and buttons share razor-sharp perpendicular corners.
- **Dividers & Wirelines:** Visual grouping is achieved via single-pixel hairline gridlines (`#E2E8F0`) rather than pill enclosures or rounded nesting blocks.
- **Operational Data Boxes:** Telemetry counters, audio channel meters, and platform labels are rendered inside rigid, rectangular blocks, matching physical rack-mount production consoles.

## Components

### Buttons
- **Primary Operational Button:** Solid `#2563EB`, text `#FFFFFF`, 0px border radius, font `Space Grotesk` (weight 600, uppercase). Height: 40px for mobile touch target. Active state drops to `#1D4ED8`.
- **Destructive / Take-Down Button:** Solid `#EF4444`, text `#FFFFFF`, zero radius. Used exclusively for emergency stream termination or unpublishing.
- **Secondary Wire Button:** Background `#FFFFFF`, border `1px solid #E2E8F0`, text `#0F172A`. Hover/pressed state shifts background to `#F1F5F9`.
- **Feed Quick Switcher Button:** Fixed height 32px, flat `#F1F5F9`, border `1px solid #E2E8F0`, zero radius, label in `label-sm`.

### Chips & Live Badges
- **Universal Live Status Badge:** Solid `#EF4444`, text `#FFFFFF`, font `Space Grotesk` bold uppercase (`10px`), height 20px, horizontal padding `6px`. Paired with a pulsating 4px square beacon indicator (never a rounded dot).
- **TikTok Platform Tag:** Solid `#06B6D4`, text `#FFFFFF`, uppercase, zero radius, padding 2px 6px.
- **Shopee Platform Tag:** Solid `#F97316`, text `#FFFFFF`, uppercase, zero radius, padding 2px 6px.
- **Metric Chips (Bitrate/FPS):** Background `rgba(15, 23, 42, 0.85)`, text `#F8FAFC`, font `Geist` tabular nums, border `1px solid rgba(255, 255, 255, 0.2)`.

### Stream Monitoring Cards
- **Structural Frame:** White background (`#FFFFFF`), `1px solid #E2E8F0` enclosure, containing top status ribbon, 9:16 or 16:9 video player viewport, and bottom telemetry readout.
- **Active State:** The currently focused audio/control channel gains an immediate outer `2px solid #2563EB` border.
- **Error / Offline State:** Frame receives a top hairline `2px solid #EF4444` and the video area displays a neutral `#F1F5F9` crosshatch calibration pattern.

### Input Fields & Switcher Controls
- **Search & Filter Inputs:** Background `#FFFFFF`, border `1px solid #E2E8F0`, text `#0F172A`, placeholder `#64748B`. Focused state applies crisp `1px solid #2563EB` with zero shadow.
- **Checkboxes & Segmented Selectors:** Square boxes (`16px x 16px`), sharp corners. Unchecked: `1px solid #CBD5E1`. Checked: Solid `#2563EB` with white geometric checkmark.

### Telemetry & Audio Peak Meters
- **VU Audio Meter:** Dual vertical or horizontal channel bars consisting of segmented sharp 2px blocks. Green (`#10B981`) up to -12dB, Orange (`#F97316`) to -3dB, and Signal Red (`#EF4444`) for digital clipping peaks.
- **Health Scroller:** Bottom-pinned mobile panel showing real-time dropped frames and CPU load in monospaced tabular typography.