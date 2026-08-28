/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import React, { useState, useRef, useEffect } from "react";
import IconCaretDown from "./icons/IconCaretDown";

interface SelectOption {
  value: string;
  label: string;
}

interface CustomSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

const CustomSelect: React.FC<CustomSelectProps> = ({
  value,
  onChange,
  options,
  disabled = false,
  placeholder = "Select an option",
  className = "",
}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const [openUpward, setOpenUpward] = useState(false);
  const selectRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);

  const selectedOption = options.find((option) => option.value === value);

  // Calculate position and open dropdown
  const handleToggleDropdown = () => {
    if (disabled) return;

    if (!isOpen && buttonRef.current) {
      // Calculate position before opening
      const buttonRect = buttonRef.current.getBoundingClientRect();
      const estimatedDropdownHeight = Math.min(options.length * 40, 240); // Estimate: ~40px per option, max 240px
      const spaceBelow = window.innerHeight - buttonRect.bottom;
      const spaceAbove = buttonRect.top;

      // Determine if should open upward
      const shouldOpenUpward = spaceBelow < estimatedDropdownHeight && spaceAbove > spaceBelow;
      setOpenUpward(shouldOpenUpward);
    }

    setIsOpen(!isOpen);
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
        setIsOpen(false);
        setFocusedIndex(-1);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  // Handle keyboard navigation
  const handleKeyDown = (event: React.KeyboardEvent) => {
    if (disabled) return;

    switch (event.key) {
      case "Enter":
      case " ":
        event.preventDefault();
        if (isOpen && focusedIndex >= 0) {
          onChange(options[focusedIndex].value);
          setIsOpen(false);
          setFocusedIndex(-1);
        } else {
          handleToggleDropdown();
        }
        break;
      case "Escape":
        setIsOpen(false);
        setFocusedIndex(-1);
        buttonRef.current?.focus();
        break;
      case "ArrowDown":
        event.preventDefault();
        if (!isOpen) {
          handleToggleDropdown();
        } else {
          setFocusedIndex((prev) => (prev < options.length - 1 ? prev + 1 : 0));
        }
        break;
      case "ArrowUp":
        event.preventDefault();
        if (!isOpen) {
          handleToggleDropdown();
        } else {
          setFocusedIndex((prev) => (prev > 0 ? prev - 1 : options.length - 1));
        }
        break;
    }
  };

  const handleOptionClick = (optionValue: string) => {
    onChange(optionValue);
    setIsOpen(false);
    setFocusedIndex(-1);
    buttonRef.current?.focus();
  };

  const baseClasses = `
    px-3 py-2 rounded-md text-sm border 
    border-[color:var(--color-interaction-base-border)] 
    bg-[color:var(--color-surface-base-background)] 
    text-[color:var(--color-primary-foreground)] 
    focus:outline-none focus:ring-2 focus:ring-offset-2 
    focus:ring-[color:var(--color-brand-border)]
    disabled:bg-[color:var(--color-base-border)] 
    disabled:text-[color:var(--color-subtle-foreground)]
    cursor-pointer
    disabled:cursor-not-allowed
    relative
    text-left
    w-full
    ${className}
  `
    .trim()
    .replace(/\s+/g, " ");

  return (
    <div ref={selectRef} className="relative w-full">
      <button
        ref={buttonRef}
        type="button"
        className={baseClasses}
        onClick={handleToggleDropdown}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        aria-labelledby="select-label"
      >
        <span className="block truncate">{selectedOption ? selectedOption.label : placeholder}</span>
        <span className="absolute inset-y-0 right-0 flex items-center pr-2 pointer-events-none">
          <IconCaretDown className={isOpen ? "rotate-180" : ""} />
        </span>
      </button>

      {isOpen && (
        <div
          className={`
            absolute left-0 right-0 z-50 
            bg-[color:var(--color-surface-base-background)] 
            border border-[color:var(--color-interaction-base-border)] 
            rounded-md shadow-lg max-h-60 overflow-auto
            ${openUpward ? "bottom-full mb-1" : "top-full mt-1"}
          `}
        >
          {options.length === 0 ? (
            <div className="px-3 py-2 text-[color:var(--color-subtle-foreground)] text-sm">No options available</div>
          ) : (
            options.map((option, index) => (
              <button
                key={option.value}
                type="button"
                className={`
                  w-full px-3 py-2 text-left text-sm cursor-pointer
                  ${
                    index === focusedIndex
                      ? "bg-[color:var(--color-interaction-hover-background)]"
                      : "hover:bg-[color:var(--color-interaction-hover-background)]"
                  }
                  ${
                    option.value === value
                      ? "text-[color:var(--color-brand-foreground)] font-medium"
                      : "text-[color:var(--color-primary-foreground)]"
                  }
                `}
                onClick={() => handleOptionClick(option.value)}
                onMouseEnter={() => setFocusedIndex(index)}
              >
                {option.label}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default CustomSelect;
