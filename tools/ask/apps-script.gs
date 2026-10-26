// Break The Routine · "Ask the next guest" → this Google Sheet + an email to the sheet owner.
// Paste in the sheet: Extensions → Apps Script. Deploy → New deployment → Web app,
// Execute as: Me, Who has access: Anyone. Put the /exec URL in Vercel as ASK_WEBHOOK_URL
// and the SECRET below as ASK_SECRET.
const SECRET = 'PASTE_THE_SAME_VALUE_AS_ASK_SECRET';

function doPost(e) {
  try {
    const d = JSON.parse(e.postData.contents);
    if (d.secret !== SECRET) return out({ ok: false, error: 'forbidden' });
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
    if (sheet.getLastRow() === 0) sheet.appendRow(['Date', 'Name', 'Instagram', 'Question', 'OK to say name on show', 'Status']);
    const clean = (v, n) => String(v || '').slice(0, n).replace(/^[=+\-@]/, "'$&");
    sheet.appendRow([new Date(), clean(d.name, 80), clean(d.ig, 40), clean(d.q, 280), d.ok ? 'Yes' : 'No', 'New']);
    MailApp.sendEmail({
      to: Session.getEffectiveUser().getEmail(),
      subject: 'BTR · New question from ' + clean(d.name, 80),
      body: '"' + String(d.q || '') + '"\n\n' + String(d.name || '') + (d.ig ? ' (' + d.ig + ')' : '') +
        '\nOK to say name on show: ' + (d.ok ? 'Yes' : 'No') + '\n\nAll questions: ' + SpreadsheetApp.getActiveSpreadsheet().getUrl()
    });
    return out({ ok: true });
  } catch (err) {
    return out({ ok: false, error: String(err) });
  }
}

function out(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}
