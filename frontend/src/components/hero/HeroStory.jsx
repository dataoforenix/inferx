import { lazy, Suspense, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { animate, useMotionValue, useReducedMotion, useScroll } from 'motion/react';
import { DEBUG_PROGRESS, FORCE_NO_3D, OPENING_SECONDS } from '../../lib/timeline';
import useWebGLSupport from '../../hooks/useWebGLSupport';
import CanvasErrorBoundary from '../three/CanvasErrorBoundary';
import StaticAssemblyFallback from '../three/StaticAssemblyFallback';
import HeroCopy from './HeroCopy';
import Annotations from './Annotations';
import { CornerMarks, OpeningChrome, ScrollCue } from './StoryChrome';

// three.js ships in its own chunk so the page shell paints first.
const AssemblyCanvas = lazy(() => import('../three/AssemblyCanvas'));

const LOAD_TIMEOUT_MS = 3500;
const SKIP_EASE = [0.23, 1, 0.32, 1];

/**
 * Opening + hero. A short time-based opening (assemble → explode → callouts →
 * reassemble) plays once, then the part glides beside the headline and the site opens.
 */
export default function HeroStory() {
  const sectionRef = useRef(null);
  const labelsRef = useRef({});
  const controls = useRef(null);
  const reduce = useReducedMotion();
  const webgl = useWebGLSupport();
  const show3D = webgl && !FORCE_NO_3D;
  const plays = show3D && !reduce && DEBUG_PROGRESS === null;

  const [ready, setReady] = useState(false);
  const [active, setActive] = useState(true);
  const [phase, setPhase] = useState(plays ? 'opening' : 'site');

  const story = useMotionValue(DEBUG_PROGRESS ?? (plays ? 0 : 1));
  const { scrollYProgress } = useScroll({ target: sectionRef, offset: ['start start', 'end start'] });

  const enterSite = useCallback(() => {
    controls.current?.stop();
    story.set(1);
    setPhase('site');
  }, [story]);

  const skip = useCallback(() => {
    if (phase !== 'opening') return;
    controls.current?.stop();
    const left = 1 - story.get();
    controls.current = animate(story, 1, { duration: 0.35 + left * 0.6, ease: SKIP_EASE, onComplete: enterSite });
  }, [phase, story, enterSite]);

  useLayoutEffect(() => {
    document.documentElement.dataset.phase = phase;
  }, [phase]);

  // Play the opening once the scene is ready; never block the site on a slow load.
  useEffect(() => {
    if (phase !== 'opening') return undefined;
    if (!ready) {
      const t = setTimeout(enterSite, LOAD_TIMEOUT_MS);
      return () => clearTimeout(t);
    }
    controls.current = animate(story, 1, { duration: OPENING_SECONDS, ease: 'linear', onComplete: enterSite });
    const opts = { passive: true };
    window.addEventListener('wheel', skip, opts);
    window.addEventListener('touchmove', skip, opts);
    window.addEventListener('keydown', skip);
    window.addEventListener('pointerdown', skip);
    return () => {
      window.removeEventListener('wheel', skip, opts);
      window.removeEventListener('touchmove', skip, opts);
      window.removeEventListener('keydown', skip);
      window.removeEventListener('pointerdown', skip);
    };
  }, [phase, ready, story, enterSite, skip]);

  // Stop rendering the scene once the hero is off screen.
  useEffect(() => {
    const el = sectionRef.current;
    if (!el) return undefined;
    const io = new IntersectionObserver(([entry]) => setActive(entry.isIntersecting), { rootMargin: '10% 0px' });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  const onReady = useCallback(() => setReady(true), []);

  return (
    <section ref={sectionRef} aria-labelledby="hero-title" className="relative h-svh min-h-[600px] overflow-hidden">
      <CornerMarks />

      {show3D ? (
        <CanvasErrorBoundary fallback={<StaticAssemblyFallback />}>
          <div className="canvas-fade absolute inset-0" data-ready={ready}>
            <Suspense fallback={null}>
              <AssemblyCanvas
                progress={story}
                scroll={scrollYProgress}
                reduce={Boolean(reduce)}
                active={active}
                labelsRef={labelsRef}
                onReady={onReady}
              />
            </Suspense>
          </div>
        </CanvasErrorBoundary>
      ) : (
        <StaticAssemblyFallback />
      )}

      <p className="sr-only">
        مجسّم ثلاثي الأبعاد لمجموعة ميكانيكية دقيقة: ترس، محمل كروي، حلقة تثبيت، عمود وشفة.
      </p>

      {show3D && <Annotations labelsRef={labelsRef} />}
      <HeroCopy story={story} />
      {plays && <OpeningChrome story={story} onSkip={skip} visible={phase === 'opening'} />}
      <ScrollCue story={story} scroll={scrollYProgress} />
    </section>
  );
}
