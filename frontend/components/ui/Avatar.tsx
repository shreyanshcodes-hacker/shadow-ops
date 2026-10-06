import { clsx } from 'clsx';

interface AvatarProps extends React.HTMLAttributes<HTMLDivElement> {
  src?: string | null;
  alt?: string;
  fallback?: React.ReactNode;
}

export function Avatar({ src, alt, fallback, className, ...props }: AvatarProps) {
  return (
    <div
      className={clsx('relative inline-flex shrink-0 overflow-hidden rounded-full bg-accent-glow', className)}
      {...props}
    >
      {src ? (
        <img
          src={src}
          alt={alt || ''}
          className="aspect-square h-full w-full object-cover"
          loading="lazy"
        />
      ) : (
        fallback || (
          <svg className="h-full w-full text-accent-DEFAULT" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z" />
          </svg>
        )
      )}
    </div>
  );
}

export function AvatarFallback({ children }: { children: React.ReactNode }) {
  return <span className="flex h-full w-full items-center justify-center text-foreground-muted">{children}</span>;
}