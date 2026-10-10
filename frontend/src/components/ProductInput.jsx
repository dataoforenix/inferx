import { useEffect, useId, useRef, useState } from 'react';
import { ArrowLeft, Check, ImagePlus, X } from 'lucide-react';

const MAX_MB = 8; // the backend's upload limit
// What the backend accepts. Some files (e.g. .jfif) arrive without a MIME type, so check the name too.
const IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const IMAGE_EXT = /\.(jpe?g|jfif|png|webp)$/i;
const isSupportedImage = (f) => IMAGE_TYPES.includes(f.type) || (!f.type && IMAGE_EXT.test(f.name));
// Each matches a prepared example, so they also work while the backend runs in demo mode.
const SUGGESTIONS = ['كرسي مكتب معدني منجد', 'رفوف مستودعات', 'صحون بلاستيك للمطبخ', 'مروحة سقف'];

function formatSize(bytes) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

/** Product image dropzone: drag, click or keyboard; previews and validates locally. */
function ImageDrop({ file, preview, onFile, onNoFile, error }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const hintId = useId();

  const take = (list) => {
    const f = list?.[0];
    if (f) onFile(f);
  };

  // Shared by the empty zone and the preview, so a second image can be dropped to replace the first.
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
      if (e.dataTransfer.files.length) take(e.dataTransfer.files);
      else onNoFile();
    },
  };

  if (file && preview) {
    return (
      <div
        {...dropProps}
        className={`relative flex h-full min-h-56 items-center gap-5 rounded-2xl border p-4 transition-[background-color,border-color] duration-200 ${
          dragging ? 'border-dashed border-brand bg-brand/5' : 'border-hairline bg-paper'
        }`}
      >
        <img src={preview} alt="معاينة صورة المنتج" className="size-28 shrink-0 rounded-xl bg-paper-2 object-contain" />
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-semibold text-ink">
            <Check className="size-4 text-brand" strokeWidth={2.5} aria-hidden="true" />
            الصورة جاهزة
          </p>
          <p className="mt-1 truncate font-mono text-[12px] text-ink-muted" dir="ltr">
            {file.name} · {formatSize(file.size)}
          </p>
          <p className="mt-1 text-[12px] text-ink-muted">{dragging ? 'أفلت لاستبدال الصورة' : 'اسحب صورة أخرى هنا لاستبدالها'}</p>
          <button
            type="button"
            onClick={() => {
              onFile(null);
              if (inputRef.current) inputRef.current.value = '';
            }}
            className="mt-3 inline-flex items-center gap-1.5 rounded-md text-sm font-medium text-ink-muted transition-colors duration-150 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal"
          >
            <X className="size-4" aria-hidden="true" />
            إزالة الصورة
          </button>
        </div>
      </div>
    );
  }

  return (
    <label
      {...dropProps}
      className={`group flex h-full min-h-56 flex-col items-center justify-center gap-3 rounded-2xl border border-dashed px-6 text-center transition-[background-color,border-color] duration-200 has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-signal ${
        dragging ? 'border-brand bg-brand/5' : error ? 'border-signal/60 bg-paper' : 'border-ink/20 bg-paper hover:border-brand/50'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={IMAGE_TYPES.join(',')}
        className="sr-only"
        aria-describedby={hintId}
        onChange={(e) => take(e.target.files)}
      />
      <span
        className={`grid size-12 place-items-center rounded-xl transition-[background-color,color,scale] duration-200 ${
          dragging ? 'scale-110 bg-brand text-white' : 'bg-paper-2 text-brand group-hover:scale-105'
        }`}
      >
        <ImagePlus className="size-6" strokeWidth={1.75} aria-hidden="true" />
      </span>
      <span className="text-[15px] font-semibold text-ink">{dragging ? 'أفلت الصورة هنا' : 'اسحب صورة المنتج هنا'}</span>
      <span id={hintId} className="text-sm text-ink-muted">
        أو <span className="text-brand underline underline-offset-4">اختر من جهازك</span> · JPG أو PNG أو WebP حتى {MAX_MB}MB
      </span>
    </label>
  );
}

export default function ProductInput({ onAnalyze, busy = false }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const previewRef = useRef(null);
  const handedOffRef = useRef(null); // preview of the last submitted photo, shown in the analysis view
  useEffect(
    () => () => {
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
      if (handedOffRef.current) URL.revokeObjectURL(handedOffRef.current);
    },
    [],
  );

  // A file dropped just outside the drop zone would make the browser open it and leave the site.
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
  };
  const [name, setName] = useState('');
  const [error, setError] = useState('');
  const nameId = useId();
  const canSubmit = (file || name.trim().length > 1) && !busy;

  const onFile = (f) => {
    if (!f) return setImage(null);
    if (!isSupportedImage(f)) return setError('نوع الملف غير مدعوم. استخدم صورة JPG أو PNG أو WebP.');
    if (f.size > MAX_MB * 1024 * 1024) return setError(`حجم الصورة أكبر من ${MAX_MB}MB.`);
    setError('');
    setImage(f);
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
      <div className="mx-auto max-w-[1320px] px-5 py-24 md:px-10 md:py-32">
        <div className="max-w-[640px]">
          <p className="flex items-center gap-2.5 text-[13px] font-medium text-ink-muted">
            <span aria-hidden="true" className="inline-block size-1.5 bg-signal" />
            الخطوة الأولى
          </p>
          <h2
            id="product-input-title"
            tabIndex={-1}
            data-autofocus
            className="mt-4 font-display text-[clamp(2rem,1.2rem+2.4vw,3rem)] leading-[1.25] font-semibold text-ink outline-none"
          >
            ابدأ من منتجك
          </h2>
          <p className="mt-4 text-[1.0625rem] leading-[1.9] text-ink-muted">
            صورة واضحة للمنتج أو اسمه يكفيان لنبدأ. كلما كان الوصف أدق، كان التقييم أدق.
          </p>
        </div>

        <form
          onSubmit={onSubmit}
          noValidate
          className="mt-12 rounded-[28px] border border-hairline bg-white/70 p-4 shadow-[0_1px_0_rgb(255_255_255/0.8)_inset,0_30px_60px_-40px_rgb(14_23_38/0.35)] backdrop-blur-sm md:p-6"
        >
          <div className="grid items-stretch gap-4 md:grid-cols-[1fr_auto_1fr] md:gap-6">
            <ImageDrop
              file={file}
              preview={preview}
              onFile={onFile}
              onNoFile={() => setError('لم تصل الصورة. اسحبها من ملفات جهازك، أو اضغط لاختيارها.')}
              error={error}
            />

            <div className="flex items-center justify-center gap-3 text-[13px] text-ink-muted md:flex-col" aria-hidden="true">
              <span className="h-px w-12 bg-ink/12 md:h-12 md:w-px" />
              أو
              <span className="h-px w-12 bg-ink/12 md:h-12 md:w-px" />
            </div>

            <div className="flex flex-col justify-center rounded-2xl border border-hairline bg-paper p-5 md:p-6">
              <label htmlFor={nameId} className="flex items-baseline justify-between gap-3">
                <span className="text-[15px] font-semibold text-ink">اسم المنتج أو وصفه</span>
                <span className="font-mono text-[11px] text-ink-muted" dir="ltr">
                  {name.length}/280
                </span>
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
                placeholder="مثال: رفوف حديدية لتخزين البضائع في المستودعات، بأحمال ثقيلة وارتفاع 4 أمتار"
                autoComplete="off"
                className="mt-3 w-full resize-none rounded-xl border border-ink/15 bg-white px-4 py-3 text-[16px] leading-[1.8] text-ink transition-[border-color,box-shadow] duration-150 placeholder:text-ink-muted/60 focus:border-brand focus:shadow-[0_0_0_4px_rgb(30_79_214/0.12)] focus:outline-none"
              />
              <div className="mt-4 flex flex-wrap gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s}
                    type="button"
                    onClick={() => {
                      setName(s);
                    }}
                    className={`rounded-full border px-3 py-1.5 text-[13px] transition-[background-color,border-color,color,scale] duration-150 active:scale-[0.97] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-signal ${
                      name === s
                        ? 'border-brand bg-brand/8 text-brand'
                        : 'border-ink/12 bg-white text-ink-muted hover:border-ink/25 hover:text-ink'
                    }`}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-5 flex flex-col gap-4 border-t border-hairline px-1 pt-5 md:flex-row md:items-center md:justify-between">
            <p className="min-h-6 text-sm" role="status" aria-live="polite">
              {error ? (
                <span className="text-[#b4400e]">{error}</span>
              ) : busy ? (
                <span className="text-ink">
                  <Check className="me-1.5 inline size-4 text-brand" strokeWidth={2.5} aria-hidden="true" />
                  نحلّل «{label}» الآن…
                </span>
              ) : (
                <span className="text-ink-muted">نستخدم الصورة أو الاسم فقط لتقييم المنتج.</span>
              )}
            </p>
            <button
              type="submit"
              disabled={!canSubmit}
              className="group inline-flex h-13 items-center justify-center gap-3 rounded-[14px] bg-brand px-7 font-display text-[1.0625rem] font-semibold text-white shadow-[inset_0_1px_0_rgb(255_255_255/0.22),0_16px_32px_-16px_rgb(19_50_143/0.8)] transition-[background-color,opacity,scale] duration-150 ease-(--ease-out) hover:bg-brand-deep focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal active:scale-[0.97] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-brand"
            >
              {busy ? 'جارٍ التحليل…' : 'حلّل المنتج'}
              <ArrowLeft
                className={`size-[18px] transition-transform duration-200 ease-(--ease-out) group-hover:-translate-x-1 ${
                  busy ? 'animate-pulse' : ''
                }`}
                strokeWidth={2.25}
                aria-hidden="true"
              />
            </button>
          </div>
        </form>
      </div>
    </section>
  );
}
