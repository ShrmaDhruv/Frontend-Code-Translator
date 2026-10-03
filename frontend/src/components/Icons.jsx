import { AUTO_DETECT } from "../constants";

function Svg({ size = 16, children, ...rest }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

export function LogoMark({ size = 30 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <rect width="32" height="32" rx="8" className="logo-bg" />
      <path
        d="M12 9 6 16l6 7M20 9l6 7-6 7"
        fill="none"
        className="logo-stroke"
        strokeWidth="2.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="16" cy="16" r="2" className="logo-dot" />
    </svg>
  );
}

export function SwapIcon(props) {
  return (
    <Svg {...props}>
      <path d="M7 7h13l-3.5-3.5M17 17H4l3.5 3.5" />
    </Svg>
  );
}

export function PlayIcon(props) {
  return (
    <Svg {...props} fill="currentColor" stroke="none">
      <path d="M8 5.5v13a1 1 0 0 0 1.5.86l11-6.5a1 1 0 0 0 0-1.72l-11-6.5A1 1 0 0 0 8 5.5Z" />
    </Svg>
  );
}

export function CopyIcon(props) {
  return (
    <Svg {...props}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15V6a2 2 0 0 1 2-2h9" />
    </Svg>
  );
}

export function CheckIcon(props) {
  return (
    <Svg {...props}>
      <path d="m5 12.5 4.5 4.5L19 7.5" />
    </Svg>
  );
}

export function CrossIcon(props) {
  return (
    <Svg {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Svg>
  );
}

export function AlertIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 4 2.8 19.5h18.4L12 4Z" />
      <path d="M12 10v4.5M12 17.2v.3" />
    </Svg>
  );
}

export function SunIcon(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
    </Svg>
  );
}

export function MoonIcon(props) {
  return (
    <Svg {...props}>
      <path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />
    </Svg>
  );
}

function AutoIcon(props) {
  return (
    <Svg {...props}>
      <path d="M12 3.5 13.8 9l5.7 1.8-5.7 1.8L12 18.5l-1.8-5.9-5.7-1.8L10.2 9 12 3.5Z" />
      <path d="M19 16.5v4M17 18.5h4" />
    </Svg>
  );
}

function ReactIcon(props) {
  return (
    <Svg {...props} strokeWidth="1.4">
      <ellipse cx="12" cy="12" rx="10" ry="4" />
      <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(60 12 12)" />
      <ellipse cx="12" cy="12" rx="10" ry="4" transform="rotate(120 12 12)" />
      <circle cx="12" cy="12" r="1.7" fill="currentColor" stroke="none" />
    </Svg>
  );
}

function VueIcon(props) {
  return (
    <Svg {...props} strokeWidth="1.7">
      <path d="M2.5 4.5 12 20.5l9.5-16h-4.2L12 13.4 6.7 4.5H2.5Z" />
      <path d="M9.2 4.5 12 9.2l2.8-4.7" />
    </Svg>
  );
}

function AngularIcon(props) {
  return (
    <Svg {...props} strokeWidth="1.7">
      <path d="M12 2.5 3.5 5.7l1.4 11.2L12 21.5l7.1-4.6 1.4-11.2L12 2.5Z" />
      <path d="m8.3 15.5 3.7-8.5 3.7 8.5M9.6 12.8h4.8" />
    </Svg>
  );
}

function HtmlIcon(props) {
  return (
    <Svg {...props} strokeWidth="1.7">
      <path d="m4 3 1.5 15.5L12 21l6.5-2.5L20 3H4Z" />
      <path d="m10.5 9.5-2.3 2.5 2.3 2.5M13.5 9.5l2.3 2.5-2.3 2.5" />
    </Svg>
  );
}

const FRAMEWORK_ICONS = {
  [AUTO_DETECT]: AutoIcon,
  React: ReactIcon,
  Vue: VueIcon,
  Angular: AngularIcon,
  HTML: HtmlIcon,
};

export function FrameworkIcon({ framework, size = 16 }) {
  const Icon = FRAMEWORK_ICONS[framework] || AutoIcon;
  return <Icon size={size} />;
}
