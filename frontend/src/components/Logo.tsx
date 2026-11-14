import { cx } from "./ui";

/** Logo EasyRent: biểu tượng ngôi nhà (cắt từ logo gốc) + chữ "Easy" xanh teal, "Rent" cam. */
export default function Logo({
  size = "md", tagline = false, className, light = false,
}: { size?: "sm" | "md" | "lg"; tagline?: boolean; className?: string; light?: boolean }) {
  const s = {
    sm: { icon: "h-7", text: "text-lg", tag: "text-[10px]" },
    md: { icon: "h-9", text: "text-xl", tag: "text-xs" },
    lg: { icon: "h-16", text: "text-4xl", tag: "text-sm" },
  }[size];
  return (
    <span className={cx("inline-flex items-center gap-2", className)}>
      <img src="/brand/easyrent-icon.png" alt="" className={cx(s.icon, "w-auto")} />
      <span className="flex flex-col leading-none">
        <span className={cx(s.text, "font-extrabold tracking-tight")}>
          <span className={light ? "text-white" : "text-brand-700"}>Easy</span>
          <span className="text-accent-500">Rent</span>
        </span>
        {tagline && <span className={cx(s.tag, "mt-1 font-medium", light ? "text-white/80" : "text-brand-700")}>Quản Lý Phòng Trọ Dễ Dàng</span>}
      </span>
    </span>
  );
}
