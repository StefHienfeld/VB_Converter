import { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface MetricWidgetProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  subValue?: string;
  variant?: "primary" | "success" | "warning" | "default";
  className?: string;
}

export const MetricWidget = ({
  icon: Icon,
  label,
  value,
  subValue,
  variant = "default",
  className,
}: MetricWidgetProps) => {
  const iconColorClass = {
    primary: "text-primary bg-primary/10",
    success: "text-success bg-success/10",
    warning: "text-warning bg-warning/10",
    default: "text-muted-foreground bg-muted",
  }[variant];

  const valueColorClass = {
    primary: "text-primary",
    success: "text-success",
    warning: "text-warning",
    default: "text-foreground",
  }[variant];

  return (
    <div className={cn("metric-widget", className)}>
      <div className={cn("w-12 h-12 rounded-2xl flex items-center justify-center mb-4", iconColorClass)}>
        <Icon className="w-6 h-6" />
      </div>
      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-2">
        {label}
      </p>
      <p className={cn("text-3xl font-bold", valueColorClass)}>
        {value}
      </p>
      {subValue && (
        <p className="text-sm text-muted-foreground mt-1">{subValue}</p>
      )}
    </div>
  );
};
