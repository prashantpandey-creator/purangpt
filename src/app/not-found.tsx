import Link from 'next/link';
import Image from 'next/image';

export default function NotFound() {
  return (
    <div className="relative w-full h-screen flex items-center justify-center bg-black overflow-hidden">
      {/* Background Image */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/images/shiva_samadhi.png"
          alt="Shiva in Samadhi"
          fill
          className="object-cover opacity-40 mix-blend-screen"
          priority
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/80 to-transparent" />
        <div className="absolute inset-0 bg-dark-900/40 backdrop-blur-[2px]" />
      </div>

      {/* Content */}
      <div className="relative z-10 text-center px-4 space-y-6 max-w-2xl mt-20">
        <h1 className="text-6xl md:text-8xl font-bold font-cinzel text-gradient opacity-90 drop-shadow-2xl">
          404
        </h1>
        <h2 className="text-2xl md:text-3xl font-semibold text-saffron tracking-wider uppercase drop-shadow-lg">
          Shiva is currently in Samadhi
        </h2>
        <p className="text-gray-300 text-lg md:text-xl leading-relaxed drop-shadow">
          The reality you are looking for has dissolved into the void. This path does not exist in the cosmic dance.
        </p>
        <div className="pt-8">
          <Link 
            href="/"
            className="btn-primary inline-flex items-center gap-2 backdrop-blur-md bg-saffron/10 border-saffron/30 hover:bg-saffron/20 transition-all shadow-xl shadow-saffron/5"
          >
            Return to the Source
          </Link>
        </div>
      </div>
    </div>
  );
}
