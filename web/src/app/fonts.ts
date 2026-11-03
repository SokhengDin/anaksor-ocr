import localFont from "next/font/local";

// Battambang shapes Khmer and Latin alike; Moul Light only sets the big Khmer display names.
export const battambang = localFont({
  src: [
    { path: "../fonts/battambang-regular.woff2", weight: "400", style: "normal" },
    { path: "../fonts/battambang-bold.woff2", weight: "700", style: "normal" },
  ],
  variable: "--font-battambang",
  display: "swap",
});

export const moul = localFont({
  src: "../fonts/moul-light.woff2",
  variable: "--font-moul",
  display: "swap",
});
