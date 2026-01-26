"use client";

import React, { useRef, useEffect } from "react";

export default function GlobalFlashlight() {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      containerRef.current.style.setProperty("--x", `${e.clientX}px`);
      containerRef.current.style.setProperty("--y", `${e.clientY}px`);
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  return (
    <div
      ref={containerRef}
      className="fixed inset-0 -z-10 pointer-events-none bg-[#020617]"
      style={{ "--x": "-1000px", "--y": "-1000px" } as React.CSSProperties}
    >
      <div 
        className="h-full w-full"
        style={{
          backgroundImage: "radial-gradient(#475569 2px, transparent 2px)",
          backgroundSize: "40px 40px",
          WebkitMaskImage: "radial-gradient(circle 350px at var(--x) var(--y), black 0%, rgba(0,0,0,0.5) 50%, transparent 100%)",
          maskImage: "radial-gradient(circle 350px at var(--x) var(--y), black 0%, rgba(0,0,0,0.5) 50%, transparent 100%)",
        }}
      />
    </div>
  );
}