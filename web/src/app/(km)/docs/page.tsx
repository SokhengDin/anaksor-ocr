import { Docs } from "@/components/Docs";
import { km } from "@/i18n/km";
import { pageMetadata } from "@/lib/meta";

export const metadata = pageMetadata(km, "docs");

export default function Page() {
  return <Docs t={km} />;
}
