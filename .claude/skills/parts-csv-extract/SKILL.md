---
name: parts-csv-extract
description: Turn photos of electronic components (chip markings, labels, packaging, datasheets) into CSV rows for importing into the parts-library inventory. Use whenever the user shares photos of parts and asks to add them to their inventory / parts library / stock.
---

# Parts CSV extraction

You are filling in rows of a CSV file that will be imported into a personal
electronics inventory (parts-library). For each part shown in the photos,
output one CSV row using **exactly** this header and column order:

```
article_number,manufacturer,description,category,package,location,quantity,purchase_price,currency,datasheet_url,notes
```

Always include the header row, even for a single part. Output the CSV as
plain text (a fenced code block is fine) so it can be copy-pasted straight
into a `.csv` file — don't add commentary inside the CSV itself.

## Field-by-field guidance

- **article_number** — the manufacturer's part/order number as printed on the
  part, chip, or label (e.g. `LM358N`, `1N4148`, `RC0805FR-0710KL`). This is
  the key the importer uses to match against existing parts, so transcribe it
  exactly, including suffixes/package codes if they're part of the ordering
  code. If a marking is partially worn or ambiguous, give your best reading
  and flag the uncertainty in `notes`.
- **manufacturer** — the brand/maker if identifiable from a logo or marking
  (e.g. "Texas Instruments", "Vishay", "Würth Elektronik"). Leave blank if you
  can't tell.
- **description** — a short, human-readable description of what the part is
  (e.g. "Dual op-amp", "100 nF ceramic capacitor", "2.54mm 4-pin header"). the description should be useful. for example for opamps mention supply voltage, offset voltage, GBP... search the web if necessary
- **category** — a short category name for grouping. **Prefer reusing one of
  the user's existing categories below** (matching is case-insensitive). Use
  the most specific (sub)category that fits — e.g. an LM358 op-amp → `Opamps`,
  not `ICs`; a 100 nF ceramic cap → `Ceramic`, not `Capacitors`. Fall back to
  the top-level category when no subcategory fits (e.g. a generic logic-level
  resistor → `Resistors`). The current categories are:

  - **Capacitors** → Ceramic, Electrolytic
  - **Connectors**
  - **Diodes** → LEDs, TVS, Zener
  - **ICs** → ADCs, Comparators, DACs, Logic Gates, Microcontrollers, Opamps
  - **Inductors & Transformers** → Inductors
  - **Power** → Fuses, LDO, Switching regulators
  - **Resistors**
  - **Transistors** → BJTs, Fets

  If a part genuinely doesn't fit any of these, pick the most natural new name
  — the import preview will flag any category that doesn't exist yet so the
  user can map it or create it. Don't leave this blank if you can reasonably
  guess the part type.
- **package** — the footprint/package code if visible or inferable (e.g.
  `DIP-8`, `SOT-23`, `0805`, `TO-220`, `SOIC-8`).
- **location** — leave blank unless the user tells you where they're storing
  these parts (you can't see this from a photo).
- **quantity** — the number of **new units being added in this batch** (how
  many of this part are in the photo/being added now), not the total stock.
  The importer adds this to whatever is already in stock for a matching
  article number. Default to `1` if a count isn't otherwise obvious.
- **purchase_price** — only if the user tells you a price; otherwise leave
  blank. Use `.` as the decimal separator.
- **currency** — `EUR` by default if a price is given; otherwise leave blank.
- **datasheet_url** —find a datasheet! only include a URL if you're confident it's correct for
  this exact part; otherwise leave blank rather than guessing.
- **notes** — anything worth flagging: uncertain readings, "marking partially
  worn", condition, etc. Leave blank if there's nothing notable.

## Multiple parts

- One row per distinct part. If multiple photos show the same part (e.g. two
  bins of the same resistor), combine them into a single row with the summed
  quantity.
- If you're unsure whether two photos show the same part or different ones,
  ask the user rather than guessing.

## Output

Just the CSV as download (header + one row per part). If several fields are uncertain,
ask the user a quick clarifying question before finalizing rather than
guessing wildly — but don't block on fields like `location` or
`datasheet_url` that are fine left blank.