import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Camera, Upload, AlertTriangle, TrendingUp,
  DollarSign, Wrench, CheckCircle2, XCircle, FileDown,
  Sparkles, ChevronDown, Settings, Search, ArrowLeft,
  Shield, Zap, BarChart3, Package, Factory, Eye,
  ChevronLeft, Menu, X
} from 'lucide-react';
import { SAMPLE_PRODUCTS } from './sampleData';

/* ────────────────────────────────────────────
   GEAR SVG COMPONENT (for intro animation)
   ──────────────────────────────────────────── */
function GearSVG({ size = 80, className = '' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 100 100" className={className}>
      <path
        d="M50 10 L54 10 L56 18 L62 16 L64 12 L68 14 L66 22 L72 26 L78 22 L80 26 L74 32 L78 38 L86 38 L86 42 L78 44 L80 50 L88 54 L86 58 L78 56 L76 62 L82 68 L78 72 L72 66 L66 72 L68 80 L64 82 L60 74 L54 76 L54 84 L50 84 L48 76 L42 78 L40 84 L36 82 L38 74 L32 70 L26 76 L22 72 L28 66 L24 60 L16 58 L16 54 L24 52 L22 46 L14 42 L16 38 L24 40 L28 34 L22 28 L26 24 L32 30 L38 26 L36 18 L40 16 L44 24 L50 22Z"
        fill="currentColor"
        opacity="0.9"
      />
      <circle cx="50" cy="50" r="16" fill="#f0f4f8" />
    </svg>
  );
}

/* ────────────────────────────────────────────
   FLOATING SHAPES (background decoration)
   ──────────────────────────────────────────── */
function FloatingShapes() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="absolute top-[10%] right-[5%] w-20 h-20 bg-blue-500/5 rounded-full animate-float-slow" />
      <div className="absolute top-[30%] left-[10%] w-14 h-14 bg-blue-400/8 rounded-2xl rotate-45 animate-float" style={{ animationDelay: '2s' }} />
      <div className="absolute bottom-[20%] right-[15%] w-10 h-10 bg-blue-300/10 rounded-full animate-float" style={{ animationDelay: '1s' }} />
      <div className="absolute top-[60%] left-[5%] w-24 h-24 bg-blue-200/5 rounded-full animate-float-slow" style={{ animationDelay: '3s' }} />
      <div className="absolute bottom-[40%] right-[40%] w-6 h-6 bg-blue-600/8 rounded-full animate-float" style={{ animationDelay: '4s' }} />
    </div>
  );
}

/* ────────────────────────────────────────────
   SCORE CIRCLE COMPONENT
   ──────────────────────────────────────────── */
function ScoreCircle({ score, size = 140 }) {
  const percent = (score / 10) * 100;
  const dashOffset = 283 - (283 * percent) / 100;
  const color = score >= 7 ? '#10b981' : score >= 5 ? '#f59e0b' : '#ef4444';

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox="0 0 100 100">
        <circle cx="50" cy="50" r="45" className="score-circle-bg" />
        <circle
          cx="50" cy="50" r="45"
          className="score-circle-fill"
          stroke={color}
          style={{ '--dash-offset': dashOffset }}
        />
      </svg>
      <div className="absolute flex flex-col items-center">
        <span className="text-3xl font-black" style={{ color }}>{score}</span>
        <span className="text-xs text-slate-400 font-bold">/10</span>
      </div>
    </div>
  );
}

/* ────────────────────────────────────────────
   useScrollReveal HOOK
   ──────────────────────────────────────────── */
function useScrollReveal(threshold = 0.15) {
  const ref = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setIsVisible(true); },
      { threshold }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [threshold]);

  return [ref, isVisible];
}

/* ────────────────────────────────────────────
   useCardReveal HOOK - for staggered card animations
   ──────────────────────────────────────────── */
function useCardReveal() {
  const ref = useRef(null);
  const [visibleCards, setVisibleCards] = useState(new Set());

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    const cards = el.querySelectorAll('.result-card');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            const idx = entry.target.dataset.cardIndex;
            setVisibleCards(prev => new Set([...prev, idx]));
          }
        });
      },
      { threshold: 0.2 }
    );

    cards.forEach(card => observer.observe(card));
    return () => observer.disconnect();
  }, []);

  return [ref, visibleCards];
}

/* ════════════════════════════════════════════
   MAIN APP COMPONENT
   ════════════════════════════════════════════ */
