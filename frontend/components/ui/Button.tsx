import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'secondary' | 'outline' | 'ghost' | 'destructive';
  size?: 'sm' | 'md' | 'lg' | 'icon';
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', isLoading, children, disabled, ...props }, ref) => {
    const variants = {
      default: cn(
        'bg-primary-600 text-white shadow-[0_0_20px_rgba(14,165,233,0.15)]',
        'hover:bg-primary-500 hover:shadow-[0_0_25px_rgba(14,165,233,0.3)]',
        'border border-primary-400/20 active:scale-[0.98]',
        'animate-glow'
      ),
      secondary: 'bg-white/5 text-slate-200 hover:bg-white/10 border border-white/5',
      outline: 'border border-white/10 bg-transparent hover:bg-white/5 text-slate-300',
      ghost: 'text-slate-400 hover:text-white hover:bg-white/5',
      destructive: 'bg-red-500/10 text-red-400 border border-red-500/20 hover:bg-red-500 hover:text-white',
    };

    const sizes = {
      sm: 'h-9 px-4 text-xs tracking-wide',
      md: 'h-11 px-6 text-sm font-medium',
      lg: 'h-14 px-10 text-lg font-heading tracking-tight',
      icon: 'h-11 w-11',
    };

    return (
      <button
        ref={ref}
        className={cn(
          'relative inline-flex items-center justify-center rounded-full transition-all duration-300 ease-out',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500/50',
          'disabled:pointer-events-none disabled:opacity-70',
          variants[variant],
          sizes[size],
          className
        )}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <div className="flex items-center gap-2">
            <svg className="h-4 w-4 animate-spin text-current" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            <span className="opacity-80">Processing...</span>
          </div>
        ) : (
          <span className="relative z-10 flex items-center">{children}</span>
        )}
      </button>
    );
  }
);

Button.displayName = 'Button';