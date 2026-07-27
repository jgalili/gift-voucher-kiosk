# The flow — `Generate Gift Voucher PDF`

Nine actions, no premium connectors. Build it in the Power Automate designer following the table
below; the print stylesheet is in [`voucher-sheet.html`](voucher-sheet.html).

**There are no `<img>` tags anywhere in the output, and that is the point.** SharePoint's Convert
file action renders server-side with no network access — it draws anything embedded in the file
and refuses to fetch anything referenced by it. The barcodes therefore arrive from the app as
plain `<i>` elements with widths. Nothing is fetched, nothing is a font, and no voucher code ever
leaves the tenant. The full account of how that was established is in
[the architecture doc](../docs/ARCHITECTURE.md#what-the-test-showed).

---

## What it takes and what it gives back

| Direction | Name | Type | Example |
|---|---|---|---|
| in | `employeeName` | text | `Judith Galili` |
| in | `generatedAt` | text | `27 Jul 2026, 09:12` |
| in | `cardsJson` | text | `[{"Batch":"Rosh Hashana","Code":"T123","Employee":"…","Bars":"<i class=\"bn\"></i>…"}]` |
| out | `pdfurl` | text | a sharing link to the finished PDF |
| out | `filename` | text | `vouchers-judith-galili-20260727-091203.pdf` |

The timestamp arrives **already formatted**, as a string. That is deliberate: `utcNow()` inside
the flow would be the server's clock in UTC at conversion time, not the moment the employee
actually stood at the desk.

`Bars` is roughly a kilobyte per code, so `cardsJson` is the large input. Forty vouchers is around
40 KB, comfortably inside the limit, but it is the reason the app strips every column the flow
doesn't need before serialising.

---

## The nine actions

| # | Action | Configuration |
|---|---|---|
| 1 | **Power Apps (V2)** trigger | Three text inputs: `employeeName`, `generatedAt`, `cardsJson` |
| 2 | **Parse JSON** | Content: `cardsJson` from the trigger. Schema below. |
| 3 | **Select** — rename it `Select_cards` | From: `body('Parse_JSON')`. Switch the map to **text mode** (the small icon on the right) and paste the card expression below. |
| 4 | **Compose** — rename it `Compose_html` | The full document: the head and header from `voucher-sheet.html`, then `join(body('Select_cards'), '')`, then the footer. |
| 5 | **Create file** (SharePoint) | Site: your site. Folder: `/VoucherPDFs`. Name: the slug below, ending `.html`. Content: `outputs('Compose_html')` |
| 6 | **Convert file** (SharePoint) | File: `body('Create_file')?['Id']`. Target type: **PDF**. |
| 7 | **Create file** (SharePoint) | Same folder. Same slug with `.pdf`. Content: `body('Convert_file')` |
| 8 | **Create sharing link for a file or folder** | File: the PDF's `Id`. Link type: **View**. Scope: **Organization**. |
| 9 | **Respond to a PowerApp or flow** | `pdfurl` = `body('Create_sharing_link')?['link']?['webUrl']`, `filename` = the PDF name |

A tenth optional action — **Delete file** on the temporary `.html` — keeps the library tidy. Put
it after step 8 and set its *Configure run after* to run on both success and failure, so a
conversion error doesn't leave orphans behind.

**Step 9 is load-bearing.** The app only marks rows as printed when `pdfurl` comes back non-empty.
If you let the flow end without responding, every sheet will print and nothing will ever be marked
as collected.

### Step 2 — Parse JSON schema

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "Batch":    { "type": "string" },
      "Code":     { "type": "string" },
      "Employee": { "type": "string" },
      "Bars":     { "type": "string" }
    },
    "required": [ "Code", "Bars" ]
  }
}
```

### Step 3 — the card expression

One `<div>` per voucher. Paste this as the whole map value, in text mode:

```
concat(
  '<div class="card"><div class="batch">', item()?['Batch'],
  '</div><div class="bc">', item()?['Bars'],
  '</div><div class="code">', item()?['Code'],
  '</div><div class="who">', item()?['Employee'],
  '</div><div class="when">Generated ', triggerBody()['text_1'],
  '</div></div>'
)
```

`triggerBody()['text_1']` is `generatedAt` — the Power Apps V2 trigger names its inputs
positionally, which is unhelpful but stable. `text` is `employeeName` and `text_2` is `cardsJson`.

Note that `Bars` is dropped in verbatim, not escaped. It is markup the app generated from a fixed
table of `n` and `w` characters, so there is nothing user-supplied in it — but if you ever change
where `Bars` comes from, revisit that.

### Step 5 — the file name slug

```
concat(
  'vouchers-',
  toLower(replace(triggerBody()['text'], ' ', '-')),
  '-',
  utcNow('yyyyMMdd-HHmmss'),
  '.html'
)
```

`utcNow()` **is** the right call here — this is a file name, not something a human reads as a
time. It guarantees uniqueness so two people scanning in the same minute can't collide.

---

## Before you build it

Create a document library called **VoucherPDFs** on the site. The flow writes both the temporary
HTML and the finished PDF there. It does not create the library itself, because a flow silently
creating libraries in your site is worse than a flow that fails with a clear error.

---

## Things that go wrong

**"Convert file" fails with an unsupported format.** The conversion service works from the file
extension, not the content type. The temporary file must end in `.html` — `.htm` also works,
anything else does not.

**The barcodes print but won't scan.** Almost always the quiet zone. Code 39 needs at least ten
narrow widths of blank space either side; that is the `padding: 2mm 5mm` on `.bc`. The other
candidate is the wide-to-narrow ratio — it must stay between 2.5:1 and 3:1, so if you change
`.bn` you must change `.bw` to match.

**The bars come out as one solid block.** `font-size: 0` is missing from `.bc`. Without it the
whitespace between the inline-block elements renders as thin white gaps and the whole thing
becomes unreadable.

**The app gets a link it can't open.** Sharing scope **Organization** requires the person running
the app to be signed in to the same tenant. For guests, use **Anyone** — and understand that you
have just made every voucher code in that PDF readable by anyone with the link.
