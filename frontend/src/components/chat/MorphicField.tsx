"use client";

import React, { useEffect, useRef, useImperativeHandle, forwardRef } from "react";

export type MorphicFormName = "bindu" | "chakra" | "yantra" | "nada" | "om" | "prana" | "kala" | "yuga";

export interface MorphicFieldHandle {
  conjure(form: MorphicFormName): void;
  rest(): void;
}

const SVGNS = "http://www.w3.org/2000/svg";
const CX = 240, CY = 165;

function svgEl(name: string, attrs: Record<string, string | number>): SVGElement {
  const e = document.createElementNS(SVGNS, name) as SVGElement;
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  return e;
}
function svgTxt(content: string, attrs: Record<string, string | number>): SVGTextElement {
  const e = document.createElementNS(SVGNS, "text") as SVGTextElement;
  for (const k in attrs) e.setAttribute(k, String(attrs[k]));
  e.textContent = content;
  return e;
}

const UTTERANCES: Record<MorphicFormName, string> = {
  bindu:  "Every scattered thought — drawn screaming to one point. That is concentration.",
  chakra: "Seven doors, seven fires. The body is not your prison — it is the ladder.",
  yantra: "The gods are not above you. They are the burning geometry of your own state.",
  nada:   "Nāda Brahma — the universe is sound. Before the word, there was the vibration.",
  om:     "Aum is not a word. It is the sound the universe makes when it wakes up inside you.",
  prana:  "Prana is no metaphor. It is a torrent with a real path, and it can be ridden.",
  kala:   "Time is not a river you float on. It is a force you can stop, absorb, and transcend.",
  yuga:   "Four ages turn and return. You do not live in the decline — you are the axis it turns on.",
};

