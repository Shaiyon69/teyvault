# Teyvault layout redesign

Source mockup: `teyvault_redesign.png` (1280 px wide, PC, 8 screens, wireframe only: labels mark what goes in each box).
This file explains the concept behind the mockup and how the same layout works on tablets and phones.

## Concept

One shell, one grammar for every section:

1. **Shell**: a dark sidebar plus a slightly lighter rounded content panel.
2. **Head card**: every section opens with a full-width card holding a big title and a subtitle (what the section is, plus context such as UID or last sync). Optional companion cards sit to its right.
3. **Stat row**: small equal cards with an UPPERCASE label and one big number.
4. **Body cards**: large cards with an UPPERCASE label, holding the section's main content.
5. **Grids**: catalogue screens (Characters, Wiki) have search + filter pills, then a subtitle and a dense tile grid.

The design separates layers by surface color only: no borders, no shadows, no gradients. Each layer is one step lighter than the one under it.

## Tokens

### Colors (dark)

| Token | Hex | Used for |
|---|---|---|
| `bg` | `#0d1117` | window, sidebar |
| `panel` | `#161b22` | rounded content panel |
| `card` | `#21262d` | cards, grid tiles |
| `raised` | `#30363d` | tiles inside cards (banners), search field, filter pills |
| `muted` | `#8b949e` | secondary text, subtitles |
| text | `#ffffff` | titles, labels, values |

Accent colors (gold, element colors, rarity, pity colors) stay as they are today. They are the only saturated colors on screen, so they stand out on the grey surfaces.

### Shape and spacing (measured at 1280 px)

| Thing | Value |
|---|---|
| Sidebar width | ~276 px |
| Content panel | starts ~46 px below the window top, radius 24 on the top-left corner, bleeds off the right/bottom edges |
| Panel padding | ~29 px |
| Gap between cards | 16 px |
| Card radius | 14 |
| Card inner padding | ~21 px |
| Head card height | ~98 px |
| Stat card height | ~80–100 px |
| Logo | 80 px square, radius 20 |
| Pills / search | 34 px tall, fully rounded, `raised` fill, thin `bg`-colored outline |
| Grid tile | portrait, ~4:5, radius 10, 8 px gap |

### Type (Inter)

| Role | Size | Style |
|---|---|---|
| Head title | 26 | regular, UPPERCASE |
| Head subtitle | 16 | regular |
| Section title ("MAP EXPLORATION") | 24 | regular, UPPERCASE |
| Card label | 12 | regular, UPPERCASE |
| Grid subtitle ("Sub Title") | 16 | regular |
| Stat value | 24–28 | semibold |

## Shell

```
PC (>= 1200 dp)                         Narrow PC / tablet (< 1200 dp)
+--------+----------------------------+ +----+------------------------+
| [logo] |  panel                     | | [] |  panel                 |
| TEYV.  |  +-----------------------+ | | ○  |  head card ...         |
| DATE   |  | HEAD TITLE            | | | ○  |                        |
|        |  | Sub title             | | | ○  |                        |
| nav    |  +-----------------------+ | |    |                        |
| items  |  ...                       | |    |                        |
|        |                            | |    |                        |
| status |                            | |    |                        |
+--------+----------------------------+ +----+------------------------+
```

- **Sidebar**: logo + "TEYVAULT" + today's date on top; nav items (Dashboard, Events, Wishes, World, Characters, Wiki, Account, Settings) below. The mockup leaves the nav list blank, so the existing nav items, sign-in status and "Made by" watermark go there. The window title bar keeps the drag area and traffic lights.
- **Tablet**: same panel, sidebar shrinks to the icon rail (`wide_rail` / `fit_rail`).

### Phone (< 600 dp)

