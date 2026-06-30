import { Loader2 } from "lucide-react";

export default function Loading() {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-dark-900">
      <Loader2 className="h-8 w-8 animate-spin text-saffron" />
    </div>
  );
}
