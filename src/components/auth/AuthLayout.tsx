import { ReactNode } from "react";
import { Logo } from "@/components/ui/Logo";

interface AuthLayoutProps {
  children: ReactNode;
  heading: string;
  subheading?: string;
  bottomLink?: {
    text: string;
    href: string;
  };
}

export function AuthLayout({
  children,
  heading,
  subheading,
  bottomLink,
}: AuthLayoutProps) {
  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-dark-900">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-saffron/5 rounded-full blur-3xl animate-pulse" />
        <div className="absolute top-1/3 -left-40 w-80 h-80 bg-amber-500/5 rounded-full blur-3xl animate-pulse" />
      </div>

      <div className="relative z-10 w-full max-w-md">
        <div className="text-center mb-8">
          <div className="flex justify-center mb-4">
            <Logo size={72} glow="lg" priority />
          </div>
          <h1 className="text-3xl font-bold font-cinzel text-gradient mb-2">
            PuranGPT
          </h1>
          <p className="text-gray-400 text-sm">AI Oracle of Sacred Texts</p>
        </div>

        <div className="rounded-2xl border border-gray-700 bg-dark-800 p-8 shadow-2xl">
          <h2 className="text-2xl font-bold text-white mb-2">{heading}</h2>
          {subheading && (
            <p className="text-gray-400 text-sm mb-8">{subheading}</p>
          )}

          <div className="mb-6">{children}</div>

          {bottomLink && (
            <div className="text-center text-sm text-gray-400">
              {bottomLink.text}{" "}
              <a
                href={bottomLink.href}
                className="text-saffron hover:text-amber-400 font-semibold transition-colors"
              >
                {bottomLink.href.includes("login") ? "Log in" : "Sign up"}
              </a>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-gray-500 mt-8">
          By using PuranGPT, you agree to our Terms & Privacy Policy
        </p>
      </div>
    </div>
  );
}