```
+---------------------------+
| [logo] Dashboard   (●) ⚙  |  app bar: section name, sign-in chip, settings gear
+---------------------------+
|  +---------------------+  |
|  | HEAD TITLE          |  |  head card stays, compact (title 20, subtitle 14)
|  | Sub title           |  |
|  +---------------------+  |
|  +--------+ +--------+    |
|  | STAT   | | STAT   |    |  stat cards: 2 per row
|  +--------+ +--------+    |
|  +---------------------+  |
|  | BODY CARD           |  |  body cards: full width, stacked
|  +---------------------+  |
+---------------------------+
| ⌂   ▦   ✦   ◎   ☺   ☰    |  bottom bar, icons only
+---------------------------+
```

- Background `bg`; no separate panel on phones (the whole page is the panel, color `panel`), cards keep the `card` color.
- Page padding 16, card gap 12, card radius 14.
- Bottom bar: Dashboard, Events, Wishes, World, Characters, Wiki. Account opens from the sign-in chip, Settings from the gear (same as today).
- The head card's companion cards (Wishes sync, World live map) drop below the head card as full-width cards.
- Everything scrolls in one page scroll. Cards that scroll internally on PC (calendar, rewards) get a fixed height or expand fully on phones.

## Screens

Each screen lists the PC layout, then the phone stack order.

### 1. Dashboard

```
+------------------------------------------------+
| HEAD TITLE / Sub title                         |
+-----------+-----------+-----------+------------+
| PRIMOGEMS | stat      | stat      | stat       |
+-----------+-----------+------------------------+
| CHECK IN TODAY        | DAILY REWARDS          |
|                       | (tall: reward calendar)|
+-----------------------+                        |
| REDEEMING CODES       |                        |
+-----------------------+------------------------+
```

- Head: greeting / account, date.
- Stat row (4): Primogems, then resin, commissions, expeditions (what the dashboard already shows; the mockup labels only the first).
- Left column: "Check in today" (status + button), then "Redeeming codes" (input + redeem).
- Right column: "Daily rewards" calendar fills the full height and scrolls inside the card. The PC dashboard still never scrolls as a page.
- **Phone**: head, stats 2×2, check in, daily rewards (fixed height, scrolls inside), redeem codes.

### 2. Events

```
+------------------------------------------------+
| HEAD TITLE / Sub title                         |
+-----------------------------------+------------+
| EVENT TIMELINE CALENDAR           | EVENT      |
|                                   | DETAILS    |
+-----------------------------------+------------+
```

- Left (~3/4): timeline chart.
- Right (~1/4): details of the event tapped on the timeline (name, dates, time left, rewards). Shows the next ending event until something is tapped.
- **Phone**: head, timeline (scrolls sideways), then event details opens as a bottom sheet when an event is tapped.

### 3. Wishes

```
+-------------------------------------+----------+
| HEAD TITLE / Sub title              | SYNC AND |
|                                     | IMP/EXP  |
+-------------------------------------+----------+
| CURRENT BANNER                                 |
|  +------------+ +------------+ +------------+  |
|  | banner     | | banner     | | banner     |  |
|  +------------+ +------------+ +------------+  |
+---------------+----------------+---------------+
| LIFETIME PULLS| PRIMOGEMS SPENT| 50/50 RECORD  |
+---------------+----------------+---------------+
| CHARACTER EVENTS                               |
| (pity meters, pull history per pool)           |
+------------------------------------------------+
```

- Companion card: sync from game, import/export, phone sync (buttons or a menu).
- Current banner: one `raised` tile per active banner (character 1, character 2, weapon).
- Stat row (3): lifetime pulls, primogems spent, 50/50 record.
- Pool cards below, one per pool (Character events, then Weapon, Standard, Chronicled).
- **Phone**: head, sync card, banners scroll sideways (one tile ≈ 85% width), stats in 3 small cards on one row (or 2 + 1), pool cards.

### 4. World

```
+-------------------------------------+----------+
| HEAD TITLE / Sub title              | LIVE MAP |
+--------+---------+---------+--------+          |
| DAYS   | ACHIEVE | SPIRAL  | OCULI  |          |
| ACTIVE | MENTS   | ABYSS   |        |          |
+--------+-+-------+----+----+--------+          |
| WAYPOINTS | DOMAINS   | CHESTS OPENED|          |
+-----------+-----------+--------------+----------+
MAP EXPLORATION
+--------------+ +--------------+ +--------------+
| region       | | region       | | region       |
+--------------+ +--------------+ +--------------+
  ... 3 per row
```

