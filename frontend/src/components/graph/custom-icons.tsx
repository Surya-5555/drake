import * as React from "react";

// Atomie-style custom SVG icons
// These are not from a standard pack. They are drawn with thicker, softer strokes and playful geometry.

export function AtomieStartIcon({ className, ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} {...props}>
      <path d="M5 10L12 4.5L19 10V18C19 19.1046 18.1046 20 17 20H7C5.89543 20 5 19.1046 5 18V10Z" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M9 20V13C9 12.4477 9.44772 12 10 12H14C14.5523 12 15 12.4477 15 13V20" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

export function AtomieBubbleIcon({ className, ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} {...props}>
      <path d="M4.5 12C4.5 7.85786 7.85786 4.5 12 4.5C16.1421 4.5 19.5 7.85786 19.5 12C19.5 16.1421 16.1421 19.5 12 19.5C10.421 19.5 8.9566 19.0116 7.74737 18.1888L4 19L5.05602 15.6562C4.6974 14.5658 4.5 13.315 4.5 12Z" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M9 12H15" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  );
}

export function AtomieDatabaseIcon({ className, ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} {...props}>
      <ellipse cx="12" cy="7" rx="8" ry="3" stroke="currentColor" strokeWidth="2.5"/>
      <path d="M4 7V12C4 13.6569 7.58172 15 12 15C16.4183 15 20 13.6569 20 12V7" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M4 12V17C4 18.6569 7.58172 20 12 20C16.4183 20 20 18.6569 20 17V12" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  );
}

export function AtomieSparkleIcon({ className, ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} {...props}>
      <path d="M12 4C12 8.41828 8.41828 12 4 12C8.41828 12 12 15.5817 12 20C12 15.5817 15.5817 12 20 12C15.5817 12 12 8.41828 12 4Z" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="18" cy="6" r="1.5" fill="currentColor"/>
      <circle cx="6" cy="18" r="1" fill="currentColor"/>
    </svg>
  );
}

export function AtomieDeleteIcon({ className, ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} {...props}>
      <rect x="5" y="8" width="14" height="12" rx="3" stroke="currentColor" strokeWidth="2.5"/>
      <path d="M8 8V6C8 4.89543 8.89543 4 10 4H14C15.1046 4 16 4.89543 16 6V8" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
      <path d="M3 8H21" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"/>
    </svg>
  );
}

export function AtomieMoreIcon({ className, ...props }: React.SVGProps<SVGSVGElement>) {
  return (
    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" className={className} {...props}>
      <circle cx="5" cy="12" r="1.5" fill="currentColor"/>
      <circle cx="12" cy="12" r="1.5" fill="currentColor"/>
      <circle cx="19" cy="12" r="1.5" fill="currentColor"/>
    </svg>
  );
}