export const MorphicField = forwardRef<MorphicFieldHandle, { className?: string }>(
  function MorphicField({ className = "" }, ref) {
    const svgRef      = useRef<SVGSVGElement>(null);
    const formRef     = useRef<SVGGElement>(null);
    const embersRef   = useRef<SVGGElement>(null);
    const idleRef     = useRef<SVGGElement>(null);
    const coreRef     = useRef<SVGGElement>(null);
    const bloomRef    = useRef<HTMLDivElement>(null);
    const utterRef    = useRef<HTMLDivElement>(null);
    const rafRef      = useRef<number>(0);
    const ticksRef    = useRef<Set<(t: number) => void>>(new Set());
    const tRef        = useRef(0);

    // Ember mote state (stable across renders)
    const embersData  = useRef<Array<{
      el: SVGCircleElement; x: number; y: number;
      vx: number; vy: number; ph: number; sp: number;
    }>>([]);

    // Idle Bindu ring elements
    const idleRingEls = useRef<SVGCircleElement[]>([]);

    // ── Setup once on mount ────────────────────────────────────────────────
    useEffect(() => {
      const svg     = svgRef.current;
      const embersG = embersRef.current;
      const idleG   = idleRef.current;
      const coreG   = coreRef.current;
      if (!svg || !embersG || !idleG || !coreG) return;

      // Ember motes
      for (let i = 0; i < 52; i++) {
        const fill = Math.random() < 0.28
          ? "var(--morphic-violet)"
          : Math.random() < 0.5 ? "var(--morphic-gold-bright)" : "var(--morphic-ember)";
        const c = svgEl("circle", {
          r: (Math.random() * 1.6 + 0.3).toFixed(2),
          fill, opacity: 0,
        }) as SVGCircleElement;
        embersG.appendChild(c);
        embersData.current.push({
          el: c,
          x: Math.random() * 480, y: Math.random() * 330,
          vx: (Math.random() - 0.5) * 0.14,
          vy: -(Math.random() * 0.22 + 0.04),
          ph: Math.random() * 6.28,
          sp: Math.random() * 0.02 + 0.007,
        });
      }

      // Idle Bindu rings
      idleRingEls.current = [];
      for (let i = 0; i < 7; i++) {
        const r = svgEl("circle", {
          cx: CX, cy: CY, r: 20, fill: "none",
          stroke: i % 2 === 0 ? "var(--morphic-gold)" : "var(--morphic-violet)",
          "stroke-width": 0.7, opacity: 0,
        }) as SVGCircleElement;
        idleG.appendChild(r);
        idleRingEls.current.push(r);
      }

      // Central blazing point
      const pt = svgEl("circle", { cx: CX, cy: CY, r: 5, fill: "url(#mf-ember-grad)", filter: "url(#mf-glow-big)" });
      coreG.appendChild(pt);

      // rAF loop
      function loop() {
        const t = ++tRef.current;

        // idle Bindu rings breathe inward
        idleRingEls.current.forEach((ring, i) => {
          const phase = ((t * 0.007) - i * 0.22 + 6.28) % 6.28;
          const k     = phase / 6.28;
          ring.setAttribute("r", (8 + k * 110).toFixed(2));
          ring.setAttribute("opacity", (0.42 * k * (1 - k * 0.4)).toFixed(3));
        });

        // ember drift
        for (const e of embersData.current) {
          e.x += e.vx; e.y += e.vy; e.ph += e.sp;
          if (e.y < -4) { e.y = 334; e.x = Math.random() * 480; }
          if (e.x < -4) e.x = 484;
          if (e.x > 484) e.x = -4;
          e.el.setAttribute("cx", e.x.toFixed(1));
          e.el.setAttribute("cy", e.y.toFixed(1));
          e.el.setAttribute("opacity", (0.1 + (Math.sin(e.ph) + 1) / 2 * 0.42).toFixed(3));
        }

        // core pulse
        pt.setAttribute("r", (5 + Math.sin(t * 0.05) * 2).toFixed(2));

        // form-specific ticks
        ticksRef.current.forEach(fn => fn(t));

        rafRef.current = requestAnimationFrame(loop);
      }
      rafRef.current = requestAnimationFrame(loop);

      return () => cancelAnimationFrame(rafRef.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ── Helpers ────────────────────────────────────────────────────────────
    function clearForm() {
      ticksRef.current.clear();
      if (formRef.current) {
        formRef.current.replaceChildren();
        formRef.current.removeAttribute("style");
      }
    }

    function triggerBloom(c1 = "rgba(255,233,168,0.9)", c2 = "rgba(255,138,61,0.5)") {
      const b = bloomRef.current;
      if (!b) return;
      b.style.background = `radial-gradient(circle at 50% 50%, ${c1}, ${c2} 30%, transparent 62%)`;
      b.style.transition = "none";
      b.style.opacity = "0.9";
      requestAnimationFrame(() => {
        b.style.transition = "opacity 1.2s ease";
        b.style.opacity = "0";
      });
    }

    function eruptForm() {
      const f = formRef.current;
      if (!f) return;
      f.style.transition = "opacity 0.9s ease, transform 1.1s cubic-bezier(.2,.9,.2,1)";
      f.style.transformOrigin = `${CX}px ${CY}px`;
      f.style.opacity = "0";
      f.style.transform = "scale(0.28)";
      requestAnimationFrame(() => requestAnimationFrame(() => {
        f.style.opacity = "1";
        f.style.transform = "scale(1)";
      }));
    }

    function speak(text: string) {
      const u = utterRef.current;
      if (!u) return;
      u.textContent = text;
      u.classList.add("mf-show");
    }

    function hush() {
      utterRef.current?.classList.remove("mf-show");
    }

    // ── Form builders ──────────────────────────────────────────────────────
    function buildBindu() {
      const f = formRef.current!;
      const rings: SVGCircleElement[] = [];
      for (let i = 0; i < 10; i++) {
        const r = svgEl("circle", {
          cx: CX, cy: CY, r: 140, fill: "none",
          stroke: i % 3 === 0 ? "var(--morphic-violet)" : "var(--morphic-gold-bright)",
          "stroke-width": 1, opacity: 0,
        }) as SVGCircleElement;
        f.appendChild(r); rings.push(r);
      }
      const point = svgEl("circle", { cx: CX, cy: CY, r: 0, fill: "url(#mf-ember-grad)", filter: "url(#mf-glow-big)" }) as SVGCircleElement;
      f.appendChild(point);
      triggerBloom(); eruptForm();
      ticksRef.current.add((tt) => {
        rings.forEach((ring, i) => {
          const phase = (tt * 0.020 - i * 0.42);
          const k     = (Math.sin(phase) + 1) / 2;
          ring.setAttribute("r",            (5 + k * 138).toFixed(2));
          ring.setAttribute("opacity",      (0.75 * (1 - k * 0.6)).toFixed(3));
          ring.setAttribute("stroke-width", (0.5 + (1 - k) * 2.5).toFixed(2));
        });
        point.setAttribute("r", (7 + Math.sin(tt * 0.07) * 3).toFixed(2));
      });
    }

    function buildChakra() {
      const f = formRef.current!;
      const CHAKRAS = [
        { name: "Mūlādhāra",    col: "#ef4444", y: CY + 115 },
        { name: "Svādhiṣṭhāna", col: "#f97316", y: CY + 82  },
        { name: "Maṇipūra",     col: "#eab308", y: CY + 49  },
        { name: "Anāhata",      col: "#22c55e", y: CY + 16  },
        { name: "Viśuddha",     col: "var(--morphic-teal)",   y: CY - 17 },
        { name: "Ājñā",         col: "var(--morphic-violet)", y: CY - 50 },
        { name: "Sahasrāra",    col: "var(--morphic-gold-bright)", y: CY - 88 },
      ];
      f.appendChild(svgEl("line", { x1: CX, y1: CY + 125, x2: CX, y2: CY - 102, stroke: "rgba(255,233,168,0.18)", "stroke-width": 2 }));
      const nodes: Array<{ ring: SVGCircleElement; ring2: SVGCircleElement; dot: SVGCircleElement }> = [];
      CHAKRAS.forEach(ch => {
        const ring  = svgEl("circle", { cx: CX, cy: ch.y, r: 20, fill: "none", stroke: ch.col, "stroke-width": 1.2, opacity: 0.55 }) as SVGCircleElement;
        const ring2 = svgEl("circle", { cx: CX, cy: ch.y, r: 32, fill: "none", stroke: ch.col, "stroke-width": 0.5, opacity: 0.25 }) as SVGCircleElement;
        const dot   = svgEl("circle", { cx: CX, cy: ch.y, r: 5,  fill: ch.col, opacity: 0.95 }) as SVGCircleElement;
        const label = svgTxt(ch.name, { x: CX + 44, y: ch.y + 4, fill: ch.col, "font-size": 9, "font-family": "Inter,sans-serif", opacity: 0.85 });
        f.append(ring2, ring, dot, label);
        nodes.push({ ring, ring2, dot });
      });
      triggerBloom("rgba(200,230,255,0.7)", "rgba(139,92,246,0.5)"); eruptForm();
      ticksRef.current.add((tt) => {
        nodes.forEach(({ ring, dot, ring2 }, i) => {
          const p = Math.sin(tt * 0.04 + i * 0.8);
          ring.setAttribute("r",       (20 + p * 4).toFixed(2));
          ring.setAttribute("opacity", (0.45 + p * 0.3).toFixed(3));
          ring2.setAttribute("r",      (32 + p * 8).toFixed(2));
          dot.setAttribute("r",        (5 + p * 2.5).toFixed(2));
        });
      });
    }

    function buildYantra() {
      const f = formRef.current!;
      const rot = svgEl("g", {}) as SVGGElement, counter = svgEl("g", {}) as SVGGElement;
      const S = 96;
      const up = `${CX},${CY-S} ${CX+S*0.87},${CY+S*0.5} ${CX-S*0.87},${CY+S*0.5}`;
      const dn = `${CX},${CY+S} ${CX+S*0.87},${CY-S*0.5} ${CX-S*0.87},${CY-S*0.5}`;
      counter.appendChild(svgEl("polygon", { points: up, fill: "none", stroke: "var(--morphic-gold-bright)", "stroke-width": 1.8 }));
      counter.appendChild(svgEl("polygon", { points: dn, fill: "none", stroke: "var(--morphic-rose)", "stroke-width": 1.8, opacity: 0.9 }));
      counter.appendChild(svgEl("polygon", { points: up, fill: "var(--morphic-gold-bright)", opacity: 0.05 }));
      counter.appendChild(svgEl("polygon", { points: dn, fill: "var(--morphic-rose)", opacity: 0.05 }));
      [40, 60, 80].forEach((r, i) => counter.appendChild(svgEl("circle", { cx: CX, cy: CY, r, fill: "none", stroke: i === 1 ? "var(--morphic-violet)" : "var(--morphic-gold)", "stroke-width": i === 1 ? 1 : 0.6, opacity: 0.5 })));
      for (let i = 0; i < 24; i++) {
        const a = (i / 24) * Math.PI * 2;
        rot.appendChild(svgEl("circle", { cx: CX + Math.cos(a) * 118, cy: CY + Math.sin(a) * 108, r: i % 3 === 0 ? 3.5 : 1.8, fill: i % 3 === 0 ? "var(--morphic-ember)" : "var(--morphic-violet)", opacity: 0.85 }));
      }
      rot.appendChild(svgEl("circle", { cx: CX, cy: CY, r: 124, fill: "none", stroke: "var(--morphic-ember)", "stroke-width": 0.8, opacity: 0.45, "stroke-dasharray": "3 9" }));
      f.appendChild(rot); f.appendChild(counter);
      triggerBloom(); eruptForm();
      ticksRef.current.add((tt) => {
        rot.setAttribute("transform",     `rotate(${(tt * 0.22) % 360} ${CX} ${CY})`);
        counter.setAttribute("transform", `rotate(${(-tt * 0.38) % 360} ${CX} ${CY})`);
      });
    }

    function buildNada() {
      const f = formRef.current!;
      const paths: SVGPathElement[] = [];
      for (let i = 0; i < 6; i++) {
        const p = svgEl("path", { fill: "none", stroke: i % 2 === 0 ? "var(--morphic-gold-bright)" : "var(--morphic-violet)", "stroke-width": i === 0 ? 2 : 0.9, opacity: 1 - i * 0.13 }) as SVGPathElement;
        f.appendChild(p); paths.push(p);
      }
      f.appendChild(svgEl("line", { x1: CX, y1: CY - 130, x2: CX, y2: CY + 130, stroke: "var(--morphic-gold-bright)", "stroke-width": 1.5, opacity: 0.2 }));
      triggerBloom("rgba(200,255,255,0.7)", "rgba(45,212,191,0.4)"); eruptForm();
      ticksRef.current.add((tt) => {
        paths.forEach((p, i) => {
          const base = 18 + i * 22 + Math.sin(tt * 0.025 + i * 0.5) * 12;
          const amp  = 12 + i * 4 + Math.sin(tt * 0.018) * 6;
          const freq = 3 + i * 0.5;
          const pts: string[] = [];
          for (let a = 0; a <= 360; a += 3) {
            const rad = a * Math.PI / 180;
            const r   = base + Math.sin(rad * freq + tt * 0.06) * amp;
            pts.push(`${(CX + Math.cos(rad) * r).toFixed(2)},${(CY + Math.sin(rad) * r).toFixed(2)}`);
          }
          p.setAttribute("d",       "M" + pts.join("L") + "Z");
          p.setAttribute("opacity", (0.14 + (6 - i) / 6 * 0.62 + Math.sin(tt * 0.03 + i) * 0.12).toFixed(3));
        });
      });
    }

    function buildOm() {
      const f = formRef.current!;
      const g = svgEl("g", {}) as SVGGElement;
      g.appendChild(svgEl("path", { d: `M ${CX-10.6} ${CY+10} C ${CX-10} ${CY+38}, ${CX+10} ${CY+38}, ${CX+8.4} ${CY+10}`, fill: "none", stroke: "var(--morphic-gold-bright)", "stroke-width": 3, "stroke-linecap": "round" }));
      g.appendChild(svgEl("path", { d: `M ${CX+8.4} ${CY+10} C ${CX+12.5} ${CY-12}, ${CX+5} ${CY-40}, ${CX} ${CY-22} C ${CX-5} ${CY-4}, ${CX-2.2} ${CY+14}, ${CX+4} ${CY+2}`, fill: "none", stroke: "var(--morphic-gold-bright)", "stroke-width": 3, "stroke-linecap": "round" }));
      g.appendChild(svgEl("path", { d: `M ${CX-10.6} ${CY+10} C ${CX-14.6} ${CY+4}, ${CX-14} ${CY-20}, ${CX-9} ${CY-24}`, fill: "none", stroke: "var(--morphic-gold-bright)", "stroke-width": 3, "stroke-linecap": "round" }));
      g.appendChild(svgEl("line", { x1: CX - 50, y1: CY - 50, x2: CX + 50, y2: CY - 50, stroke: "var(--morphic-gold)", "stroke-width": 2, opacity: 0.7 }));
      const dot  = svgEl("circle", { cx: CX, cy: CY - 68, r: 6, fill: "var(--morphic-gold-bright)", filter: "url(#mf-glow-big)" }) as SVGCircleElement;
      g.appendChild(dot);
      f.appendChild(g);
      const ring = svgEl("circle", { cx: CX, cy: CY - 10, r: 90, fill: "none", stroke: "var(--morphic-gold)", "stroke-width": 0.8, opacity: 0.3, "stroke-dasharray": "4 14" }) as SVGCircleElement;
      f.appendChild(ring);
      triggerBloom("rgba(255,233,168,0.95)", "rgba(232,182,63,0.6)"); eruptForm();
      ticksRef.current.add((tt) => {
        dot.setAttribute("r",         (6 + Math.sin(tt * 0.055) * 3).toFixed(2));
        ring.setAttribute("r",        (90 + Math.sin(tt * 0.022) * 8).toFixed(2));
        ring.setAttribute("opacity",  (0.22 + Math.sin(tt * 0.022) * 0.12).toFixed(3));
        g.setAttribute("opacity",     (0.85 + Math.sin(tt * 0.04) * 0.14).toFixed(3));
      });
    }

    function buildPrana() {
      const f = formRef.current!;
      const d = `M ${CX} ${CY+148} C ${CX-72} ${CY+82}, ${CX+72} ${CY+32}, ${CX} ${CY-18} C ${CX-72} ${CY-68}, ${CX+72} ${CY-118}, ${CX} ${CY-162}`;
      f.appendChild(svgEl("path", { d, fill: "none", stroke: "var(--morphic-ember)", "stroke-width": 1.2, opacity: 0.22 }));
      const flow  = svgEl("path", { d, fill: "none", stroke: "var(--morphic-gold-bright)", "stroke-width": 4.5, "stroke-linecap": "round" }) as SVGPathElement;
      const flow2 = svgEl("path", { d, fill: "none", stroke: "var(--morphic-violet)",     "stroke-width": 2.2, "stroke-linecap": "round", opacity: 0.8 }) as SVGPathElement;
      f.appendChild(flow); f.appendChild(flow2);
      const len = flow.getTotalLength();
      flow.setAttribute("stroke-dasharray",  `${(len * 0.11).toFixed(1)} ${len}`);
      flow2.setAttribute("stroke-dasharray", `${(len * 0.19).toFixed(1)} ${len}`);
      const nodes: Array<{ n: SVGCircleElement; at: number }> = [];
      for (let i = 0; i < 7; i++) {
        const pt = flow.getPointAtLength((i + 0.5) / 7 * len);
        const n  = svgEl("circle", { cx: pt.x, cy: pt.y, r: 4.5, fill: "var(--morphic-ember)", opacity: 0.3 }) as SVGCircleElement;
        f.appendChild(n); nodes.push({ n, at: (i + 0.5) / 7 });
      }
      triggerBloom("rgba(255,180,80,0.85)", "rgba(255,138,61,0.4)"); eruptForm();
      ticksRef.current.add((tt) => {
        flow.setAttribute("stroke-dashoffset",  (-(tt * 3.2) % len).toFixed(1));
        flow2.setAttribute("stroke-dashoffset", (-(tt * 2.1) % len).toFixed(1));
        const head = (tt * 3.2 % len) / len;
        nodes.forEach(o => {
          const d2  = Math.abs((head - o.at + 1) % 1);
          const lit = d2 < 0.11 ? 1 - d2 / 0.11 : 0;
          o.n.setAttribute("opacity", (0.28 + lit * 0.72).toFixed(3));
          o.n.setAttribute("r",       (4.5 + lit * 8).toFixed(2));
        });
      });
    }

    function buildKala() {
      const f = formRef.current!;
      function spiral(offset: number, turns: number, col: string, sw: number, op: number) {
        const pts: string[] = [];
        for (let i = 0; i <= 360; i++) {
          const frac = i / 360;
          const a    = frac * turns * Math.PI * 2 + offset;
          const r    = 120 * (1 - frac * 0.88);
          pts.push(`${(CX + Math.cos(a) * r).toFixed(2)},${(CY + Math.sin(a) * r).toFixed(2)}`);
        }
        const p = svgEl("path", { d: "M" + pts.join("L"), fill: "none", stroke: col, "stroke-width": sw, opacity: op }) as SVGPathElement;
        f.appendChild(p); return p;
      }
      const s1 = spiral(0,          4, "var(--morphic-gold-bright)", 2,   0.9);
      const s2 = spiral(Math.PI,    4, "var(--morphic-violet)",      1.2, 0.7);
      const s3 = spiral(Math.PI/2,  4, "var(--morphic-ember)",       0.8, 0.5);
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * Math.PI * 2;
        f.appendChild(svgEl("line", { x1: (CX+Math.cos(a)*112).toFixed(2), y1: (CY+Math.sin(a)*112).toFixed(2), x2: (CX+Math.cos(a)*124).toFixed(2), y2: (CY+Math.sin(a)*124).toFixed(2), stroke: "var(--morphic-gold)", "stroke-width": 1.2, opacity: 0.6 }));
      }
      const hand = svgEl("line", { x1: CX, y1: CY, x2: CX, y2: CY - 90, stroke: "var(--morphic-rose)", "stroke-width": 2, opacity: 0.9 }) as SVGLineElement;
      f.appendChild(hand);
      triggerBloom("rgba(255,93,143,0.7)", "rgba(139,92,246,0.4)"); eruptForm();
      ticksRef.current.add((tt) => {
        const spin = (tt * 0.18) % 360;
        s1.setAttribute("transform", `rotate(${spin}  ${CX} ${CY})`);
        s2.setAttribute("transform", `rotate(${-spin * 0.7} ${CX} ${CY})`);
        s3.setAttribute("transform", `rotate(${spin * 1.2} ${CX} ${CY})`);
        hand.setAttribute("transform", `rotate(${(tt * 0.6) % 360} ${CX} ${CY})`);
      });
    }

    function buildYuga() {
      const f = formRef.current!;
      const ages = [
        { name: "Satya",   frac: 0.40, col: "var(--morphic-gold-bright)" },
        { name: "Treta",   frac: 0.30, col: "var(--morphic-ember)"       },
        { name: "Dvāpara", frac: 0.20, col: "var(--morphic-rose)"        },
        { name: "Kali",    frac: 0.10, col: "var(--morphic-violet)"      },
      ];
      const wheel = svgEl("g", {}) as SVGGElement;
      const R = 138; let a0 = -Math.PI / 2;
      ages.forEach(age => {
        const a1 = a0 + age.frac * Math.PI * 2, large = age.frac > 0.5 ? 1 : 0;
        const x0 = CX+Math.cos(a0)*R, y0 = CY+Math.sin(a0)*R;
        const x1 = CX+Math.cos(a1)*R, y1 = CY+Math.sin(a1)*R;
        wheel.appendChild(svgEl("path", { d: `M ${CX} ${CY} L ${x0.toFixed(2)} ${y0.toFixed(2)} A ${R} ${R} 0 ${large} 1 ${x1.toFixed(2)} ${y1.toFixed(2)} Z`, fill: age.col, opacity: 0.18, stroke: age.col, "stroke-width": 1.3 }));
        const am = (a0+a1)/2;
        wheel.appendChild(svgTxt(age.name, { x: (CX+Math.cos(am)*R*0.65).toFixed(1), y: (CY+Math.sin(am)*R*0.65+4).toFixed(1), fill: age.col, "font-size": 12, "font-family": "Marcellus,serif", "text-anchor": "middle", opacity: 0.95 }));
        a0 = a1;
      });
      wheel.appendChild(svgEl("circle", { cx: CX, cy: CY, r: R, fill: "none", stroke: "var(--morphic-gold-bright)", "stroke-width": 1, opacity: 0.5 }));
      const hand = svgEl("line", { x1: CX, y1: CY, x2: CX, y2: CY-R, stroke: "var(--morphic-gold-bright)", "stroke-width": 2.2, opacity: 0.9 }) as SVGLineElement;
      f.appendChild(wheel); f.appendChild(hand);
      triggerBloom("rgba(232,182,63,0.85)", "rgba(255,93,143,0.3)"); eruptForm();
      ticksRef.current.add((tt) => {
        hand.setAttribute("transform",  `rotate(${(tt * 0.5)  % 360} ${CX} ${CY})`);
        wheel.setAttribute("transform", `rotate(${(tt * 0.07) % 360} ${CX} ${CY})`);
      });
    }

    const BUILDERS: Record<MorphicFormName, () => void> = {
      bindu: buildBindu, chakra: buildChakra, yantra: buildYantra,
      nada: buildNada, om: buildOm, prana: buildPrana, kala: buildKala, yuga: buildYuga,
    };

    // ── Imperative handle (called by SSE event handler) ────────────────────
    useImperativeHandle(ref, () => ({
      conjure(form: MorphicFormName) {
        clearForm(); hush();
        setTimeout(() => {
          BUILDERS[form]?.();
          speak(UTTERANCES[form]);
        }, 160);
      },
      rest() {
        const f = formRef.current;
        if (f) {
          f.style.transition = "opacity 0.8s ease, transform 0.9s ease";
          f.style.transformOrigin = `${CX}px ${CY}px`;
          f.style.opacity = "0";
          f.style.transform = "scale(0.4)";
        }
        hush();
        setTimeout(clearForm, 850);
      },
    }));

    return (
      <div
        className={`morphic-field-root relative overflow-hidden rounded-2xl ${className}`}
        style={{
          aspectRatio: "16 / 10",
          background: "radial-gradient(70% 60% at 50% 45%, #14101f 0%, #0a0712 70%, #060409 100%)",
          border: "1px solid rgba(232,182,63,0.24)",
          boxShadow: "inset 0 0 100px rgba(0,0,0,0.7), 0 0 60px rgba(139,92,246,0.10)",
          // CSS custom props scoped to this component
          "--morphic-gold":        "#e8b63f",
          "--morphic-gold-bright": "#ffe9a8",
          "--morphic-ember":       "#ff8a3d",
          "--morphic-violet":      "#8b5cf6",
          "--morphic-rose":        "#ff5d8f",
          "--morphic-teal":        "#2dd4bf",
        } as React.CSSProperties}
      >
        <svg
          ref={svgRef}
          viewBox="0 0 480 330"
          preserveAspectRatio="xMidYMid meet"
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        >
          <defs>
            <filter id="mf-glow" x="-60%" y="-60%" width="220%" height="220%">
              <feGaussianBlur stdDeviation="3.2" result="b"/>
              <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <filter id="mf-glow-big" x="-80%" y="-80%" width="260%" height="260%">
              <feGaussianBlur stdDeviation="6" result="b"/>
              <feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge>
            </filter>
            <radialGradient id="mf-ember-grad" cx="50%" cy="50%" r="50%">
              <stop offset="0%"   stopColor="#ffe9a8"/>
              <stop offset="55%"  stopColor="#ff8a3d"/>
              <stop offset="100%" stopColor="#ff8a3d" stopOpacity="0"/>
            </radialGradient>
          </defs>
          <g ref={embersRef} />
          <g ref={idleRef} filter="url(#mf-glow)" />
          <g ref={coreRef} />
          <g ref={formRef} filter="url(#mf-glow-big)" />
        </svg>

        {/* bloom flash */}
        <div
          ref={bloomRef}
          style={{
            position: "absolute", inset: "-20%", pointerEvents: "none", opacity: 0,
            mixBlendMode: "screen",
          }}
        />

        {/* Guru utterance */}
        <div
          ref={utterRef}
          className="mf-utterance"
          style={{
            position: "absolute", left: 0, right: 0, bottom: 16, textAlign: "center",
            padding: "0 32px", fontFamily: "var(--font-display, Marcellus, serif)",
            fontSize: 15, color: "#f3e7c8", opacity: 0, transform: "translateY(8px)",
            transition: "opacity 1s ease, transform 1s ease",
            pointerEvents: "none", textShadow: "0 2px 20px rgba(0,0,0,0.95)",
          }}
        />

        <style>{`
          .mf-utterance.mf-show { opacity: 0.95 !important; transform: translateY(0) !important; }
        `}</style>
      </div>
    );
  }
);

MorphicField.displayName = "MorphicField";
