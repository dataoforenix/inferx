import { useCallback, useRef, useState } from 'react';
import SiteBackdrop from './components/SiteBackdrop';
import SiteCursor from './components/SiteCursor';
import SiteHeader from './components/SiteHeader';
import HeroStory from './components/hero/HeroStory';
import ProductInput from './components/ProductInput';
import AnalysisSection from './components/AnalysisSection';
import SiteFooter from './components/SiteFooter';
import { analyzeProduct, confirmProduct } from './lib/analyzeProduct';

export default function App() {
  const [run, setRun] = useState(null); // { id, input, status: 'running' | 'done', outcome }
  const latest = useRef(0);

  const execute = useCallback(async (input, request) => {
    const id = ++latest.current;
    setRun({ id, input, status: 'running' });
    const outcome = await request();
    if (latest.current === id) setRun({ id, input, status: 'done', outcome });
  }, []);

  const startAnalysis = useCallback((input) => execute(input, () => analyzeProduct(input)), [execute]);

  const confirm = useCallback(
    (categoryId) => {
      const { input, outcome } = run;
      execute(input, () => confirmProduct(categoryId, outcome.product, input.name));
    },
    [run, execute],
  );

  const reset = useCallback(() => {
    latest.current += 1;
    setRun(null);
    const target = document.getElementById('product-input');
    target?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    target?.querySelector('[data-autofocus]')?.focus({ preventScroll: true });
  }, []);

  return (
    <>
      <SiteBackdrop />
      <SiteCursor />
      <SiteHeader />
      <main>
        <HeroStory />
        <ProductInput onAnalyze={startAnalysis} busy={run?.status === 'running'} />
        {run && <AnalysisSection run={run} onReset={reset} onConfirm={confirm} onAnalyze={startAnalysis} />}
      </main>
      <SiteFooter />
    </>
  );
}
