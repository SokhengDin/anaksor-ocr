export const wrap = "mx-auto max-w-[74rem] px-6 max-md:px-5";

const btnShape =
  "inline-flex items-center gap-[.45rem] px-4 py-[.35rem] border rounded-lg font-text text-[.95rem]/[1.4] no-underline cursor-pointer disabled:opacity-55 disabled:cursor-progress";
const quiet = "border-hairline bg-paper text-ink font-normal hover:border-jade hover:text-jade-deep";

export const btn = `${btnShape} min-h-10 border-jade-deep bg-jade-deep text-white font-bold hover:border-jade hover:bg-jade`;
export const btnQuiet = `${btnShape} min-h-10 ${quiet}`;
export const btnSmall = `${btnShape} min-h-8 ${quiet}`;
export const btnToggle = `${btnQuiet} aria-pressed:border-jade-deep aria-pressed:text-jade-deep aria-pressed:font-bold aria-pressed:bg-[color-mix(in_srgb,var(--color-jade)_8%,var(--color-paper))]`;

export const hint = "m-0 text-[.875rem] text-ink-soft";
export const meta = "text-[.875rem] text-ink-soft";
export const panelHead = "flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1";

const noticeShape = "mt-0 mx-0 mb-4 px-4 py-3 border-l-[3px] rounded-r-md";
export const notice = `${noticeShape} border-l-saffron bg-[color-mix(in_srgb,var(--color-saffron)_9%,var(--color-paper))]`;
export const noticeError = `${noticeShape} border-l-danger bg-[color-mix(in_srgb,var(--color-danger)_7%,var(--color-paper))]`;

export const marker =
  "absolute grid place-items-center size-8 rounded-full bg-saffron text-ink font-text text-base/none font-bold shadow-[0_0_0_3px_var(--color-paper)] max-sm:size-[1.6rem] max-sm:text-[.85rem]/none";

export const brand = "flex items-center gap-[.6rem] text-ink no-underline font-bold whitespace-nowrap [&_img]:size-[1.85rem] [&_img]:rounded-[7px]";
export const wordmark = "text-[1.05rem] tracking-[-.005em] [&_span]:text-ink-soft [&_span]:font-normal";

export const tableWrap = "overflow-x-auto mb-5 border border-hairline rounded-lg";
export const tdNum = "tabular-nums whitespace-nowrap";
export const note =
  "flex gap-[.7rem] mb-5 px-4 py-[.85rem] border-l-[3px] border-l-saffron rounded-r-md bg-[color-mix(in_srgb,var(--color-saffron)_9%,var(--color-paper))] [&_svg]:mt-[.4rem] [&_svg]:text-saffron-ink [&_p]:m-0";
export const steps =
  "list-none p-0 [counter-reset:step] [&>li]:relative [&>li]:pl-[2.6rem] [&>li]:mb-[.9rem] [&>li]:[counter-increment:step] [&>li]:before:content-[counter(step)] [&>li]:before:absolute [&>li]:before:left-0 [&>li]:before:top-[.2rem] [&>li]:before:grid [&>li]:before:place-items-center [&>li]:before:size-[1.7rem] [&>li]:before:rounded-full [&>li]:before:bg-saffron [&>li]:before:font-text [&>li]:before:text-[.9rem]/none [&>li]:before:font-bold";
export const fields =
  "grid grid-cols-[max-content_1fr] gap-x-5 gap-y-[.4rem] mb-5 [&_dt_code]:font-bold [&_dd]:m-0 max-sm:grid-cols-1 max-sm:gap-0 max-sm:[&_dd]:mb-[.7rem]";
