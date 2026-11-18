
import * as SelectPrimitive from "@radix-ui/react-select";

export type SelectOption = {
  value: string;
  label: string;
};

type ResponsiveSelectProps = {
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  className?: string;
  ariaLabel?: string;
};

const EMPTY = "__easyrent_empty__";

export function ResponsiveSelect({
  value,
  onValueChange,
  options,
  className = "",
  ariaLabel,
}: ResponsiveSelectProps) {
  const selected = options.find((o) => o.value === value);

  return (
    <SelectPrimitive.Root
      value={value === "" ? EMPTY : value}
      onValueChange={(next) =>
        onValueChange(next === EMPTY ? "" : next)
      }
    >
      <SelectPrimitive.Trigger
        aria-label={ariaLabel}
        title={selected?.label}
        className={[
          "flex h-10 w-full min-w-0 max-w-full",
          "items-center justify-between gap-2",
          "rounded-lg border border-slate-300",
          "bg-white px-3 text-left text-sm text-slate-800",
          "outline-none focus-visible:ring-2",
          "focus-visible:ring-teal-600",
          className,
        ].join(" ")}
      >
        <span className="block min-w-0 flex-1 truncate">
          <SelectPrimitive.Value />
        </span>
        <SelectPrimitive.Icon
          className="shrink-0 text-slate-600"
        >
          <span aria-hidden="true">▾</span>
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>

      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          side="bottom"
          align="start"
          sideOffset={4}
          collisionPadding={12}
          className={[
            "z-[1000] overflow-hidden rounded-lg",
            "border border-slate-200 bg-white",
            "text-slate-900 shadow-xl",
          ].join(" ")}
          style={{
            width:
              "min(var(--radix-select-trigger-width), calc(100vw - 24px))",
            maxHeight:
              "min(320px, var(--radix-select-content-available-height))",
          }}
        >
          <SelectPrimitive.ScrollUpButton
            className="py-1 text-center text-xs"
          >
            ▲
          </SelectPrimitive.ScrollUpButton>

          <SelectPrimitive.Viewport className="p-1">
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value === "" ? EMPTY : option.value}
                value={option.value === "" ? EMPTY : option.value}
                textValue={option.label}
                className={[
                  "relative flex w-full cursor-pointer",
                  "items-center rounded-md py-2 pl-3 pr-8",
                  "text-sm leading-5 whitespace-normal",
                  "break-words outline-none",
                  "data-[highlighted]:bg-teal-50",
                  "data-[highlighted]:text-teal-900",
                ].join(" ")}
              >
                <SelectPrimitive.ItemText>
                  {option.label}
                </SelectPrimitive.ItemText>

                <SelectPrimitive.ItemIndicator
                  className="absolute right-2 top-2"
                >
                  ✓
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>

          <SelectPrimitive.ScrollDownButton
            className="py-1 text-center text-xs"
          >
            ▼
          </SelectPrimitive.ScrollDownButton>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
