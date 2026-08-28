/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

"use client";

import React from "react";
import { Language } from "@/app/hooks/useConfig";
import CustomSelect from "./CustomSelect";

interface LanguageDropdownProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  excludeLanguage?: string; // Language to exclude from options (e.g., exclude source when selecting target)
  languages: Language[]; // Languages passed from parent component
}

const LanguageDropdown: React.FC<LanguageDropdownProps> = ({
  label,
  value,
  onChange,
  disabled = false,
  excludeLanguage,
  languages,
}) => {
  const availableLanguages = languages.filter((lang) => lang.code !== excludeLanguage);

  const selectOptions = availableLanguages.map((language) => ({
    value: language.code,
    label: language.label,
  }));

  return (
    <div className="flex gap-2 flex-col flex-1">
      <label className="text-sm text-[color:var(--color-primary-foreground)] mr-2 w-40">{label}</label>
      <CustomSelect value={value} onChange={onChange} options={selectOptions} disabled={disabled} className="" />
    </div>
  );
};

export default LanguageDropdown;
