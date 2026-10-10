// Small "estimate" badge for numbers built from a column listed in report.estimated_fields
// (docs/api_contract.md, "Data-quality badges"). Solid colors only: it is also drawn into the PDF,
// and html2canvas can't parse color-mix().
// `plain` (used in the PDF): html2canvas draws a pill's box and its Arabic text at different heights,
// so the printed report uses a bracketed word instead.
export default function EstimateTag({ show, plain = false }) {
  if (!show) return null;
  if (plain) return <span className="ms-1 text-[11px] font-normal text-[#5b6474]">(تقدير)</span>;
  return (
    <span className="ms-1.5 inline-flex h-[17px] items-center rounded-[4px] border border-[#cfd3d0] bg-[#eceeec] px-1.5 align-middle font-sans text-[10.5px] leading-none font-medium text-[#596067]">
      تقدير
    </span>
  );
}
