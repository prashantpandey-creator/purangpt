import { NextResponse } from "next/server";

const OPENAI_KEY = process.env.OPENAI_API_KEY;
const OPENAI_URL = "https://api.openai.com/v1/audio/transcriptions";

export async function POST(req: Request) {
  if (!OPENAI_KEY) {
    return NextResponse.json({ error: "Transcription service not configured" }, { status: 503 });
  }
  let formData: FormData;
  try {
    formData = await req.formData();
  } catch {
    return NextResponse.json({ error: "Expected multipart/form-data" }, { status: 400 });
  }
  const file = formData.get("file");
  if (!file || !(file instanceof Blob)) {
    return NextResponse.json({ error: "file field required" }, { status: 400 });
  }
  // Forward the language hint the client sends (hi-IN, en-US, ru-RU…).
  // gpt-4o-transcribe can auto-detect, but an explicit hint is slightly faster.
  const langHint = (formData.get("lang") as string | null) || "";

  const body = new FormData();
  body.append("file", file, "audio.webm");
  body.append("model", "gpt-4o-transcribe");
  body.append("response_format", "json");
  if (langHint) body.append("language", langHint.split("-")[0]); // BCP-47 → ISO-639-1

  try {
    const res = await fetch(OPENAI_URL, {
      method: "POST",
      headers: { Authorization: `Bearer ${OPENAI_KEY}` },
      body,
      signal: AbortSignal.timeout(8_000), // fail fast — gpt-4o-transcribe returns in <3s
    });
    if (!res.ok) {
      const detail = await res.text().catch(() => "");
      return NextResponse.json(
        { error: "Transcription failed", detail: detail.slice(0, 200) },
        { status: 502 }
      );
    }
    const data = (await res.json()) as { text?: string };
    return NextResponse.json({ text: (data.text || "").trim() });
  } catch (err) {
    return NextResponse.json({ error: "Network error", detail: String(err).slice(0, 200) }, { status: 502 });
  }
}
