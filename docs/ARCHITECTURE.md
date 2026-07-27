# Architecture

## The problem

A SharePoint list holds gift voucher batches. Each row is one *batch* for one *employee* —
a batch name in `Title`, the person in `Employee`, and all the voucher codes crammed into a
single text column as a semicolon-separated string:

| Title | Employee | QRCodes | number |
|---|---|---|---|
| Rosh Hashana | Judith Galili | `T123;T543;T666` | 3 |
| Shavuot | Judith Galili | `T988;T443` | 2 |

At a handout desk, an employee scans their card and needs a printable sheet with **one card per
voucher code** — not one card per row. So the work splits into three jobs: identify the person
from a scan, explode the batches into individual vouchers, and lay those vouchers out as a
printable PDF.

## The shape of the solution

```
  employee card                                                         printable PDF
       │                                                                      ▲
       ▼                                                                      │
┌──────────────┐   employee email    ┌────────────────┐   voucher JSON   ┌────────────┐
│  Scan screen │ ──────────────────► │  SharePoint    │ ───────────────► │   Cloud    │
│  (text input)│                     │  GiftVouchers  │                  │   flow     │
└──────────────┘                     └────────────────┘                  └────────────┘
                                              │                                 │
                                              ▼                                 ▼
                                     ┌────────────────┐                  HTML → PDF via
                                     │ Voucher screen │                  SharePoint's
                                     │ (card gallery) │                  Convert file
                                     └────────────────┘
```

Three moving parts, and only one of them holds any logic worth explaining.

## 1. Identifying the employee

The card encodes the employee's email address (UPN). The `Employee` column is a SharePoint
person field, so the match is direct — no lookup table, no mapping list:

```powerfx
Filter(GiftVouchers, Employee.Email = gblScanId)
```

Equality on `Employee.Email` **is** delegable to SharePoint, so this stays correct past 2,000
rows. Case matters to the delegable form, which is why the scan is normalised once on the way
in rather than wrapped in `Lower()` inside the filter — `Lower()` on the left-hand side would
silently break delegation.

There is no camera and no barcode reader control. A handheld keyboard-wedge scanner simply types
the ID into a focused text box and presses Enter, which is why the text input uses
`DelayOutput: true` — Power Apps has no "on Enter" event for text inputs, but `DelayOutput` fires
`OnChange` once typing stops, which is exactly the behaviour a wedge scanner produces.
`SetFocus()` on screen entry keeps the box armed between employees.

## 2. Exploding the batches into cards

This is the only genuinely fiddly bit of Power Fx in the app. `Split()` turns one row's
`QRCodes` into a table, `AddColumns` attaches that table to its parent row, and `Ungroup`
flattens the nested result into one record per code:

```powerfx
ClearCollect(colCards,
    ForAll(
        Ungroup(
            AddColumns(colBatches, "Codes",
                Filter(Split(QRCodes, ";"), !IsBlank(Trim(Result)))
            ),
            "Codes"
        ),
        {
            Batch:     Title,
            Code:      Trim(Result),
            Employee:  gblEmployeeName,
            Generated: gblGeneratedAt
        }
    )
)
```

The inner `Filter(..., !IsBlank(Trim(Result)))` matters more than it looks. A trailing semicolon
(`T123;T543;`) is easy for a human to leave behind and would otherwise produce a blank voucher
card in the printed output.

`number` is deliberately **not** used as the source of truth. It is a convenience column that can
drift out of step with `QRCodes`; the codes themselves are authoritative. The app surfaces the
mismatch rather than trusting either side.

## 3. Rendering the QR codes

Power Apps has no QR generator — the built-in barcode control only *reads*. This build uses the
free `api.qrserver.com` endpoint, called from an `Image` control's `Image` property:

```powerfx
"https://api.qrserver.com/v1/create-qr-code/?size=300x300&margin=0&data=" & EncodeUrl(ThisItem.Code)
```

**This sends every voucher code to a third-party service.** For the test codes here that is
irrelevant; before this handles real, redeemable vouchers it should be swapped for something that
keeps codes inside the tenant. See [Swapping the QR renderer](#swapping-the-qr-renderer).

## 4. The PDF

The app hands the flow three things — the employee name, a formatted timestamp, and the card
collection as JSON — and gets back a URL:

```powerfx
Set(gblPdf,
    GenerateGiftVoucherPDF.Run(
        gblEmployeeName,
        Text(gblGeneratedAt, "[$-en-US]dd mmm yyyy, HH:mm"),
        JSON(colCards, JSONFormat.Compact)
    )
);
Download(gblPdf.pdfurl)
```

The flow builds an A4 HTML page — a CSS grid of voucher cards with page-break rules — writes it
to a document library, and calls SharePoint's **Convert file** action, which renders it to PDF
through the same Graph conversion service that powers "Download as PDF" in Office. That is why
this needs no premium connector and costs nothing.

HTML was chosen over the native `PDF()` function because print layout is the whole point here.
`PDF()` captures what fits on a screen; it has no concept of a page break, so a fourteen-voucher
sheet either overflows or has to be paged by hand. The flow's HTML has `page-break-inside: avoid`
on each card and gets clean A4 pages for free.

### Why the timestamp is computed in the app, not the flow

`Now()` in the flow would be the *server's* clock at *conversion* time, in UTC. The employee is
standing at the desk; the time printed on their voucher should be the moment they scanned, in
their own timezone. So the app stamps it, and the flow only formats what it is given.

## Trust and failure modes

| Situation | What happens |
|---|---|
| Unknown card scanned | Message on the scan screen; nothing navigates, box re-arms for the next scan |
| Employee has no voucher rows | Same path as unknown — treated as "nothing to hand out" |
| `QRCodes` blank on a row that exists | Row contributes zero cards; other batches still print |
| `number` disagrees with the actual code count | Cards are built from the codes; the app shows the real count |
| QR service unreachable | Cards still render with the code printed as text; only the QR image is missing |
| Flow fails | Button re-enables and surfaces the error rather than silently doing nothing |

**What this does not do.** Nothing here marks a voucher as redeemed, prevents a second printing,
or audits who printed what. Anyone who can open the app and knows a colleague's email can print
that colleague's vouchers. If the codes are worth money, read
[the limitations](../README.md#-honest-limitations) before deploying it.

## Swapping the QR renderer

The QR URL appears in exactly two places — `imgQR.Image` in the app and the `<img>` tag in the
flow's HTML — so replacing the service is a two-line change. Options, cheapest first:

- **An Azure Function** on the free consumption tier returning a PNG. Codes stay in your tenant.
- **A PCF code component** drawing the QR client-side, so codes never leave the browser at all.
  Needs code components enabled in the environment.
- **A premium connector** (Encodian, Plumsail) if you already pay for one.

The flow and the app must use the same renderer, or the on-screen preview and the printed sheet
will disagree.
