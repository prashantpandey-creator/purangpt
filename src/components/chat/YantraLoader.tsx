"use client";

import React, { useEffect, useRef, useState } from "react";

// Pipeline phases — driven by SSE events from the backend
const PHASE_CAPTIONS: Record<string, string> = {
  expand:   "Mapping your question into Sanskrit…",
  latent:   "Finding the right region of the void…",
  search:   "Searching the Puranas…",
  gretil:   "Consulting original Sanskrit manuscripts…",
  graph:    "Walking the knowledge graph…",
  buddhi:   "Synthesizing through the three granthis…",
  respond:  "The answer is forming…",
  default:  "Tapping into the void…",
};

const PHASE_SPEEDS: Record<string, number> = {
  expand:   0.3,   // slow — waiting for LLM
  latent:   0.6,   // quick — embedding runs fast
  search:   1.2,   // fast — pgvector
  gretil:   0.4,   // slow — regex over 56M chars
  graph:    0.8,   // medium — in-memory walk
  buddhi:   0.5,   // slow — LLM synthesis
  respond:  1.5,   // fastest — tokens streaming
  default:  0.5,
};

export function YantraLoader({ phase = "default" }: { phase?: string }) {
  const outerRingRef = useRef<SVGGElement>(null);
  const innerTriangleRef = useRef<SVGGElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  const [captionIndex, setCaptionIndex] = useState(0);
  const [captionOpacity, setCaptionOpacity] = useState(1);

  // Get current phase caption
  const caption = PHASE_CAPTIONS[phase] || PHASE_CAPTIONS.default;
  const speed = PHASE_SPEEDS[phase] || PHASE_SPEEDS.default;

  useEffect(() => {
    let outerAngle = 0;
    let innerAngle = 0;
    let animationFrameId: number;

    const animate = () => {
      outerAngle = (outerAngle + speed * 0.5) % 360;
      innerAngle = (innerAngle - speed * 0.8) % 360;

      if (outerRingRef.current) {
        outerRingRef.current.setAttribute("transform", `rotate(${outerAngle}, 24, 24)`);
      }
      if (innerTriangleRef.current) {
        innerTriangleRef.current.setAttribute("transform", `rotate(${innerAngle}, 24, 24)`);
      }

      animationFrameId = requestAnimationFrame(animate);
    };

    animationFrameId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(animationFrameId);
  }, [speed]);

  useEffect(() => {
    // Glitch effect — speed varies with phase intensity
    const interval = phase === "respond" ? 800 : 2200;
    const glitchInterval = setInterval(() => {
      if (wrapperRef.current) {
        const dx = (Math.random() - 0.5) * 4;
        const dy = (Math.random() - 0.5) * 4;
        wrapperRef.current.style.transform = `translate(${dx}px, ${dy}px)`;
        wrapperRef.current.style.opacity = "0.55";

        setTimeout(() => {
          if (wrapperRef.current) {
            wrapperRef.current.style.transform = "translate(0, 0)";
            wrapperRef.current.style.opacity = "1";
          }
        }, phase === "respond" ? 50 : 110);
      }
    }, interval);

    return () => clearInterval(glitchInterval);
  }, [phase]);

  return (
    <div className="flex items-center gap-3 py-1">
      <div
        ref={wrapperRef}
        className="w-5 h-5 flex-shrink-0"
        style={{ transition: "opacity 0.05s ease-out" }}
      >
        <svg viewBox="0 0 48 48" className="w-full h-full">
          {/* Static Center Bindu */}
          <circle cx="24" cy="24" r="2" fill="#e8b63f" />

          {/* Inner Triangle (Counter-rotating) */}
          <g ref={innerTriangleRef}>
            <polygon
              points="24,14 34,32 14,32"
              fill="none"
              stroke="#e8b63f"
              strokeWidth="1.5"
            />
            <polygon
              points="24,34 14,16 34,16"
              fill="none"
              stroke="#e8b63f"
              strokeWidth="1.5"
              opacity="0.6"
            />
          </g>

          {/* Outer Ring (Rotating) */}
          <g ref={outerRingRef}>
            <circle cx="24" cy="24" r="18" fill="none" stroke="#e8b63f" strokeWidth="1.5" strokeDasharray="4 8" />
            <circle cx="24" cy="24" r="21" fill="none" stroke="#e8b63f" strokeWidth="1" opacity="0.5" strokeDasharray="12 4" />
          </g>
        </svg>
      </div>
      <span
        className="text-[13px] transition-opacity duration-200"
        style={{
          fontFamily: 'Inter, sans-serif',
          color: '#a38d7c',
          opacity: 1,
        }}
      >
        {caption}
      </span>
    </div>
  );
}
