import Link from "next/link";
import { MapPinOff, Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="glass-panel max-w-md w-full p-8 text-center">
        <MapPinOff className="mx-auto mb-4 text-indigo-400" size={48} />
        <h1 className="text-xl font-bold mb-2">Page not found</h1>
        <p className="text-gray-500 text-sm mb-6">
          The page you&apos;re looking for doesn&apos;t exist or has moved.
        </p>
        <Link
          href="/"
          className="neu-button inline-flex items-center justify-center gap-2 py-3 px-6 bg-indigo-500 text-white font-bold rounded-xl"
        >
          <Home size={16} /> Back to Home
        </Link>
      </div>
    </div>
  );
}
