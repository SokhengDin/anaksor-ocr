import { Home } from "@/components/Home";
import { km } from "@/i18n/km";
import { pageMetadata } from "@/lib/meta";

export const metadata = pageMetadata(km, "home");

export default function Page() {
  return <Home t={km} />;
}
