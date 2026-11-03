import { Home } from "@/components/Home";
import { en } from "@/i18n/en";
import { pageMetadata } from "@/lib/meta";

export const metadata = pageMetadata(en, "home");

export default function Page() {
  return <Home t={en} />;
}
