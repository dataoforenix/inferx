import { useEffect, useId, useRef, useState } from 'react';
import { ArrowLeft, ImageSquare, X } from '@phosphor-icons/react';

const MAX_MB = 8; // the backend's upload limit
// What the backend accepts. Some files (e.g. .jfif) arrive without a MIME type, so check the name too.
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const IMAGE_EXT = /\.(jpe?g|jfif|png|webp)$/i;
const isSupportedImage = (f) => IMAGE_TYPES.includes(f.type) || (!f.type && IMAGE_EXT.test(f.name));
// Each matches a prepared example, so they also work while the backend runs in demo mode.
// The last one is the ambiguous example: it shows the «أيّ هذه هو منتجك؟» confirmation step in demo mode.
const SUGGESTIONS = ['كرسي مكتب معدني منجد', 'رفوف مستودعات', 'صحون بلاستيك للمطبخ', 'مروحة سقف', 'كرسي بلاستيك بأرجل معدنية'];

function formatSize(bytes) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

export default function ProductInput({ onAnalyze, busy = false }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [dragging, setDragging] = useState(false);
  const previewRef = useRef(null);
  const handedOffRef = useRef(null); // preview of the last submitted photo, shown in the analysis view
  const fileInputRef = useRef(null);
  useEffect(
    () => () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
      if (handedOffRef.current) URL.revokeObjectURL(handedOffRef.current);
    },
    [],
  );

  // A file dropped just outside the composer would make the browser open it and leave the site.
  useEffect(() => {
    const guard = (e) => {
      if (e.dataTransfer?.types?.includes('Files')) e.preventDefault();
    };
    window.addEventListener('dragover', guard);
    window.addEventListener('drop', guard);
    return () => {
      window.removeEventListener('dragover', guard);
      window.removeEventListener('drop', guard);
    };
  }, []);

  const setImage = (f) => {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = f ? URL.createObjectURL(f) : null;
    setPreview(previewRef.current);
    setFile(f);
    if (!f && fileInputRef.current) fileInputRef.current.value = '';
  };
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const nameId = useId();
  const hintId = useId();
  const canSubmit = (file || name.trim().length > 1) && !busy;

  const onFile = (f) => {
    if (!f) return setImage(null);
    if (!isSupportedImage(f)) return setError('نوع الملف غير مدعوم. استخدم صورة JPG أو PNG أو WebP.');
    if (f.size > MAX_MB * 1024 * 1024) return setError(`حجم الصورة أكبر من ${MAX_MB}MB.`);
    setError('');
    setImage(f);
  };

  // The whole composer is the drop target, so a photo can land anywhere on it (and replace the current one).
  const dropProps = {
    onDragEnter: (e) => {
      e.preventDefault();
      setDragging(true);
    },
    onDragOver: (e) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      setDragging(true);
    },
    onDragLeave: (e) => {
      // dragleave also fires when moving onto a child element; only reset when the pointer really left.
      if (!e.currentTarget.contains(e.relatedTarget)) setDragging(false);
    },
    onDrop: (e) => {
      e.preventDefault();
      setDragging(false);
      // Images dragged from a web page (e.g. WhatsApp Web) carry a link, not a file.
      if (e.dataTransfer.files.length) onFile(e.dataTransfer.files[0]);
      else setError('لم تصل الصورة. اسحبها من ملفات جهازك، أو اضغط «أرفق صورة».');
    },
  };

  const onSubmit = (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    // Only what the user typed is sent as the description; a file name like "WhatsApp Image …" would mislead the AI.
    onAnalyze?.({ name: label, text: name.trim(), file, preview });

    // Start the next product from an empty form, so an old photo never gets sent with a new name.
    // The preview URL now belongs to the analysis view; free the one handed over before it.
    if (handedOffRef.current) URL.revokeObjectURL(handedOffRef.current);
    handedOffRef.current = previewRef.current;
    previewRef.current = null;
    setPreview(null);
    setFile(null);
    setName('');
    setError('');
  };

  const label = name.trim() || 'صورة المنتج';

  return (
    <section id="product-input" aria-labelledby="product-input-title" className="relative scroll-mt-0">
      <div className="mx-auto grid max-w-[1320px] gap-10 px-5 py-24 md:px-10 md:py-32 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-16">
        <div className="lg:pt-4">
          <h2
            id="product-input-title"
            tabIndex={-1}
            data-autofocus
            className="font-display text-[clamp(2rem,1.2rem+2.4vw,3rem)] leading-[1.2] font-bold text-ink outline-none"
          >
            ابدأ من منتجك
          </h2>
          <p className="mt-4 max-w-[38ch] text-[1.0625rem] leading-[1.9] text-ink-muted">
            اكتب اسمه أو صِفه، وأرفق صورة إن وُجدت. كلما كان الوصف أدق، كان التقييم أدق.
          </p>
        </div>

        <form onSubmit={onSubmit} noValidate>
          <div
            {...dropProps}
            className={`relative rounded-[16px] border bg-white shadow-[0_24px_50px_-34px_rgb(21_24_27/0.45)] transition-[border-color,box-shadow] duration-200 focus-within:border-ink/40 ${
              dragging ? 'border-ink' : error ? 'border-signal/50' : 'border-hairline'
            }`}
          >
            <label htmlFor={nameId} className="block px-5 pt-4 text-[13px] font-medium text-ink-muted md:px-6 md:pt-5">
              اسم المنتج أو وصفه
            </label>
            <textarea
              id={nameId}
              rows={3}
              maxLength={280}
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) e.currentTarget.form?.requestSubmit();
              }}
              placeholder="مثال: رفوف حديدية لتخزين البضائع في المستودعات، بأحمال ثقيلة"
              autoComplete="off"
              aria-describedby={hintId}
              className="block w-full resize-none bg-transparent px-5 pt-1 pb-3 font-display text-[1.25rem] leading-[1.7] text-ink placeholder:text-ink-muted/55 focus:outline-none md:px-6 md:text-[1.375rem]"
            />

            {file && preview && (
              <div className="mx-5 mb-3 flex items-center gap-3 rounded-[10px] bg-paper p-2 pe-3 md:mx-6">
                <img src={preview} alt="معاينة صورة المنتج" className="size-12 shrink-0 rounded-[8px] bg-paper-2 object-cover" />
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-medium text-ink">الصورة مرفقة</p>
                  <p className="truncate font-mono text-[11.5px] text-ink-muted" dir="ltr">
                    {file.name} · {formatSize(file.size)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onFile(null)}
                  aria-label="إزالة الصورة"
                  className="grid size-8 shrink-0 place-items-center rounded-[8px] text-ink-muted transition-colors duration-150 hover:bg-paper-2 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
                >
                  <X className="size-4" weight="bold" aria-hidden="true" />
                </button>
              </div>
            )}

            <div className="flex items-center justify-between gap-3 border-t border-hairline px-3 py-3 md:px-4">
              <label className="inline-flex h-11 cursor-pointer items-center gap-2 rounded-[10px] px-3 text-[14.5px] font-medium text-ink transition-colors duration-150 hover:bg-paper has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-signal">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept={IMAGE_TYPES.join(',')}
                  className="sr-only"
                  onChange={(e) => onFile(e.target.files?.[0])}
                />
                <ImageSquare className="size-5" aria-hidden="true" />
                {file ? 'استبدل الصورة' : 'أرفق صورة'}
              </label>
              <button
                type="submit"
                disabled={!canSubmit}
                className="group inline-flex h-11 items-center gap-3 rounded-[10px] bg-brand ps-5 pe-1.5 font-display text-[1rem] font-semibold text-white transition-[background-color,opacity,scale] duration-150 ease-(--ease-out) hover:bg-brand-deep focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:bg-brand"
              >
                {busy ? 'جارٍ التحليل…' : 'حلّل المنتج'}
                <span aria-hidden="true" className="grid size-8 place-items-center rounded-[7px] bg-accent text-ink">
                  <ArrowLeft
                    weight="bold"
                    className={`size-4 transition-transform duration-200 ease-(--ease-out) group-hover:-translate-x-0.5 ${busy ? 'animate-pulse' : ''}`}
                  />
                </span>
              </button>
            </div>

            {dragging && (
              <div className="pointer-events-none absolute inset-2 grid place-items-center rounded-[12px] border-2 border-dashed border-ink/50 bg-white/90">
                <p className="flex items-center gap-2 font-display text-[1.125rem] font-semibold text-ink">
                  <ImageSquare className="size-6" aria-hidden="true" />
                  {file ? 'أفلت لاستبدال الصورة' : 'أفلت الصورة هنا'}
                </p>
              </div>
            )}
          </div>

          <p id={hintId} className="mt-3 min-h-6 text-[13.5px]" role="status" aria-live="polite">
            {error ? (
              <span className="text-signal">{error}</span>
            ) : busy ? (
              <span className="text-ink">نحلّل «{label}» الآن…</span>
            ) : (
              <span className="text-ink-muted">الصورة اختيارية: JPG أو PNG أو WebP حتى {MAX_MB}MB، ويمكن سحبها إلى الخانة.</span>
            )}
          </p>

          <div className="mt-5 flex flex-wrap items-baseline gap-x-5 gap-y-2 text-[14.5px]">
            <span className="text-ink-muted">جرّب:</span>
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => setName(s)}
                aria-pressed={name === s}
                className={`rounded-sm underline decoration-1 underline-offset-[6px] transition-[color,text-decoration-color] duration-150 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal ${
                  name === s ? 'text-ink decoration-accent decoration-2' : 'text-ink/75 decoration-ink/20 hover:text-ink hover:decoration-ink/60'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </form>
      </div>
    </section>
  );
}
