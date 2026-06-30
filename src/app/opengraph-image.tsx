import { ImageResponse } from "next/og";

// export const dynamic = "force-static"; // Removed due to edge runtime conflict
export const runtime = "edge";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const alt = "PuranGPT — AI Oracle of the Sacred Texts";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          background: "#0a0a0a",
          backgroundImage:
            "radial-gradient(circle at 50% 50%, rgba(232,182,63, 0.15) 0%, rgba(232,182,63, 0) 70%)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textAlign: "center",
            padding: "60px",
          }}
        >
          <h1
            style={{
              fontSize: "80px",
              fontWeight: "bold",
              color: "#e8b63f",
              margin: "0 0 20px 0",
              fontFamily: "serif",
            }}
          >
            PuranGPT
          </h1>
          <p
            style={{
              fontSize: "40px",
              color: "#b8b8b8",
              margin: "0",
              fontWeight: "300",
              fontFamily: "serif",
            }}
          >
            AI Oracle of the Sacred Texts
          </p>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}
