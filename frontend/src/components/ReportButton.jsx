import { useEffect, useRef, useState } from 'react';
import { CircleNotch, FileArrowDown } from '@phosphor-icons/react';
import { exportReportPdf } from '../lib/exportReport';

/**
 * "Download PDF" button. While exporting it mounts the sheet from `renderSheet()` off-screen,
 * captures its [data-report-page]s and saves the PDF.
 */
export default function ReportButton({ productName, renderSheet, align = 'end' }) {
  const sheetRef = useRef(null);
  const [state, setState] = useState('idle'); // idle | exporting | error

  useEffect(() => {
    if (state !== 'exporting') return undefined;
    let cancelled = false;
    exportReportPdf(sheetRef.current, productName)
      .then(() => !cancelled && setState('idle'))
      .catch((err) => {
        console.error(err);
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [state, productName]);

  return (
    <div className={`flex flex-col items-start gap-2 ${align === 'end' ? 'md:items-end' : ''}`}>
      <button
        type="button"
        onClick={() => setState('exporting')}
        disabled={state === 'exporting'}
        className="inline-flex h-12 items-center gap-2.5 rounded-[12px] bg-brand px-5 text-[15px] font-semibold text-white transition-[background-color,scale] duration-150 ease-(--ease-out) hover:bg-brand-deep focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal active:scale-[0.97] disabled:cursor-wait disabled:opacity-80"
      >
        {state === 'exporting' ? (
          <CircleNotch className="size-4 animate-spin" weight="bold" aria-hidden="true" />
        ) : (
          <FileArrowDown className="size-5" aria-hidden="true" />
        )}
        {state === 'exporting' ? 'نجهّز التقرير…' : 'نزّل التقرير PDF'}
      </button>
      {state === 'error' && (
        <p role="alert" className="text-[13px] text-signal">
          تعذّر تجهيز التقرير، حاول مرة أخرى.
        </p>
      )}
      {state === 'exporting' && <div ref={sheetRef}>{renderSheet()}</div>}
    </div>
  );
}
