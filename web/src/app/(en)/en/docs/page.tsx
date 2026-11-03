import { Docs } from "@/components/Docs";
import { en } from "@/i18n/en";
import { pageMetadata } from "@/lib/meta";

export const metadata = pageMetadata(en, "docs");

export default function Page() {
  return <Docs t={en} />;
}
