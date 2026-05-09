import { Loader2 } from "lucide-react";

interface SpinnerProps {
  size?: number;
  className?: string;
  label?: string;
}

export default function Spinner({ size = 20, className = "", label }: SpinnerProps) {
  return (
    <div className={`flex items-center justify-center gap-2 text-gray-500 ${className}`}>
      <Loader2 size={size} className="animate-spin" />
      {label && <span className="text-sm">{label}</span>}
    </div>
  );
}
