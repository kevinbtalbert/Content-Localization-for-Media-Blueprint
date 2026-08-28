/*
 * SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0
 */

import Card from "./Card";

const Header = ({ className, title, description }: { className?: string; title: string; description: string }) => {
  return (
    <Card className={`${className ?? ""}`} padding="p-6">
      <div className="flex flex-col" style={{ gap: "2px" }}>
        <h2 className="text-xl text-[color:var(--color-secondary-foreground)]">nvidia</h2>
        <h1 className="text-2xl font-semibold">{title}</h1>
        <p className="text-sm">{description}</p>
      </div>
    </Card>
  );
};

export default Header;
