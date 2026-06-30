import Link from "next/link";
import { Navbar } from "@/components/landing/Navbar";
import { Footer } from "@/components/landing/Footer";

export const metadata = {
  title: "API Documentation · PuranGPT",
  description:
    "Call PuranGPT from your own code. A Pro-only REST endpoint that returns cited, source-grounded answers from the scriptural corpus.",
};

function Code({ children }: { children: React.ReactNode }) {
  return (
    <pre
      className="overflow-x-auto rounded-xl border border-white/10 p-4 text-[13px] leading-relaxed text-[#e5e2e1]"
      style={{ background: "#0b0b0b", fontFamily: "var(--font-mono, ui-monospace, monospace)" }}
    >
      <code>{children}</code>
    </pre>
  );
}

export default function DocsPage() {
  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-[#000] text-[#e5e2e1]">
        <section className="mx-auto max-w-3xl px-4 md:px-8 pt-32 pb-20">
          <span className="text-[10px] uppercase tracking-[0.25em] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>
            Developers
          </span>
          <h1
            className="mt-3 text-4xl md:text-5xl text-transparent bg-clip-text bg-gradient-to-b from-[#ffd080] via-[#f0cd80] to-[#e8b63f]"
            style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}
          >
            PuranGPT API
          </h1>
          <p className="mt-5 text-base leading-8 text-[#d8c594]" style={{ fontFamily: "var(--font-body)" }}>
            Ask the scriptural corpus from your own code and get back cited, source-grounded
            answers. The API is available on the <strong className="text-[#f0cd80]">Pro</strong> plan.
          </p>

          {/* Get a key */}
          <h2 className="mt-12 text-2xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
            1. Get an API key
          </h2>
          <p className="mt-3 text-sm leading-7 text-[#c7ae9a]" style={{ fontFamily: "var(--font-body)" }}>
            Open <Link href="/settings" className="text-[#e8b63f] hover:underline">Settings → API</Link> and
            create a key. It looks like <code className="text-[#f0cd80]">pgk_live_…</code> and is shown only
            once, so copy it somewhere safe. You can revoke a key at any time.
          </p>

          {/* Endpoint */}
          <h2 className="mt-12 text-2xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
            2. Call the endpoint
          </h2>
          <p className="mt-3 text-sm leading-7 text-[#c7ae9a]" style={{ fontFamily: "var(--font-body)" }}>
            Send a <code className="text-[#f0cd80]">POST</code> to <code className="text-[#f0cd80]">/api/v1/chat</code> with
            your key in the <code className="text-[#f0cd80]">Authorization</code> header.
          </p>

          <div className="mt-4">
            <Code>{`curl https://purangpt.com/api/v1/chat \\
  -H "Authorization: Bearer pgk_live_your_key_here" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "What does the Bhagavad Gita say about acting without attachment to results?",
    "mode": "research",
    "language": "en"
  }'`}</Code>
          </div>

          {/* Request */}
          <h2 className="mt-12 text-2xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
            Request body
          </h2>
          <div className="mt-4 overflow-hidden rounded-xl border border-white/10">
            {[
              ["query", "string (required)", "Your question."],
              ["mode", '"research" | "guide"', 'Default "research". "guide" answers in Guruji\'s voice.'],
              ["language", '"en" | "hi" | "ru"', 'Default "en".'],
              ["top_k", "number 1–25", "How many source passages to retrieve. Default 10."],
              ["session_id", "string", "Optional — continues a prior conversation."],
              ["stream", "boolean", "Default false. true returns a raw SSE stream instead of JSON."],
            ].map(([field, type, desc], i) => (
              <div
                key={field}
                className="grid grid-cols-[120px_1fr] gap-3 px-4 py-3 text-sm"
                style={{ background: i % 2 ? "rgba(255,255,255,0.02)" : "transparent" }}
              >
                <div>
                  <code className="text-[#f0cd80]">{field}</code>
                  <div className="mt-0.5 text-[11px] text-[#a38d7c]" style={{ fontFamily: "var(--font-ui)" }}>{type}</div>
                </div>
                <p className="text-[#c7ae9a]" style={{ fontFamily: "var(--font-body)" }}>{desc}</p>
              </div>
            ))}
          </div>

          {/* Response */}
          <h2 className="mt-12 text-2xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
            Response
          </h2>
          <p className="mt-3 text-sm leading-7 text-[#c7ae9a]" style={{ fontFamily: "var(--font-body)" }}>
            By default you get a single JSON object with the assembled answer and its citations:
          </p>
          <div className="mt-4">
            <Code>{`{
  "answer": "Krishna tells Arjuna that one has a right to action alone…",
  "citations": [
    {
      "text_name": "Bhagavad Gita",
      "reference": "2.47",
      "text": "You have a right to your duty, but never to the fruits of action.",
      "language": "sa"
    }
  ],
  "session_id": "api:…",
  "grounding_quality": "high"
}`}</Code>
          </div>

          {/* Errors */}
          <h2 className="mt-12 text-2xl text-[#e5e2e1]" style={{ fontFamily: "var(--font-display)", fontWeight: 600 }}>
            Errors
          </h2>
          <div className="mt-4 overflow-hidden rounded-xl border border-white/10">
            {[
              ["401", "Missing or invalid API key."],
              ["403", "The key's account is no longer on a Pro plan."],
              ["400", "Missing query or malformed JSON body."],
              ["429", "Rate limit reached — slow down and retry."],
            ].map(([code, desc], i) => (
              <div
                key={code}
                className="grid grid-cols-[60px_1fr] gap-3 px-4 py-3 text-sm"
                style={{ background: i % 2 ? "rgba(255,255,255,0.02)" : "transparent" }}
              >
                <code className="text-[#f0cd80]">{code}</code>
                <p className="text-[#c7ae9a]" style={{ fontFamily: "var(--font-body)" }}>{desc}</p>
              </div>
            ))}
          </div>

          <div className="mt-12 flex flex-wrap gap-3">
            <Link href="/settings" className="btn-primary inline-flex items-center gap-2 rounded-full px-7 py-3 text-sm font-semibold">
              Create an API key
            </Link>
            <Link href="/chat" className="btn-secondary inline-flex items-center gap-2 rounded-full px-7 py-3 text-sm font-semibold">
              Try it in the app
            </Link>
          </div>
        </section>
      </main>
      <Footer />
    </>
  );
}
