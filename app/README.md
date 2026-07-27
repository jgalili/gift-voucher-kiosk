# The canvas app

Two screens the user sees, one they never do. Every formula is below in full — paste them in and
the app works; there is nothing hidden in a property you can't see.

**Layout:** tablet (landscape, 1366 × 768).
**Data source:** the `GiftVouchers` SharePoint list.
**Connectors:** SharePoint, plus the `GenerateGiftVoucherPDF` flow.

---

## What the list needs

| Column | Type | Notes |
|---|---|---|
| `Title` | Single line of text | The batch name — "Rosh Hashana" |
| `Employee` | Person | Matched against the scanned email |
| `QRCodes` | Single line of text | Codes separated by `;` |
| `Printed` | **Yes/No, default No** | Set to Yes once the sheet has been handed over |
| `number` | Number | Optional, and deliberately unused |

`Printed` is the one you have to add. Everything else was already there.

---

## Global state

| Variable | Holds |
|---|---|
| `gblScanId` | the email the scanner just typed, trimmed |
| `gblEmployeeName` | the display name from the person column |
| `gblGeneratedAt` | the moment of the scan — stamped once, reused everywhere |
| `gblError` | a message for the scan screen, blank when all is well |
| `gblBusy` | true while the flow is running |
| `colBatches` | the **unprinted** rows for this employee — the ones that will be printed |
| `colDone` | the rows already marked `Printed`, so the desk can see why there is nothing |
| `colCards` | one record per voucher code, exploded from `colBatches` |

---

## `App.OnStart`

Bar widths first — these are the only numbers you should ever need to change to make the
barcodes bigger, smaller or chunkier, and they apply to both the screen preview and the printed
sheet:

```powerfx
Set(gblBarN, "0.4mm");   // narrow element
Set(gblBarW, "1.2mm");   // wide element — Code 39 wants 2.5:1 to 3:1
Set(gblBarH, "14mm");    // bar height

Set(gblError, Blank());
Set(gblBusy, false);
Clear(colCards);
```

Then the Code 39 table. Each character is nine elements, alternating bar-space-bar starting with
a bar; exactly three of the nine are wide. `*` is the start and stop character and is not part of
the payload:

```powerfx
ClearCollect(colC39,
    {C:"0",P:"nnnwwnwnn"}, {C:"1",P:"wnnwnnnnw"}, {C:"2",P:"nnwwnnnnw"}, {C:"3",P:"wnwwnnnnn"},
    {C:"4",P:"nnnwwnnnw"}, {C:"5",P:"wnnwwnnnn"}, {C:"6",P:"nnwwwnnnn"}, {C:"7",P:"nnnwnnwnw"},
    {C:"8",P:"wnnwnnwnn"}, {C:"9",P:"nnwwnnwnn"},
    {C:"A",P:"wnnnnwnnw"}, {C:"B",P:"nnwnnwnnw"}, {C:"C",P:"wnwnnwnnn"}, {C:"D",P:"nnnnwwnnw"},
    {C:"E",P:"wnnnwwnnn"}, {C:"F",P:"nnwnwwnnn"}, {C:"G",P:"nnnnnwwnw"}, {C:"H",P:"wnnnnwwnn"},
    {C:"I",P:"nnwnnwwnn"}, {C:"J",P:"nnnnwwwnn"}, {C:"K",P:"wnnnnnnww"}, {C:"L",P:"nnwnnnnww"},
    {C:"M",P:"wnwnnnnwn"}, {C:"N",P:"nnnnwnnww"}, {C:"O",P:"wnnnwnnwn"}, {C:"P",P:"nnwnwnnwn"},
    {C:"Q",P:"nnnnnnwww"}, {C:"R",P:"wnnnnnwwn"}, {C:"S",P:"nnwnnnwwn"}, {C:"T",P:"nnnnwnwwn"},
    {C:"U",P:"wwnnnnnnw"}, {C:"V",P:"nwwnnnnnw"}, {C:"W",P:"wwwnnnnnn"}, {C:"X",P:"nwnnwnnnw"},
    {C:"Y",P:"wwnnwnnnn"}, {C:"Z",P:"nwwnwnnnn"},
    {C:"-",P:"nwnnnnwnw"}, {C:".",P:"wwnnnnwnn"}, {C:" ",P:"nwwnnnwnn"}, {C:"$",P:"nwnwnwnnn"},
    {C:"/",P:"nwnwnnnwn"}, {C:"+",P:"nwnnnwnwn"}, {C:"%",P:"nnnwnwnwn"}, {C:"*",P:"nwnnwnwnn"}
)
```

> This table was generated from a reference Code 39 implementation and then verified by
> rendering the bars, rasterising the resulting A4 PDF at 300 dpi and decoding it — all five test
> codes came back exactly. Please don't retype it by hand; a single wrong element produces a
> barcode that looks perfect and scans as something else, which is the worst possible failure for
> a voucher.

---

## Screen 1 — `scrScan`

### `scrScan.OnVisible`

```powerfx
Reset(txtScan);
SetFocus(txtScan)
```

