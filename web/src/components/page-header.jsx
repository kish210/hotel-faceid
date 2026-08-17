import { cn } from "@/lib/utils";

export function PageHeader({ title, description, children, className }) {
  return (
    <div className={cn("mb-6 flex flex-wrap items-center justify-between gap-3", className)}>
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {description && <p className="text-muted-foreground mt-1 text-sm">{description}</p>}
      </div>
      {children}
    </div>
  );
}
