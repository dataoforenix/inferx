// Renders the report pages to images and packs them into an A4 PDF.
// Canvas rendering (rather than jsPDF text) keeps Arabic shaping intact.
// Both libraries are loaded on demand so they stay out of the main bundle.

const safeFileName = (name) => name.replace(/[\\/:*?"<>|]+/g, ' ').trim();

export async function exportReportPdf(sheet, productName) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([import('html2canvas'), import('jspdf')]);
  await document.fonts.ready;

  const pdf = new jsPDF({ unit: 'mm', format: 'a4', compress: true });
  const pageW = pdf.internal.pageSize.getWidth();
  const pageH = pdf.internal.pageSize.getHeight();

  const pages = [...sheet.querySelectorAll('[data-report-page]')];
  for (const [i, page] of pages.entries()) {
    const canvas = await html2canvas(page, {
      scale: 2,
      backgroundColor: '#f6f3ec',
      logging: false,
      // The sheet is hidden on screen; show it only inside html2canvas's clone.
      onclone: (_doc, clone) => {
        clone.parentElement.style.visibility = 'visible';
      },
    });
    // Shrink to fit if a page ran taller than A4.
    const h = Math.min(pageH, (canvas.height * pageW) / canvas.width);
    const w = (canvas.width * h) / canvas.height;
    if (i > 0) pdf.addPage();
    pdf.addImage(canvas.toDataURL('image/jpeg', 0.92), 'JPEG', (pageW - w) / 2, 0, w, h);
  }

  pdf.save(`صنّعها - ${safeFileName(productName)}.pdf`);
}
