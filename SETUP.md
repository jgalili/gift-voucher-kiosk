# Setup guide

From nothing to a working kiosk in about twenty minutes. No Power Platform experience assumed —
every step says what you should see when it worked.

---

## Before you start

| | |
|---|---|
| **A SharePoint list** | With `Title` (single line of text), `Employee` (person), and `QRCodes` (single line of text). A `number` column is optional and is not used. |
| **A Power Apps and Power Automate licence** | The ones included with Microsoft 365 are enough. Nothing here is premium. |
| **A barcode scanner** | Any handheld model that behaves as a keyboard. You can also just type an email while testing. |

**What the badges must encode.** This build looks people up by email address, so the scanner has
to emit something like `jane@contoso.com`. If your badges carry a payroll number instead, stop
here and read [the architecture doc](docs/ARCHITECTURE.md#1-identifying-the-employee) — you need
one extra lookup step and it belongs in a specific place.

---

## Step 1 — Prepare the list and the library

Open the list and confirm a row looks roughly like this:

| Title | Employee | QRCodes |
|---|---|---|
| Rosh Hashana | Judith Galili | `T123;T543;T666` |

Semicolons between codes, no spaces needed. Trailing semicolons are tolerated — the app throws
the empty entries away.

Then add two things:

**A `Printed` column.** *Add column* → **Yes/No** → name it exactly `Printed` → default **No** →
Save. This is what stops a sheet being printed twice.

**A `VoucherPDFs` document library.** *Site contents* → **New** → **Document library** → name it
exactly `VoucherPDFs`. The flow writes the working HTML and the finished PDF here. It won't create
the library for you, on purpose — a flow that quietly creates things in your site is worse than
one that fails with a clear error.

> **Existing rows will have a blank `Printed`, not a No.** That's fine and expected; the app tests
> for `Printed <> true` precisely so those rows still print.

> **`QRCodes` is a single line of text**, which SharePoint caps at 255 characters — roughly 40
> five-character codes. Past that it truncates without telling you. Split long batches across
> rows; the app merges them back together anyway.

---

## Step 2 — Build the flow

Follow **[`flow/README.md`](flow/README.md)** — nine actions in the Power Automate designer, none
of them premium. Name it exactly `Generate Gift Voucher PDF`; the app refers to it by name.

**What you should see:** a manual test run that returns a `pdfurl`, and a PDF sitting in
`VoucherPDFs`.

---

## Step 3 — Create the app

1. Go to <https://make.powerapps.com> and check the environment picker, top right, is the one
   you want.
2. **Create** → **Blank app** → **Blank canvas app** → **Create**.
3. Name it `Gift Voucher Kiosk`, choose **Tablet**, then **Create**.

**What you should see:** an empty screen called `Screen1` and a formula bar across the top.

---

## Step 4 — Connect your list and the flow

1. In the left rail, click the **Data** icon (a cylinder).
2. **Add data** → search **SharePoint** → pick your connection.
3. Paste your site URL, then tick **GiftVouchers** and click **Connect**.

**What you should see:** `GiftVouchers` listed under Data. If you type `GiftVouchers` into the
formula bar now it will resolve instead of turning red.

Then add the flow: select the **Print** button, open the **Power Automate** pane from the left
rail, and choose `Generate Gift Voucher PDF`. Power Apps rewrites the button's `OnSelect` when you
do this, so add the flow *before* you paste the formula from the app guide, not after.

---

## Step 5 — Build the two screens

Every control and every formula is in **[`app/README.md`](app/README.md)** — screen by screen,
property by property. Work through it in order:

- `App.OnStart` — the bar widths and the Code 39 table
- `scrScan` — the text box the scanner types into
- `scrVouchers` — the card gallery and the print button

Rename `Screen1` to `scrScan` before you start. The formulas refer to controls by name, so the
names matter.

> **Don't retype the Code 39 table — copy and paste it.** One wrong character produces a barcode
> that looks perfect and scans as a different code, which is the worst thing a voucher can do.

> **Watch out for the formula bar's autocomplete.** Power Apps will helpfully finish names as you
> type, which mangles pasted formulas. Paste into a plain text editor first if a formula comes out
> looking wrong, then paste it in one go rather than typing it.

---

## Step 6 — Test it without a scanner

Press **F5** (or the play button) to preview.

1. Type an employee's email into the box and wait about half a second. Do **not** press Enter —
   the delay is what triggers the lookup, and this is exactly what a scanner produces.
2. You should land on the voucher screen with one card per code.
3. Click **Print**. The PDF opens, and the batches you just printed flip to `Printed = Yes`.
4. Scan the same address again. You should be told, by name, that they have already collected
   everything — and nothing should print.

**Check a barcode actually scans** before you trust it: print one sheet on paper and read a code
with the handheld scanner. On screen it will not scan reliably no matter how good it looks, and
that is normal — screen pixels and print dots are not the same thing.

**Nothing happened?** The most common cause is `DelayOutput` being left off on `txtScan`. Without
it, `OnChange` fires on every keystroke and the lookup runs against a half-typed address.

**"No vouchers found"?** Check the email you typed matches the `Employee` column's address
exactly, including case. The filter is deliberately case-sensitive so it stays delegable — see
[the architecture note](docs/ARCHITECTURE.md#1-identifying-the-employee).

**"Already collected" when you didn't expect it?** You're testing with rows you printed earlier.
Open the list, set `Printed` back to No, and scan again.

---

## Step 7 — Plug in the scanner

1. Open Notepad and scan a badge. Whatever appears is exactly what the app will receive.
2. If you get the email followed by a new line, you are done — the scanner is in
   keyboard-wedge mode and needs no configuration.
3. If you get nothing, or a jumble, consult the scanner's manual for "USB HID keyboard" mode.
   Most scanners are configured by scanning a barcode printed in that manual.

**What you should see:** scanning a badge in the previewed app fills the box and moves to the
voucher screen on its own.

---

## Step 8 — Share it

**Share** (top right) → add the people who staff the handout desk → **Share**.

They also need read access to the SharePoint list; Power Apps will prompt you about this and it
is easier to accept than to fix later.

> **Think about who you share it with.** Anyone with the app and a colleague's email address can
> print that colleague's vouchers. There is no check that the badge belongs to the person holding
> it. That is fine for a staffed desk and not fine for a self-service portal — see
> [the limitations](README.md#-honest-limitations).

---

## Removing it

Delete the app from **Apps**, the flow from **My flows**, and the connection under
**Connections** if nothing else uses it. The `VoucherPDFs` library can go too.

Your original list survives, but note that it **is** written to — the app sets `Printed` on rows it
has printed. To restore the list exactly as it was, clear that column.
