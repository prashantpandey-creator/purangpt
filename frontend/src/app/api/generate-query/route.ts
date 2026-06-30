import { NextResponse } from "next/server";

const GROQ_API_KEY = process.env.GROQ_API_KEY; // The user will need to set this in .env.local

export async function POST(req: Request) {
  if (!GROQ_API_KEY) {
    return NextResponse.json(
      { error: "Groq API key not configured." },
      { status: 500 }
    );
  }

  try {
    const { query } = await req.json();

    if (!query) {
      return NextResponse.json({ error: "Query is required" }, { status: 400 });
    }

    const response = await fetch("https://api.groq.com/openai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${GROQ_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        model: "llama-3.3-70b-versatile",
        messages: [
          {
            role: "system",
            content: `You are an expert Vedic Research Assistant. Your job is to take an informal, potentially vague question from a user and formulate it into a precise, highly structured, scholarly research prompt that will be fed into a deep-research RAG system.

Guidelines:
1. Identify the core concepts (e.g., deities, philosophical schools, specific texts).
2. Ask the system to 'Analyze', 'Compare', 'Trace the origins of', or 'Synthesize'.
3. Maintain a formal, academic tone.
4. Keep the final prompt under 3 sentences.
5. Do NOT answer the question. ONLY output the formulated prompt.

Example User Input: 'what does shiva say about breathing'
Example Output: 'Analyze the references to Pranayama and breath control as attributed to Lord Shiva across the Agamas and Puranas, focusing on the intersection of esoteric yoga and devotion.'`
          },
          {
            role: "user",
            content: query
          }
        ],
        temperature: 0.3,
        max_tokens: 150,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error?.message || "Failed to generate query");
    }

    const data = await response.json();
    const formulatedQuery = data.choices[0].message.content.trim();

    return NextResponse.json({ formulatedQuery });
  } catch (error: any) {
    console.error("Error generating query:", error);
    return NextResponse.json(
      { error: "Failed to generate query" },
      { status: 500 }
    );
  }
}
