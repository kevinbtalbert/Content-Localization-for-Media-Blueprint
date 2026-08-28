/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import { useState, ReactNode, useRef, useEffect } from "react";
import IconCaretDown from "../icons/IconCaretDown";
import { H2 } from "../Text";

interface AccordionProps {
  title: string;
  children: ReactNode;
  defaultExpanded?: boolean;
  className?: string;
}

const Accordion: React.FC<AccordionProps> = ({ title, children, defaultExpanded = false, className = "" }) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [contentHeight, setContentHeight] = useState<string>(defaultExpanded ? "none" : "0px");
  const contentRef = useRef<HTMLDivElement>(null);

  // Simple measurement when expanding
  useEffect(() => {
    const measureHeight = () => {
      if (isExpanded && contentRef.current) {
        // Temporarily allow full height to measure
        setContentHeight("9999px");
        requestAnimationFrame(() => {
          if (contentRef.current) {
            setContentHeight(`${contentRef.current.scrollHeight + 16}px`);
          }
        });
      } else {
        setContentHeight("0px");
      }
    };

    measureHeight();

    // Recalculate on resize when expanded
    if (isExpanded) {
      window.addEventListener("resize", measureHeight, true);
      return () => {
        window.removeEventListener("resize", measureHeight, true);
      };
    }
  }, [isExpanded, children]);

  return (
    <div className={`rounded-xl border border-[color:var(--color-base-border)] p-4 ${className}`}>
      <button
        type="button"
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between text-left cursor-pointer"
        aria-expanded={isExpanded}
      >
        <H2 className="text-2xl font-semibold text-[color:var(--color-primary-foreground)] tracking-tight">{title}</H2>
        <IconCaretDown className={`transition-transform duration-300 ease-in-out ${isExpanded ? "rotate-180" : ""}`} />
      </button>
      <div
        className="overflow-hidden transition-all duration-300 ease-in-out"
        style={{
          maxHeight: contentHeight,
        }}
      >
        <div ref={contentRef}>{children}</div>
      </div>
    </div>
  );
};
export default Accordion;
