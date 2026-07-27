# The flow — `Generate Gift Voucher PDF`

Nine actions, no premium connectors. Build it in the Power Automate designer following the table
below, or read [`definition.json`](definition.json) if you prefer the raw Logic Apps definition.

The print markup lives in [`voucher-sheet.html`](voucher-sheet.html) — edit and preview that file
in a browser first, then port the change into steps 3 and 4.

---

## What it takes and what it gives back

| Direction | Name | Type | Example |
|---|---|---|---|
| in | `employeeName` | text | `Judith Galili` |
| in | `generatedAt` | text | `26 Jul 2026, 18:20` |
| in | `cardsJson` | text | `[{"Batch":"Rosh Hashana","Code":"T123",…}]` |
| out | `pdfurl` | text | a sharing link to the finished PDF |
| out | `filename` | text | `vouchers-judith-galili-20260726-182014.pdf` |

The timestamp arrives **already formatted**, as a string. That is deliberate: `utcNow()` inside
the flow would be the server's clock in UTC at conversion time, not the moment the employee
actually stood at the desk. See [the architecture note](../docs/ARCHITECTURE.md#why-the-timestamp-is-computed-in-the-app-not-the-flow).

---

## The nine actions

| # | Action | Configuration |
|---|---|---|
| 1 | **Power Apps (V2)** trigger | Three text inputs: `employeeName`, `generatedAt`, `cardsJson` |
| 2 | **Parse JSON** | Content: `cardsJson` from the trigger. Schema below. |
| 3 | **Select** — rename it `Select_cards` | From: `body('Parse_JSON')`. Switch the map to **text mode** (the small icon on the right) and paste the card expression below. |
| 4 | **Compose** — rename it `Compose_html` | The full document: header, `join(body('Select_cards'), '')`, footer. |
| 5 | **Create file** (SharePoint) | Site: your site. Folder: `/VoucherPDFs`. Name: `concat('vouchers-', <slug>, '-', utcNow('yyyyMMdd-HHmmss'), '.html')`. Content: `outputs('Compose_html')` |
| 6 | **Convert file** (SharePoint) | File: `body('Create_file')?['Id']`. Target type: **PDF**. |
| 7 | **Create file** (SharePoint) | Same folder. Name: the same slug with `.pdf`. Content: `body('Convert_file')` |
| 8 | **Create sharing link for a file or folder** | File: the PDF's `Id`. Link type: **View**. Scope: **Organization**. |
| 9 | **Respond to a PowerApp or flow** | `pdfurl` = `body('Create_sharing_link')?['link']?['webUrl']`, `filename` = the PDF name |

A tenth optional action — **Delete file** on the temporary `.html` — keeps the library tidy. Put
it after step 8, and set its *Configure run after* to run on both success and failure so a
conversion error doesn't leave orphans behind.

### Step 2 — Parse JSON schema

```json
{
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "Batch":     { "type": "string" },
      "Code":      { "type": "string" },
      "Employee":  { "type": "string" },
      "Generated": { "type": "string" }
    },
    "required": [ "Batch", "Code" ]
  }
}
```

### Step 3 — the card expression

One `<div>` per voucher. Paste this as the whole map value, in text mode:

```
concat(
  '<div class="card"><div class="batch">', item()?['Batch'],
  '</div><img src="https://api.qrserver.com/v1/create-qr-code/?size=300x300&margin=0&data=',
  encodeUriComponent(item()?['Code']),
  '" alt=""><div class="code">', item()?['Code'],
  '</div><div class="who">', triggerBody()['text'],
  '</div><div class="when">Generated ', triggerBody()['text_1'],
  '</div></div>'
)
```

`triggerBody()['text']` is `employeeName` and `text_1` is `generatedAt` — the Power Apps V2
trigger names its inputs positionally, which is unhelpful but stable.

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

## Things that go wrong

**"Convert file" fails with an unsupported format.** The conversion service works from the file
extension, not the content type. The temporary file must end in `.html` — `.htm` also works,
anything else does not.

**The PDF has empty boxes where the QR codes should be.** The converter renders server-side and
must fetch each QR image over the internet. If your tenant blocks that, or the QR service is
unreachable, the images come back blank — the printed codes underneath are still correct and the
vouchers are still redeemable by hand. This is the strongest argument for swapping the QR
renderer for something that produces inline data URIs;
[the architecture doc](../docs/ARCHITECTURE.md#swapping-the-qr-renderer) covers the options.

**The app gets a link it can't open.** Sharing scope **Organization** requires the person running
the app to be signed in to the same tenant. For guests, use **Anyone** — and understand that you
have just made every voucher code in that PDF readable by anyone with the link.