That is what makes this a kiosk. The box is armed the moment the screen appears and re-armed
after every employee, so a queue of forty people is forty scans and no clicks.

### `txtScan` — text input

| Property | Value |
|---|---|
| `HintText` | `"Scan employee card…"` |
| `DelayOutput` | `true` |
| `Format` | `TextFormat.Text` |
| `Size` | `24` |

**`DelayOutput` is the whole trick.** Power Apps text inputs have no "on Enter" event. With
`DelayOutput` on, `OnChange` fires once typing stops — and a keyboard-wedge scanner produces
exactly that: a burst of characters, then silence.

### `txtScan.OnChange`

```powerfx
If(
    !IsBlank(Trim(txtScan.Text)),

    Set(gblScanId, Trim(txtScan.Text));
    Set(gblGeneratedAt, Now());

    ClearCollect(colAll, Filter(GiftVouchers, Employee.Email = gblScanId));
    ClearCollect(colBatches, Filter(colAll, Printed <> true));
    ClearCollect(colDone,    Filter(colAll, Printed = true));

    Switch(
        true,

        // nothing at all for this address
        CountRows(colAll) = 0,
            Set(gblError, "No vouchers found for " & gblScanId);
            Set(gblEmployeeName, Blank());
            Clear(colCards);
            Reset(txtScan);
            SetFocus(txtScan),

        // everything they have was already handed over
        CountRows(colBatches) = 0,
            Set(gblEmployeeName, First(colAll).Employee.DisplayName);
            Set(gblError,
                gblEmployeeName & " has already collected all "
                & CountRows(colDone) & " voucher batch(es). Nothing left to print."
            );
            Clear(colCards);
            Reset(txtScan);
            SetFocus(txtScan),

        // something to print
        true,
            Set(gblError, Blank());
            Set(gblEmployeeName, First(colBatches).Employee.DisplayName);

            ClearCollect(colCards,
                ForAll(
                    Ungroup(
                        AddColumns(colBatches, "Codes",
                            Filter(Split(QRCodes, ";"), !IsBlank(Trim(Result)))
                        ),
                        "Codes"
                    ),
                    With({s: "*" & Upper(Trim(Result)) & "*"},
                        {
                            Batch:     Title,
                            Code:      Trim(Result),
                            Employee:  gblEmployeeName,
                            Generated: gblGeneratedAt,
                            Bars:
                                Concat(
                                    ForAll(Sequence(Len(s)) As ch,
                                        With({pat: LookUp(colC39, C = Mid(s, ch.Value, 1), P)},
                                            Concat(
                                                ForAll(Sequence(9) As el,
                                                    "<i class=""" &
                                                    If(Mod(el.Value, 2) = 1, "b", "s") &
                                                    If(Mid(pat, el.Value, 1) = "w", "w", "n") &
                                                    """></i>"
                                                ),
                                                Value
                                            ) &
                                            If(ch.Value < Len(s), "<i class=""sn""></i>", "")
                                        )
                                    ),
                                    Value
                                )
                        }
                    )
                )
            );

            Navigate(scrVouchers, ScreenTransition.Fade)
    )
)
```

Five things in here are deliberate and easy to get wrong:

**`Employee.Email = gblScanId` is delegable; `Lower(Employee.Email) = …` is not.** Wrapping the
left-hand side in a function pushes the whole filter client-side, which silently caps at 2,000
rows. If your badges emit mixed case, normalise the *scan* — never the column.

**`Printed <> true`, not `Printed = false`.** A Yes/No column on rows created before you added it
is blank, not false. `= false` would skip every pre-existing row and print nothing.

**The blank filter inside `Split`.** A trailing semicolon in `QRCodes` (`"T123;T543;"`) yields an
empty final element. Without the guard that becomes a blank voucher card on the printed sheet.

**`Reset` and `SetFocus` on both failure paths.** Without them the desk has to click the box again
before the next person can scan, which in a queue is the difference between a kiosk and a
nuisance.

**The barcode is built once, here, and carried on the record.** Building it in the gallery instead
would re-evaluate 59 elements per card on every redraw.

### `lblError`

| Property | Value |
|---|---|
| `Text` | `gblError` |
| `Visible` | `!IsBlank(gblError)` |
| `Color` | `RGBA(168, 0, 0, 1)` |

---

## Screen 2 — `scrVouchers`

### Header labels

| Control | `Text` |
|---|---|
| `lblWho` | `gblEmployeeName` |
| `lblCount` | `CountRows(colCards) & " voucher(s) · generated " & Text(gblGeneratedAt, "[$-en-US]dd mmm yyyy, HH:mm")` |
| `lblAlready` | `If(CountRows(colDone) > 0, CountRows(colDone) & " earlier batch(es) already collected — not included", "")` |

### `galVouchers` — gallery

| Property | Value |
|---|---|
| `Items` | `colCards` |
| `WrapCount` | `4` |
| `TemplateSize` | `280` |

Inside the template:

