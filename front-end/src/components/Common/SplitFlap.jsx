import React, { useEffect, useRef, useState } from 'react';

const GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$%';

const randomGlyph = () => GLYPHS[Math.floor(Math.random() * GLYPHS.length)];

export default function SplitFlap({ words, interval = 3200, tileClassName = '' }) {
  const width = Math.max(...words.map((w) => w.length));
  const pad = (w) => w.toUpperCase().padEnd(width, ' ');

  const [wordIndex, setWordIndex] = useState(0);
  const [chars, setChars] = useState(() => pad(words[0]).split(''));
  const [flipping, setFlipping] = useState(() => new Array(width).fill(false));
  const timers = useRef([]);

  useEffect(() => {
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const target = pad(words[wordIndex]).split('');

    if (reduceMotion) {
      setChars(target);
      return undefined;
    }

    target.forEach((finalChar, i) => {
      const flips = 6 + i * 2;
      let count = 0;
      const id = setInterval(() => {
        count += 1;
        const done = count >= flips;
        setChars((prev) => {
          const next = [...prev];
          next[i] = done ? finalChar : randomGlyph();
          return next;
        });
        setFlipping((prev) => {
          const next = [...prev];
          next[i] = !done;
          return next;
        });
        if (done) clearInterval(id);
      }, 60);
      timers.current.push(id);
    });

    const cycle = setTimeout(() => {
      setWordIndex((idx) => (idx + 1) % words.length);
    }, interval);

    return () => {
      timers.current.forEach(clearInterval);
      timers.current = [];
      clearTimeout(cycle);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wordIndex]);

  return (
    <span className="inline-flex gap-1 md:gap-1.5" aria-label={words[wordIndex]} role="text">
      {chars.map((c, i) => (
        <span
          key={i}
          aria-hidden="true"
          className={`flap-tile ${flipping[i] ? 'is-flipping' : ''} ${tileClassName}`}
        >
          {c === ' ' ? '\u00A0' : c}
        </span>
      ))}
    </span>
  );
}
