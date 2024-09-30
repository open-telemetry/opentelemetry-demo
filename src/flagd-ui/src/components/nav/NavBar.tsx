// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const NavBar = () => {
  const pathname = usePathname();

  return (
    <nav className="bg-gray-800 p-4 sm:p-6">
      <div className="container mx-auto flex items-center justify-between">
        <Link href="/" className="text-xl font-bold text-white">
          Flagd Configurator
        </Link>
        <ul className="flex space-x-2 sm:space-x-4">
          <li>
            <Link
              href="/"
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                pathname === "/"
                  ? "bg-blue-700 text-white underline underline-offset-4"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              } transition-all duration-200`}
            >
              Basic
            </Link>
          </li>
          <li>
            <Link
              href="/advanced"
              className={`rounded-md px-3 py-2 text-sm font-medium ${
                pathname === "/advanced"
                  ? "bg-blue-700 text-white underline underline-offset-4"
                  : "text-gray-300 hover:bg-gray-700 hover:text-white"
              } transition-all duration-200`}
            >
              Advanced
            </Link>
          </li>
        </ul>
      </div>
    </nav>
  );
};

export default NavBar;