| Control | Property | Value |
|---|---|---|
| `lblBatch` | `Text` | `ThisItem.Batch` |
| `htmBars` | `HtmlText` | `"<div style=""background:#fff;padding:2mm 5mm;font-size:0;white-space:nowrap"">" & Substitute(Substitute(Substitute(Substitute(ThisItem.Bars, "class=""bn""", "style=""display:inline-block;vertical-align:top;height:" & gblBarH & ";width:" & gblBarN & ";background:#000"""), "class=""bw""", "style=""display:inline-block;vertical-align:top;height:" & gblBarH & ";width:" & gblBarW & ";background:#000"""), "class=""sn""", "style=""display:inline-block;vertical-align:top;height:" & gblBarH & ";width:" & gblBarN & ";background:#fff"""), "class=""sw""", "style=""display:inline-block;vertical-align:top;height:" & gblBarH & ";width:" & gblBarW & ";background:#fff""") & "</div>"` |
| `lblCode` | `Text` | `ThisItem.Code` |
| `lblEmp` | `Text` | `ThisItem.Employee` |

The `Substitute` chain exists because the **HtmlText control does not honour a `<style>` block** —
it only keeps inline `style` attributes. The compact class-based markup is what gets sent to the
flow; this expands it to inline styles for the on-screen preview only. If the preview ever looks
wrong, that's cosmetic: the printed sheet uses the class version and the stylesheet in
[`../flow/voucher-sheet.html`](../flow/voucher-sheet.html).

The code is always shown as text beneath its barcode. If anything at all goes wrong with the
bars, the voucher is still redeemable by hand.

### `btnPrint.OnSelect`

```powerfx
Set(gblBusy, true);
Set(gblError, Blank());

Set(gblResult,
    GenerateGiftVoucherPDF.Run(
        gblEmployeeName,
        Text(gblGeneratedAt, "[$-en-US]dd mmm yyyy, HH:mm"),
        JSON(
            ShowColumns(colCards, "Batch", "Code", "Employee", "Bars"),
            JSONFormat.Compact
        )
    )
);

If(
    !IsBlank(gblResult.pdfurl),

    // only now, and only for the rows that were actually on this sheet
    ForAll(colBatches As b,
        Patch(GiftVouchers, LookUp(GiftVouchers, ID = b.ID), { Printed: true })
    );
    Launch(gblResult.pdfurl);
    Navigate(scrScan, ScreenTransition.Fade),

    Set(gblError, "The sheet could not be generated. Nothing has been marked as printed — try again.")
);

Set(gblBusy, false)
```

`btnPrint.DisplayMode`: `If(gblBusy || CountRows(colCards) = 0, DisplayMode.Disabled, DisplayMode.Edit)`

Three deliberate choices:

**`ShowColumns` drops `Generated` and anything else the flow doesn't need.** The `Bars` string is
around a kilobyte per code; a Power Apps flow input has a size ceiling and there is no reason to
spend it on a timestamp the flow is already receiving as its own parameter.

**The `Patch` happens after the flow returns, never before.** If the PDF fails, nothing is marked
printed and the employee can try again. The reverse order would quietly burn a batch on a failed
render.

**It patches `colBatches`, not `colAll`.** Only the rows that went onto this sheet get marked —
rows already printed are left exactly as they are, with their original `Modified` timestamp
intact.

> **The gap that remains.** If the flow succeeds and then the `Patch` fails — a network drop in
> the half-second between them — the sheet exists and the rows are still unprinted, so it can be
> printed again. Closing that properly needs the marking to happen inside the flow, in the same
> transaction as the render. It is written up in
> [the architecture doc](../docs/ARCHITECTURE.md#the-printed-gate).

### `btnBack.OnSelect`

```powerfx
Clear(colCards);
Clear(colBatches);
Clear(colDone);
Set(gblEmployeeName, Blank());
Navigate(scrScan, ScreenTransition.Fade)
```

Clearing on the way out matters more than it looks: without it, the next employee's screen
briefly shows the previous employee's vouchers while the new lookup runs. At a handout desk that
is a privacy problem, not a cosmetic one.

---

## Things worth knowing before you change it

- **`number` is not used anywhere.** The codes in `QRCodes` are the source of truth. If you want
  the app to police the mismatch, compare `CountRows(colCards)` against `Sum(colBatches, number)`
  and show a warning — don't make one correct the other.
- **`Split(text, ";")` returns a single-column table whose column is called `Result`.** That name
  is fixed by the platform and is why `Result` appears unqualified inside the `ForAll`.
- **`Ungroup` needs the added column's name as a string literal**, matching the one given to
  `AddColumns`. Rename one and you must rename both.
- **Code 39 encodes uppercase only.** `Upper()` is applied before lookup. A lowercase code in the
  list scans back as uppercase, so treat your codes as case-insensitive or use a different
  symbology.
- **The quiet zone is not optional.** Code 39 needs at least ten narrow widths of blank space
  either side or scanners will not see the barcode at all. That is what the `padding: 2mm 5mm`
  is doing, in both the preview and the print stylesheet. Don't tighten it to save space.
- **255 characters.** `QRCodes` is single-line text, so roughly 40 five-character codes per row.
  SharePoint truncates past that without complaining; split the batch across rows instead.
