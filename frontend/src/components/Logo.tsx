import { ImgHTMLAttributes } from 'react';

interface LogoIconProps extends ImgHTMLAttributes<HTMLImageElement> {
  size?: number;
}

export function RemoraIcon({ size = 32, className, alt = '', ...props }: LogoIconProps) {
  return (
    <img
      src="/assets/logo.png"
      alt={alt}
      width={size}
      height={Math.round(size * 0.82)}
      className={`object-contain ${className ?? ''}`}
      {...props}
    />
  );
}
