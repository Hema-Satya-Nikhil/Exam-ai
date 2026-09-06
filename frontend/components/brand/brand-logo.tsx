import Image from 'next/image';

type BrandLogoProps = {
  className?: string;
  priority?: boolean;
};

export function BrandLogo({ className = 'h-24 w-24', priority = false }: BrandLogoProps) {
  return (
    <Image
      src="/branding/examcraft-ai-logo.png"
      alt="ExamCraft AI"
      width={1254}
      height={1254}
      priority={priority}
      className={`object-contain ${className}`}
    />
  );
}