- Live map: tall companion card next to head + both stat rows. Holds a map preview image and buttons for HoYoLAB interactive map / Teyvat GPS (embedding only works on mobile, where `flet_webview` exists).
- Stat rows: 4 then 3.
- "Map exploration" is a section title outside any card, followed by one card per region (icon, name, exploration %, progress bar), 3 per row.
- **Phone**: head, stats 2 per row (7 → 4 rows), live map card (button row), map exploration 1 per row.

### 5. Characters

```
+------------------------------------------------+
| HEAD TITLE / Sub title                         |
+------------------------------------------------+
( SEARCH                                          )
(ELEMENTS)(WEAPON)(RARITY)(META TIER)(META ROLE)(SORT)(GROUP BY)
Sub title  (group name, e.g. "Pyro" or "5★")
[ ][ ][ ][ ][ ][ ][ ][ ][ ]
[ ][ ][ ][ ][ ][ ][ ][ ][ ]
```

- Search and filter pills are always visible (no Filters button on PC). Each pill opens its dropdown menu; an active filter shows its value in the pill and gets the accent color.
- "Group by" splits the grid into groups; each group gets a subtitle. No grouping = one subtitle with the count.
- Grid: 9 portrait tiles per row at 1280 px (portrait, name, level/constellation).
- **Phone**: search full width, pills scroll sideways in one row, grid 3 per row.

### 6. Wiki

```
+------------------------------------------------+
| HEAD TITLE / Sub title                         |
+------------------------------------------------+
( CATEGORY                                        )
( SEARCH                                          )
(SORT)(ELEMENTS)(REGION)(RARITY)(WEAPON)(ASCENSION STAT)
Sub title
[ ][ ][ ][ ][ ][ ][ ][ ][ ]
```

- Same as Characters, with an extra full-width bar above search: the category picker (characters, weapons, artifacts, collectibles, achievements, ...). On PC it can be a row of segmented pills; on phone a full-width dropdown.
- Filter pills change with the category (only filters that apply are shown).
- Infinite scroll stays (`WIKI_PAGE`).
- **Phone**: category, search, pills scroll sideways, grid 3 per row.

### 7. Account

```
+------------------------------------------------+
| HEAD TITLE / Sub title                         |
+------------------------------------------------+
| SIGN IN WITH HOYOLAB                           |
+------------------------------------------------+
| ACCOUNT 1                                      |
| (game roles, default UID, sign out)            |
+------------------------------------------------+
```

- Full-width stacked cards. Sign-in card is the action; one card per signed-in account / game role below it.
- **Phone**: identical, already single column.

### 8. Settings

- Head card, then full-width stacked cards (one per group: Appearance, Behaviour, Phone sync, Data, About). The mockup leaves them unlabelled.
- **Phone**: identical.

## Mapping to code (`teyvat/gui/`)

| Mockup | Code |
|---|---|
| Colors | new style in `STYLES` filling `STYLE` via `use_style()` (`card_bg`, page bg, radius 14, no border/blur/gradient) |
| Head card | `hero()` |
| Body / stat cards | `card()` / `tile()` |
| Grid | `tile_grid()` |
| Search + pills | `filter_bar()` (PC: always open; phone: sideways scroll) |
| Loading | `skeleton()` uses the same card shapes, so loading looks like the mockup |
| Layout switch | existing `phone` / `wide_rail` logic |

## Open points

- Light theme: the mockup is dark only. Plan: GitHub-light equivalents (`#ffffff` bg, `#f6f8fa` panel, `#eaeef2` card, `#d0d7de` raised, `#57606a` muted).
- Sidebar nav styling is not shown: use plain rows (icon + label), the selected one gets a `card`-colored rounded background.
- Dashboard stat cards 2–4 are unlabelled in the mockup.