export default function App() {
  const [introVisible, setIntroVisible] = useState(true);
  const [introFading, setIntroFading] = useState(false);
  const [result, setResult] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisStep, setAnalysisStep] = useState(0);
  const [demoMode, setDemoMode] = useState(true);
  const [mobileMenu, setMobileMenu] = useState(false);

  // Intro auto-dismiss after assembly animation
  useEffect(() => {
    const t1 = setTimeout(() => setIntroFading(true), 3200);
    const t2 = setTimeout(() => setIntroVisible(false), 4000);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, []);

  // Analysis simulation
  const runAnalysis = useCallback((productIndex = 0) => {
    setResult(null);
    setAnalyzing(true);
    setAnalysisStep(0);

    const steps = [1, 2, 3, 4];
    steps.forEach((step, i) => {
      setTimeout(() => setAnalysisStep(step), (i + 1) * 700);
    });

    setTimeout(() => {
      setAnalyzing(false);
      setAnalysisStep(0);
      setResult(SAMPLE_PRODUCTS[productIndex]);
      document.getElementById('results')?.scrollIntoView({ behavior: 'smooth' });
    }, 3500);
  }, []);

  const handleDownloadDataReport = () => {
    if (!result) return;
    const reportContent = `=====================================================
تقرير تحليل الجدوى الصناعية - منصة صنّعها (الأردن)
تاريخ التقرير: ${new Date().toLocaleDateString('ar-JO')}
=====================================================

1. بيانات المنتج الرسمية:
-----------------------------------------------------
- اسم المنتج: ${result.productName}
- رمز النظام المنسق الدولي (HS6): ${result.hsCode}
- القرار النهائي: ${result.decision === 'صنّعها' ? 'صنّعها (مُجدٍ محلياً)' : 'لا (غير مُجدٍ محلياً)'}
- مؤشر التقييم الإجمالي: ${result.score} من 10

2. معادلة الاحتساب وتفصيل السكور:
-----------------------------------------------------
- طريقة الحساب: ${result.calculationBreakdown?.formula || 'حساب متعدد المعايير'}
- تفسير النتيجة: ${result.calculationBreakdown?.explanation || ''}

3. البيانات الرقمية الحقيقية (Real Dataset):
-----------------------------------------------------
• حجم السوق والواردات (5 سنوات):
  - القيمة: ${result.market.imports5Years}
  - الوصف: ${result.market.sizeDescription}
  - اتجاه النمو: ${result.market.trend}
  - المصدر: دائرة الإحصاءات العامة الأردنية (DOS)

• الكلفة والجمارك:
  - نسبة الرسوم الجمركية: ${result.cost.customsDuty}
  - كلفة شحن الكيلوغرام المستورد: ${result.cost.shippingEstimate}
  - وفر الكلفة على المصنع المحلي: ${result.cost.savingsNote}
  - المصدر: جدول التعرفة الجمركية الأردنية الرسمية

• جاهزية الورش والمعدات:
  - المكائن والمعدات المطلوبة: ${result.manufacturing.machines}
  - المواد الخام المتوفرة: ${result.manufacturing.rawMaterials}
  - جاهزية الورش المحلية: ${result.manufacturing.workshopsStatus}
  - المصدر: غرفة صناعة الأردن وغرفة صناعة عمان

4. تدقيق المخاطر وإيجنت التشكيك (Skeptic Analysis):
-----------------------------------------------------
عنوان التحذيرات: ${result.skeptic.warningTitle}
الأسباب الواقعية ضد القرار والمخاطر:
${result.skeptic.reasons.map((r, i) => `  ${i + 1}. ${r}`).join('\n')}

=====================================================
تم استخراج هذا التقرير آلياً عبر منصة "صنّعها" - هاكثون إحلال المستوردات
=====================================================`;

    const blob = new Blob([reportContent], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `تقرير_صنّعها_${result.productName.split(' ')[0]}_${result.hsCode}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleFileUpload = (e) => {
    if (e.target.files?.[0]) runAnalysis(Math.floor(Math.random() * SAMPLE_PRODUCTS.length));
  };

  /* ─── SCROLL REVEAL REFS ─── */
  const [heroRef, heroVisible] = useScrollReveal();
  const [howRef, howVisible] = useScrollReveal();
  const [uploadRef, uploadVisible] = useScrollReveal();
  const [analysisRef, analysisVisible] = useScrollReveal();
  const [resultsRef, resultsVisible] = useScrollReveal();
  const [footerRef, footerVisible] = useScrollReveal();

  /* ═══════════════════════════════════════
     RENDER
     ═══════════════════════════════════════ */
  return (
    <div className="min-h-screen" dir="rtl">

      {/* ████████ INTRO SCREEN ████████ */}
      {introVisible && (
        <div
          className={`fixed inset-0 z-50 bg-gradient-to-br from-slate-900 via-blue-950 to-slate-900 flex flex-col items-center justify-center ${
            introFading ? 'animate-intro-slide-up' : ''
          }`}
        >
          {/* Background particles */}
          <div className="absolute inset-0 overflow-hidden">
            {[...Array(20)].map((_, i) => (
              <div
                key={i}
                className="absolute w-1 h-1 bg-blue-400/30 rounded-full animate-float"
                style={{
                  top: `${Math.random() * 100}%`,
                  left: `${Math.random() * 100}%`,
                  animationDelay: `${Math.random() * 5}s`,
                  animationDuration: `${4 + Math.random() * 4}s`,
                }}
              />
            ))}
          </div>

          {/* Gears assembling */}
          <div className="relative w-64 h-64 flex items-center justify-center mb-8">
            {/* Gear 1 - top right */}
            <div
              className="absolute text-blue-400/60"
              style={{
                animation: 'converge 1.2s ease-out 0.3s forwards, gearSpin 8s linear 1.5s infinite',
                opacity: 0,
                top: '0%',
                right: '5%',
              }}
            >
              <GearSVG size={70} />
            </div>

            {/* Gear 2 - bottom left */}
            <div
              className="absolute text-blue-300/50"
              style={{
                animation: 'converge 1.2s ease-out 0.6s forwards, gearSpinReverse 6s linear 1.8s infinite',
                opacity: 0,
                bottom: '5%',
                left: '5%',
              }}
            >
              <GearSVG size={55} />
            </div>

            {/* Gear 3 - center small */}
            <div
              className="absolute text-blue-500/70"
              style={{
                animation: 'converge 1.2s ease-out 0.9s forwards, gearSpin 5s linear 2.1s infinite',
                opacity: 0,
                top: '35%',
                left: '30%',
              }}
            >
              <GearSVG size={40} />
            </div>

            {/* Gear 4 - top left */}
            <div
              className="absolute text-blue-200/40"
              style={{
                animation: 'converge 1.2s ease-out 0.2s forwards, gearSpinReverse 10s linear 1.4s infinite',
                opacity: 0,
                top: '10%',
                left: '10%',
              }}
            >
              <GearSVG size={50} />
            </div>

            {/* Gear 5 - bottom right */}
            <div
              className="absolute text-blue-400/50"
              style={{
                animation: 'converge 1.2s ease-out 0.5s forwards, gearSpin 7s linear 1.7s infinite',
                opacity: 0,
                bottom: '10%',
                right: '15%',
              }}
            >
              <GearSVG size={45} />
            </div>
          </div>

          {/* Logo text assembles */}
          <div
            className="text-center"
            style={{ animation: 'fadeSlideUp 1s ease-out 1.8s forwards', opacity: 0 }}
          >
            <h1 className="text-6xl md:text-8xl font-black text-white tracking-tight">
              صنّعها
            </h1>
            <div
              className="flex items-center justify-center gap-2 mt-3"
              style={{ animation: 'fadeIn 0.8s ease-out 2.5s forwards', opacity: 0 }}
            >
              <span className="text-blue-300 text-lg font-semibold">من الفكرة إلى المصنع</span>
              <span className="text-2xl">🇯🇴</span>
            </div>
          </div>

          {/* Loading bar */}
          <div
            className="w-48 h-1 bg-white/10 rounded-full mt-8 overflow-hidden"
            style={{ animation: 'fadeIn 0.5s ease-out 2s forwards', opacity: 0 }}
          >
            <div className="h-full bg-gradient-to-l from-blue-400 to-emerald-400 rounded-full" style={{ animation: 'progressFill 1s ease-out 2.2s forwards', width: 0, '--progress': '100%' }} />
          </div>
        </div>
      )}

      {/* ████████ NAVBAR ████████ */}
      <nav className="fixed top-0 left-0 right-0 z-40 bg-white/90 backdrop-blur-lg border-b border-slate-200/80 shadow-sm no-print">
        <div className="max-w-7xl mx-auto px-4 md:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-blue-700 rounded-xl flex items-center justify-center text-white font-black text-lg shadow-md">
              ص
            </div>
            <span className="text-lg font-black text-slate-800">صنّعها</span>
          </div>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-8 text-sm font-semibold text-slate-600">
            <a href="#how" className="hover:text-blue-700 transition-colors">كيف يعمل</a>
            <a href="#upload" className="hover:text-blue-700 transition-colors">التحليل</a>
            <a href="#results" className="hover:text-blue-700 transition-colors">النتائج</a>
            <a href="#footer" className="hover:text-blue-700 transition-colors">عنّا</a>
          </div>

          <div className="flex items-center gap-3">
            {/* Demo toggle */}
            <div className="hidden md:flex items-center gap-2 bg-slate-100 px-3 py-1.5 rounded-full border border-slate-200">
              <Sparkles className="w-3.5 h-3.5 text-amber-500" />
              <span className="text-[11px] font-bold text-slate-600">Demo</span>
              <button
                onClick={() => setDemoMode(!demoMode)}
                className={`w-9 h-5 flex items-center rounded-full p-0.5 transition-colors cursor-pointer ${demoMode ? 'bg-blue-600' : 'bg-slate-300'}`}
              >
                <div className={`bg-white w-4 h-4 rounded-full shadow-md transition-transform ${demoMode ? '-translate-x-4' : ''}`} />
              </button>
            </div>

            <a href="#upload" className="bg-blue-700 hover:bg-blue-800 text-white px-5 py-2 rounded-xl text-sm font-bold transition-colors flex items-center gap-1.5">
              ابدأ الآن <ArrowLeft className="w-4 h-4" />
            </a>

            {/* Mobile menu */}
            <button onClick={() => setMobileMenu(!mobileMenu)} className="md:hidden text-slate-700 cursor-pointer">
              {mobileMenu ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
            </button>
          </div>
        </div>

        {/* Mobile dropdown */}
        {mobileMenu && (
          <div className="md:hidden bg-white border-t border-slate-200 px-4 py-4 space-y-3 text-sm font-semibold text-slate-700">
            <a href="#how" onClick={() => setMobileMenu(false)} className="block py-2">كيف يعمل</a>
            <a href="#upload" onClick={() => setMobileMenu(false)} className="block py-2">التحليل</a>
            <a href="#results" onClick={() => setMobileMenu(false)} className="block py-2">النتائج</a>
          </div>
        )}
      </nav>

      {/* ████████ HERO SECTION ████████ */}
      <section
        ref={heroRef}
        className={`relative min-h-screen flex items-center pt-16 overflow-hidden bg-gradient-to-bl from-[#0c1e3a] via-[#0f2d5e] to-[#0a1628] ${heroVisible ? 'section-visible' : 'section-hidden'}`}
      >
        <FloatingShapes />

        {/* Grid overlay */}
        <div className="absolute inset-0 bg-grid opacity-30" />

        {/* Gradient orbs */}
        <div className="absolute top-[20%] left-[60%] w-[500px] h-[500px] bg-blue-600/10 rounded-full blur-3xl" />
        <div className="absolute bottom-[10%] right-[70%] w-[400px] h-[400px] bg-blue-400/5 rounded-full blur-3xl" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 md:px-8 w-full grid md:grid-cols-2 gap-10 items-center py-20">
          {/* Text content */}
          <div className="text-right space-y-6">
            <div className="inline-flex items-center gap-2 bg-white/10 border border-white/20 text-blue-200 px-4 py-1.5 rounded-full text-sm font-semibold backdrop-blur-md">
              <Sparkles className="w-4 h-4 text-amber-400" /> من الفكرة إلى القرار
            </div>

            <h1 className="text-4xl md:text-6xl font-black text-white leading-tight tracking-tight">
              هل يستحق هذا المنتج
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-l from-blue-300 to-emerald-300">
                التصنيع محلياً؟
              </span>
            </h1>

            <p className="text-lg text-blue-200/80 max-w-lg leading-relaxed font-medium">
              أدخل منتجك واحصل على تحليل سريع وموضوعي لإمكانية تصنيعه محلياً، مع توضيح التكاليف والمواد والمعدات والفرص المتاحة.
            </p>

            <div className="flex flex-wrap gap-3 pt-2">
              <a href="#upload" className="bg-white text-blue-900 hover:bg-blue-50 px-7 py-3.5 rounded-xl text-base font-black transition-all flex items-center gap-2 shadow-lg shadow-blue-900/30 hover:shadow-xl">
                ابدأ الآن <ArrowLeft className="w-5 h-5" />
              </a>
              <a href="#how" className="border-2 border-white/30 text-white hover:bg-white/10 px-7 py-3.5 rounded-xl text-base font-bold transition-all flex items-center gap-2">
                اسحب للأسفل <ChevronDown className="w-5 h-5 animate-bounce-subtle" />
              </a>
            </div>
          </div>

          {/* Hero visual - animated gears */}
          <div className="relative hidden md:flex items-center justify-center h-[420px]">
            <div className="absolute text-blue-400/20 animate-gear-spin" style={{ top: '5%', right: '10%' }}>
              <GearSVG size={160} />
            </div>
            <div className="absolute text-blue-300/15 animate-gear-spin-reverse" style={{ bottom: '10%', left: '5%' }}>
              <GearSVG size={120} />
            </div>
            <div className="absolute text-blue-500/25 animate-gear-spin" style={{ top: '40%', right: '45%' }}>
              <GearSVG size={80} />
            </div>
            <div className="absolute text-emerald-400/15 animate-gear-spin-reverse" style={{ top: '15%', left: '20%' }}>
              <GearSVG size={60} />
            </div>
            {/* Center icon */}
            <div className="relative z-10 w-32 h-32 bg-white/10 backdrop-blur-xl rounded-3xl border border-white/20 flex items-center justify-center animate-float shadow-2xl shadow-blue-500/20">
              <Factory className="w-16 h-16 text-white" />
            </div>
          </div>
        </div>

        {/* Bottom features strip */}
        <div className="absolute bottom-0 left-0 right-0 bg-white/5 backdrop-blur-lg border-t border-white/10">
          <div className="max-w-7xl mx-auto px-4 md:px-8 py-5 grid grid-cols-3 gap-4 text-center">
            {[
              { icon: <Shield className="w-5 h-5" />, title: "بيانات موثوقة", sub: "من مصادر حقيقية" },
              { icon: <Zap className="w-5 h-5" />, title: "نتائج خلال دقائق", sub: "بسرعة وسهولة" },
              { icon: <BarChart3 className="w-5 h-5" />, title: "تحليل شامل", sub: "أربعة عوامل رئيسية" },
            ].map((f, i) => (
              <div key={i} className="flex flex-col items-center gap-1.5 text-white/80">
                <div className="w-10 h-10 bg-white/10 rounded-xl flex items-center justify-center">{f.icon}</div>
                <span className="text-xs md:text-sm font-bold">{f.title}</span>
                <span className="text-[10px] text-white/50 font-medium">{f.sub}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ████████ HOW IT WORKS ████████ */}
      <section
        id="how"
        ref={howRef}
        className={`relative py-20 bg-white ${howVisible ? 'section-visible' : 'section-hidden'}`}
      >
        <FloatingShapes />
        <div className="relative z-10 max-w-7xl mx-auto px-4 md:px-8">
          <div className="text-center mb-14">
            <span className="inline-block bg-blue-50 text-blue-700 px-4 py-1 rounded-full text-sm font-bold border border-blue-200 mb-3">آلية العمل</span>
            <h2 className="text-3xl md:text-5xl font-black text-slate-900">كيف يعمل؟</h2>
          </div>

          <div className="grid md:grid-cols-4 gap-6 stagger-children section-visible">
            {[
              { n: "١", icon: <Package className="w-7 h-7" />, title: "أدخل المنتج", desc: "أضف صورة أو اسم المنتج المستورد الذي تريد تقييمه.", color: "blue" },
              { n: "٢", icon: <Search className="w-7 h-7" />, title: "نحلل ونحدد", desc: "نحدد كود HS6 والمواد والعمليات والمعدات اللازمة تلقائياً.", color: "indigo" },
              { n: "٣", icon: <BarChart3 className="w-7 h-7" />, title: "نقيّم الجدوى", desc: "نحسب التكاليف والجمارك ومؤشر الفرصة السوقية.", color: "emerald" },
              { n: "٤", icon: <CheckCircle2 className="w-7 h-7" />, title: "نقدم النتيجة", desc: "هل يُصنع محلياً؟ ولماذا؟ مع تقرير قابل للتحميل.", color: "amber" },
            ].map((step) => (
              <div key={step.n} className="relative bg-slate-50 rounded-2xl p-6 border border-slate-200 hover:border-blue-300 hover:shadow-lg transition-all group">
                <div className={`w-12 h-12 bg-${step.color}-100 text-${step.color}-700 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform`}>
                  {step.icon}
                </div>
                <div className="absolute top-4 left-4 w-8 h-8 bg-blue-700 text-white rounded-full flex items-center justify-center text-sm font-black">
                  {step.n}
                </div>
                <h3 className="text-lg font-black text-slate-900 mb-2">{step.title}</h3>
                <p className="text-sm text-slate-500 leading-relaxed font-medium">{step.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ████████ UPLOAD / INPUT SECTION ████████ */}
      <section
        id="upload"
        ref={uploadRef}
        className={`relative py-20 bg-slate-50 bg-grid ${uploadVisible ? 'section-visible' : 'section-hidden'}`}
      >
        <div className="relative z-10 max-w-5xl mx-auto px-4 md:px-8">
          <div className="text-center mb-10">
            <span className="inline-block bg-blue-50 text-blue-700 px-4 py-1 rounded-full text-sm font-bold border border-blue-200 mb-3">ابدأ التحليل</span>
            <h2 className="text-3xl md:text-4xl font-black text-slate-900">أدخل المنتج المستورد</h2>
          </div>

          {/* Demo quick picks */}
          {demoMode && (
            <div className="bg-blue-50/80 border border-blue-200 rounded-2xl p-4 mb-8 flex flex-col md:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-blue-900 text-sm font-bold">
                <Sparkles className="w-4 h-4 text-amber-500" />
                <span>أمثلة جاهزة للعرض السريع:</span>
              </div>
              <div className="flex flex-wrap gap-2">
                {SAMPLE_PRODUCTS.map((p, i) => (
                  <button
                    key={p.id}
                    onClick={() => runAnalysis(i)}
                    className="text-xs px-4 py-2 rounded-xl font-bold border cursor-pointer bg-white text-slate-700 border-blue-200 hover:bg-blue-700 hover:text-white hover:border-blue-700 transition-all"
                  >
                    {p.productName.split(' ').slice(0, 2).join(' ')}
                    <span className={`mr-1.5 text-[10px] px-1.5 py-0.5 rounded-md font-black ${p.decision === 'صنّعها' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                      {p.decision}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Upload cards */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Image upload */}
            <div className="relative bg-white rounded-3xl p-8 border-2 border-dashed border-slate-300 hover:border-blue-500 hover:shadow-xl transition-all group cursor-pointer">
              <input
                type="file"
                accept="image/*"
                onChange={handleFileUpload}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
              />
              <div className="flex flex-col items-center justify-center text-center gap-4 py-8">
                <div className="w-20 h-20 bg-blue-50 rounded-2xl flex items-center justify-center group-hover:scale-110 transition-transform">
                  <Camera className="w-10 h-10 text-blue-600" />
                </div>
                <div>
                  <h3 className="text-lg font-black text-slate-800">أضف صورة منتجك هنا</h3>
                  <p className="text-xs text-slate-400 mt-1">أو اسحب وأفلت الصورة</p>
                </div>
                <span className="inline-flex items-center gap-2 bg-slate-100 text-slate-600 px-4 py-2 rounded-xl text-xs font-bold group-hover:bg-blue-600 group-hover:text-white transition-colors">
                  <Upload className="w-4 h-4" /> اختر صورة
                </span>
              </div>
            </div>

            {/* Text input */}
            <div className="bg-white rounded-3xl p-8 border border-slate-200 shadow-sm flex flex-col justify-between">
              <div className="space-y-5">
                <div>
                  <label className="text-sm font-bold text-slate-700 block mb-2">أو أدخل اسم المنتج</label>
                  <div className="relative">
                    <input
                      type="text"
                      placeholder="مثال: كرسي معدني مكتبي"
                      className="w-full bg-slate-50 border border-slate-200 rounded-xl px-4 py-3.5 text-sm font-medium text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
                    />
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400" />
                  </div>
                </div>

                <div className="flex flex-wrap gap-2">
                  <span className="text-xs text-slate-400 font-medium">اقتراحات:</span>
                  {['كرسي معدني', 'رفوف مستودعات', 'مراوح سقفية'].map((s) => (
                    <button
                      key={s}
                      onClick={() => runAnalysis(SAMPLE_PRODUCTS.findIndex(p => p.productName.includes(s.split(' ')[0])) || 0)}
                      className="text-[11px] bg-slate-100 hover:bg-blue-100 text-slate-600 hover:text-blue-700 px-3 py-1 rounded-lg font-semibold transition-colors cursor-pointer"
                    >
                      {s}
                    </button>
                  ))}
                </div>
              </div>

              <button
                onClick={() => runAnalysis(0)}
                className="mt-6 w-full bg-blue-700 hover:bg-blue-800 text-white py-3.5 rounded-xl font-black text-base flex items-center justify-center gap-2 transition-all cursor-pointer shadow-lg shadow-blue-200 hover:shadow-xl"
              >
                <ArrowLeft className="w-5 h-5" />
                تحليل المنتج
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* ████████ ANALYSIS LOADING ████████ */}
      {analyzing && (
        <section className="py-20 bg-white">
          <div className="max-w-4xl mx-auto px-4 md:px-8 text-center">
            <div className="mb-8">
              <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-blue-600 border-t-transparent mb-4"></div>
              <h2 className="text-2xl md:text-3xl font-black text-slate-900">جاري تحليل المنتج...</h2>
              <p className="text-sm text-slate-500 mt-2 font-medium">نقوم الآن بدراسة جميع الجوانب للحصول على أفضل نتيجة.</p>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[
                { icon: <Eye className="w-6 h-6" />, name: "الفرص السوقية", step: 1 },
                { icon: <Settings className="w-6 h-6" />, name: "المعدات", step: 2 },
                { icon: <Wrench className="w-6 h-6" />, name: "العمليات التصنيعية", step: 3 },
                { icon: <Package className="w-6 h-6" />, name: "المواد", step: 4 },
              ].map((item) => (
                <div key={item.step} className={`bg-slate-50 rounded-2xl p-5 border transition-all duration-500 ${
                  analysisStep >= item.step ? 'border-blue-300 shadow-md' : 'border-slate-200'
                }`}>
                  <div className={`w-12 h-12 mx-auto rounded-xl flex items-center justify-center mb-3 transition-colors duration-500 ${
                    analysisStep >= item.step ? 'bg-blue-100 text-blue-700' : 'bg-slate-200 text-slate-400'
                  }`}>
                    {analysisStep >= item.step ? <CheckCircle2 className="w-6 h-6 text-blue-600" /> : item.icon}
                  </div>
                  <p className="text-sm font-bold text-slate-800">{item.name}</p>
                  <p className="text-xs text-slate-400 mt-1 font-medium">
                    {analysisStep >= item.step ? 'تم التحليل ✓' : 'جاري التحليل...'}
                  </p>

                  {/* Progress bar */}
                  <div className="w-full h-1.5 bg-slate-200 rounded-full mt-3 overflow-hidden">
                    <div className={`h-full rounded-full transition-all duration-700 ${
                      analysisStep >= item.step ? 'bg-blue-600 w-full' : 'bg-slate-300 w-1/4'
                    }`} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* ████████ RESULTS SECTION ████████ */}
      {result && !analyzing && (
        <section
          id="results"
          ref={resultsRef}
          className="py-20 bg-white relative overflow-hidden"
        >
          <FloatingShapes />

          {/* Animated background burst when results appear */}
          <div className="absolute inset-0 pointer-events-none">
            <div
              className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[800px] h-[800px] rounded-full"
              style={{
                background: result.decision === 'صنّعها'
                  ? 'radial-gradient(circle, rgba(16,185,129,0.08) 0%, transparent 70%)'
                  : 'radial-gradient(circle, rgba(239,68,68,0.08) 0%, transparent 70%)',
                animation: 'scaleIn 1.2s ease-out forwards',
              }}
            />
          </div>

          <div className="relative z-10 max-w-6xl mx-auto px-4 md:px-8 space-y-10">

            {/* ── VERDICT HERO: Reveals from center like opening a box ── */}
            <div
              className={`animate-reveal-center rounded-3xl p-8 md:p-10 border-2 shadow-xl relative overflow-hidden ${
                result.decision === 'صنّعها'
                  ? 'bg-gradient-to-bl from-emerald-50 via-white to-emerald-50/30 border-emerald-200'
                  : 'bg-gradient-to-bl from-rose-50 via-white to-rose-50/30 border-rose-200'
              }`}
            >
              {/* Shimmer line across top */}
              <div className="absolute top-0 left-0 right-0 h-1 animate-shimmer rounded-t-3xl"
                style={{ background: result.decision === 'صنّعها'
                  ? 'linear-gradient(90deg, transparent 30%, rgba(16,185,129,0.5) 50%, transparent 70%)'
                  : 'linear-gradient(90deg, transparent 30%, rgba(239,68,68,0.5) 50%, transparent 70%)',
                  backgroundSize: '200% 100%',
                }}
              />

              <div className="flex flex-col md:flex-row items-center gap-8">
                {/* Score circle - pops in with spring */}
                <div className="animate-score-pop flex flex-col items-center justify-center p-3 bg-white/80 rounded-2xl border border-slate-100 shadow-sm" style={{ animationDelay: '0.4s', opacity: 0 }}>
                  <ScoreCircle score={result.score} size={150} />
                  <span className="text-xs font-black text-slate-500 mt-1">مؤشر الجدوى المحسوب</span>
                  <span className="text-[10px] text-blue-600 font-semibold">بناءً على الأرقام الحقيقية</span>
                </div>

                {/* Info - slides in */}
                <div className="flex-1 text-center md:text-right space-y-4" style={{ animation: 'slideRevealUp 0.8s cubic-bezier(0.16,1,0.3,1) 0.3s forwards', opacity: 0 }}>
                  {/* Verdict badge - stamps in */}
                  <div className="flex flex-wrap items-center justify-center md:justify-start gap-2">
                    <span
                      className={`animate-verdict-stamp inline-flex items-center gap-2 px-6 py-3 rounded-xl text-xl font-black shadow-lg ${
                        result.decision === 'صنّعها'
                          ? 'bg-emerald-600 text-white shadow-emerald-300 animate-glow-pulse'
                          : 'bg-rose-600 text-white shadow-rose-300 animate-glow-pulse-red'
                      }`}
                      style={{ animationDelay: '0.6s', opacity: 0 }}
                    >
                      {result.decision === 'صنّعها' ? <CheckCircle2 className="w-7 h-7" /> : <XCircle className="w-7 h-7" />}
                      قرار الإيجنت: {result.decision === 'صنّعها' ? 'صنّعها (مُجدٍ محلياً)' : 'لا (غير مُجدٍ محلياً)'}
                    </span>
                  </div>

                  <h2 className="text-2xl md:text-3xl font-black text-slate-900">{result.productName}</h2>

                  <div className="flex flex-wrap items-center justify-center md:justify-start gap-3">
                    <span className="bg-slate-100 text-slate-700 px-3 py-1.5 rounded-lg text-sm font-bold border border-slate-200">
                      رمز النظام المنسق HS6: {result.hsCode}
                    </span>
                    <span className="text-sm text-slate-600 font-medium">
                      {result.decision === 'صنّعها' 
                        ? '✅ أوصى الإيجنت بالتصنيع بناءً على وفر كلف الشحن وتوفر الورش الحرفية وحجم الواردات.'
                        : '❌ أوصى الإيجنت بعدم التصنيع نظراً لعدم وجود جدوى استثمارية لورشة ناشئة مقارنة بالمستورد أو المصانع القائمة.'}
                    </span>
                  </div>

                  {/* كيف حسبها الإيجنت (Calculation Breakdown Box) */}
                  {result.calculationBreakdown && (
                    <div className="bg-blue-50/80 border border-blue-200/90 rounded-2xl p-3.5 text-right space-y-1">
                      <div className="flex items-center gap-2 text-xs font-black text-blue-900">
                        <span>📐 كيف حسبها الإيجنت؟ (معادلة السكور):</span>
                      </div>
                      <p className="text-xs text-blue-800 font-mono font-bold bg-white/70 px-2.5 py-1.5 rounded-lg border border-blue-100">
                        {result.calculationBreakdown.formula}
                      </p>
                      <p className="text-[11px] text-slate-600 leading-relaxed pt-0.5">
                        {result.calculationBreakdown.explanation}
                      </p>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2 pt-2">
                    <button
                      onClick={handleDownloadDataReport}
                      className="inline-flex items-center gap-1.5 bg-blue-700 hover:bg-blue-800 text-white px-5 py-2.5 rounded-xl text-sm font-bold transition-colors cursor-pointer shadow-md hover:shadow-lg"
                    >
                      <FileDown className="w-4 h-4" /> تحميل ملف البيانات وطريقة الحساب (TXT)
                    </button>
                    <button
                      onClick={() => window.print()}
                      className="inline-flex items-center gap-1.5 bg-slate-100 hover:bg-slate-200 text-slate-700 border border-slate-200 px-4 py-2.5 rounded-xl text-sm font-bold transition-colors cursor-pointer"
                    >
                      طباعة
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* ── SECTION TITLE: unfolds down ── */}
            <div
              className="text-center animate-unfold-v"
              style={{ animationDelay: '0.5s', opacity: 0 }}
            >
              <h3 className="text-2xl md:text-3xl font-black text-slate-900">الأركان الأربعة لتحليل الإيجنت</h3>
              <p className="text-sm text-slate-500 mt-1 font-medium">بيانات رقمية حقيقية 100% بدون مؤشرات افتراضية</p>
              {/* Animated line */}
              <div className="mx-auto mt-4 h-0.5 bg-gradient-to-l from-transparent via-blue-400 to-transparent" style={{ animation: 'expandLine 1s ease-out 0.8s forwards', width: 0, maxWidth: '200px' }} />
            </div>

            {/* ── 4 FACTOR CARDS: Each flips in on scroll ── */}
            <div className="grid md:grid-cols-2 gap-6">

              {/* Card 1: Market */}
              <div
                className="result-card"
                data-card-index="0"
                ref={el => {
                  if (el) {
                    const observer = new IntersectionObserver(([e]) => {
                      if (e.isIntersecting) el.classList.add('card-visible');
                    }, { threshold: 0.2 });
                    observer.observe(el);
                  }
                }}
                style={{ transitionDelay: '0.1s' }}
              >
                <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm hover:shadow-xl hover:border-blue-300 transition-all group h-full">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 bg-blue-100 rounded-xl flex items-center justify-center group-hover:scale-110 group-hover:rotate-6 transition-all duration-300">
                        <TrendingUp className="w-6 h-6 text-blue-700" />
                      </div>
                      <div>
                        <h4 className="font-black text-slate-900">حجم الاستيراد والطلب (سوق)</h4>
                        <span className="text-[11px] text-slate-400 font-medium">بيانات التجارة الخارجية - DOS</span>
                      </div>
                    </div>
                    <span className="text-xs font-bold bg-blue-50 text-blue-700 px-2.5 py-1 rounded-lg border border-blue-200">سجل رسمي</span>
                  </div>
                  <div className="space-y-2 mt-4">
                    <p className="text-sm text-slate-800"><strong>إجمالي الواردات (5 سنوات):</strong> <span className="text-blue-700 font-black">{result.market.imports5Years}</span></p>
                    <p className="text-xs text-slate-500 leading-relaxed">{result.market.sizeDescription}</p>
                    <p className="text-xs font-bold text-emerald-600 pt-2">📈 اتجاه السوق: {result.market.trend}</p>
                  </div>
                </div>
              </div>

              {/* Card 2: Cost */}
              <div
                className="result-card"
                data-card-index="1"
                ref={el => {
                  if (el) {
                    const observer = new IntersectionObserver(([e]) => {
                      if (e.isIntersecting) el.classList.add('card-visible');
                    }, { threshold: 0.2 });
                    observer.observe(el);
                  }
                }}
                style={{ transitionDelay: '0.25s' }}
              >
                <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm hover:shadow-xl hover:border-amber-300 transition-all group h-full">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 bg-amber-100 rounded-xl flex items-center justify-center group-hover:scale-110 group-hover:-rotate-6 transition-all duration-300">
                        <DollarSign className="w-6 h-6 text-amber-700" />
                      </div>
                      <div>
                        <h4 className="font-black text-slate-900">الجمارك والشحن (كلفة)</h4>
                        <span className="text-[11px] text-slate-400 font-medium">جدول التعريفة الجمركية الأردنية</span>
                      </div>
                    </div>
                    <span className="text-xs font-bold bg-amber-50 text-amber-700 px-2.5 py-1 rounded-lg border border-amber-200">حماية جمركية</span>
                  </div>
                  <div className="space-y-2 mt-4">
                    <p className="text-sm text-slate-800"><strong>نسبة الرسوم الجمركية:</strong> <span className="text-amber-700 font-black">{result.cost.customsDuty}</span></p>
                    <p className="text-xs text-slate-500"><strong>كلفة شحن الكيلوغرام المستورد:</strong> {result.cost.shippingEstimate}</p>
                    <p className="text-xs text-slate-600 leading-relaxed pt-2">💡 ميزة الكلفة: {result.cost.savingsNote}</p>
                  </div>
                </div>
              </div>

              {/* Card 3: Manufacturing */}
              <div
                className="result-card"
                data-card-index="2"
                ref={el => {
                  if (el) {
                    const observer = new IntersectionObserver(([e]) => {
                      if (e.isIntersecting) el.classList.add('card-visible');
                    }, { threshold: 0.2 });
                    observer.observe(el);
                  }
                }}
                style={{ transitionDelay: '0.4s' }}
              >
                <div className="bg-white rounded-2xl p-6 border border-slate-200 shadow-sm hover:shadow-xl hover:border-indigo-300 transition-all group h-full">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 bg-indigo-100 rounded-xl flex items-center justify-center group-hover:scale-110 group-hover:rotate-6 transition-all duration-300">
                        <Wrench className="w-6 h-6 text-indigo-700" />
                      </div>
                      <div>
                        <h4 className="font-black text-slate-900">جاهزية الورش والمعدات (تصنيع)</h4>
                        <span className="text-[11px] text-slate-400 font-medium">مسح غرف الصناعة والورش</span>
                      </div>
                    </div>
                    <span className="text-xs font-bold bg-indigo-50 text-indigo-700 px-2.5 py-1 rounded-lg border border-indigo-200">القدرة المحلية</span>
                  </div>
                  <div className="space-y-2 mt-4 text-xs">
                    <p className="text-sm text-slate-800"><strong>المكائن والمعدات المطلوبة:</strong></p>
                    <p className="text-slate-600 bg-slate-50 p-2.5 rounded-xl border border-slate-100 leading-relaxed">{result.manufacturing.machines}</p>
                    <p className="text-sm text-slate-800 pt-1"><strong>المواد الخام وسلاسل التوريد:</strong></p>
                    <p className="text-slate-600 leading-relaxed">{result.manufacturing.rawMaterials}</p>
                    <p className="text-xs font-bold text-indigo-700 pt-2">🏭 واقع الورش: {result.manufacturing.workshopsStatus}</p>
                  </div>
                </div>
              </div>

              {/* Card 4: Skeptic */}
              <div
                className="result-card"
                data-card-index="3"
                ref={el => {
                  if (el) {
                    const observer = new IntersectionObserver(([e]) => {
                      if (e.isIntersecting) el.classList.add('card-visible');
                    }, { threshold: 0.2 });
                    observer.observe(el);
                  }
                }}
                style={{ transitionDelay: '0.55s' }}
              >
                <div className="bg-amber-50/60 rounded-2xl p-6 border border-amber-200 shadow-sm hover:shadow-xl transition-all group h-full">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-12 h-12 bg-amber-200/60 rounded-xl flex items-center justify-center group-hover:scale-110 group-hover:-rotate-6 transition-all duration-300">
                        <AlertTriangle className="w-6 h-6 text-amber-700" />
                      </div>
                      <div>
                        <h4 className="font-black text-amber-900">إيجنت التشكيك والمخاطر (مشكك)</h4>
                        <span className="text-[11px] text-amber-700/60 font-medium">أسباب واقعية ضد القرار</span>
                      </div>
                    </div>
                    <span className="text-xs font-bold bg-amber-200 text-amber-900 px-2.5 py-1 rounded-lg">تدقيق المخاطر</span>
                  </div>
                  <p className="text-xs text-amber-800 font-bold mb-3">{result.skeptic.warningTitle}</p>
                  <ul className="space-y-2">
                    {result.skeptic.reasons.map((r, i) => (
                      <li key={i} className="flex items-start gap-2 bg-white/80 p-3 rounded-xl border border-amber-200/50 text-xs text-amber-900 leading-relaxed font-medium">
                        <span className="text-amber-600 font-bold mt-0.5">⚠</span>
                        {r}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

            </div>
          </div>
        </section>
      )}

      {/* ████████ FOOTER ████████ */}
      <footer
        id="footer"
        ref={footerRef}
        className={`relative bg-gradient-to-bl from-[#0c1e3a] via-[#0f2d5e] to-[#0a1628] text-white py-16 overflow-hidden ${footerVisible ? 'section-visible' : 'section-hidden'}`}
      >
        <div className="absolute inset-0 bg-grid opacity-10" />
        <div className="relative z-10 max-w-5xl mx-auto px-4 md:px-8 text-center space-y-6">
          <div className="flex items-center justify-center gap-3">
            <div className="w-12 h-12 bg-white/15 rounded-2xl flex items-center justify-center text-2xl font-black">
              ص
            </div>
            <div className="text-right">
              <h3 className="text-2xl font-black">صنّعها</h3>
              <p className="text-xs text-blue-300/80 font-medium">من الفكرة إلى المصنع</p>
            </div>
          </div>

          <p className="text-base text-blue-200/70 max-w-md mx-auto font-medium">
            تحليل ذكي .. لقرارات صناعية أفضل
          </p>

          <a href="#upload" className="inline-flex items-center gap-2 bg-white text-blue-900 hover:bg-blue-50 px-8 py-3.5 rounded-xl font-black text-base transition-all shadow-lg">
            <ArrowLeft className="w-5 h-5" /> ابدأ الآن
          </a>

          <div className="pt-8 border-t border-white/10 text-xs text-white/30 font-medium">
            © 2026 صنّعها — هاكثون إحلال المستوردات 🇯🇴
          </div>
        </div>
      </footer>

    </div>
  );
}
