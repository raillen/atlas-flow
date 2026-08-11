import type { FC } from "react";

export interface AtlasLogoProps {
  size?: number;
  className?: string;
}

export const AtlasLogo: FC<AtlasLogoProps> = ({ size = 24, className }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-label="Atlas Flow"
  >
    <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" />
    <ellipse cx="12" cy="12" rx="6" ry="10" stroke="currentColor" strokeWidth="1.5" />
    <line x1="2" y1="12" x2="22" y2="12" stroke="currentColor" strokeWidth="1.5" />
    <line x1="12" y1="2" x2="12" y2="22" stroke="currentColor" strokeWidth="1.5" />
  </svg>
);
