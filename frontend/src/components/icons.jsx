export function Icon({ children, size = 20, className = "", ...props }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`ui-icon ${className}`.trim()}
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  );
}

export function UserIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5.5 19.5a6.5 6.5 0 0 1 13 0" />
    </Icon>
  );
}

export function CreditCardIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3" y="5.5" width="18" height="13" rx="2" />
      <path d="M3 10h18" />
      <path d="M7 15h3" />
    </Icon>
  );
}

export function GiftIcon(props) {
  return (
    <Icon {...props}>
      <rect x="4" y="11" width="16" height="9" rx="1.5" />
      <path d="M12 7v13" />
      <path d="M4 11h16" />
      <path d="M12 7c0-2.2 1.4-3.5 3.2-3.5 1.3 0 2.3 1 2.3 2.3C17.5 7.4 14.2 8.2 12 7Z" />
      <path d="M12 7c0-2.2-1.4-3.5-3.2-3.5C8.5 3.5 7.5 4.5 7.5 5.8 7.5 7.4 10.8 8.2 12 7Z" />
    </Icon>
  );
}

export function FileTextIcon(props) {
  return (
    <Icon {...props}>
      <path d="M14 3.5H8A2.5 2.5 0 0 0 5.5 6v12A2.5 2.5 0 0 0 8 20.5h8A2.5 2.5 0 0 0 18.5 18V8.5L14 3.5Z" />
      <path d="M14 3.5V8.5h4.5" />
      <path d="M9 12.5h6M9 16h6" />
    </Icon>
  );
}

export function SettingsIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9c.3.7.9 1.2 1.6 1.4H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1Z" />
    </Icon>
  );
}

export function BellIcon(props) {
  return (
    <Icon {...props}>
      <path d="M18 16v-5a6 6 0 1 0-12 0v5l-1.5 2h15L18 16Z" />
      <path d="M10 19a2 2 0 0 0 4 0" />
    </Icon>
  );
}

export function MenuIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4 7h16M4 12h16M4 17h16" />
    </Icon>
  );
}

export function LogOutIcon(props) {
  return (
    <Icon {...props}>
      <path d="M9 5.5H6.5A2.5 2.5 0 0 0 4 8v8a2.5 2.5 0 0 0 2.5 2.5H9" />
      <path d="M10 12h10" />
      <path d="m16 8 4 4-4 4" />
    </Icon>
  );
}

export function PencilIcon(props) {
  return (
    <Icon {...props}>
      <path d="M12 20h9" />
      <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z" />
    </Icon>
  );
}

export function PlusIcon(props) {
  return (
    <Icon {...props}>
      <path d="M12 5v14M5 12h14" />
    </Icon>
  );
}

export function MinusIcon(props) {
  return (
    <Icon {...props}>
      <path d="M5 12h14" />
    </Icon>
  );
}

export function TrashIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3" />
    </Icon>
  );
}

export function PhoneIcon(props) {
  return (
    <Icon {...props}>
      <path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6 19.8 19.8 0 0 1-3.1-8.6A2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1.9.3 1.8.6 2.6a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.5-1.1a2 2 0 0 1 2.1-.5c.8.3 1.7.5 2.6.6A2 2 0 0 1 22 16.9Z" />
    </Icon>
  );
}

export function CameraIcon(props) {
  return (
    <Icon {...props}>
      <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h3.2l1.6-2.4A2 2 0 0 1 9.5 3h5a2 2 0 0 1 1.7.6L17.8 6H21a2 2 0 0 1 2 2Z" />
      <circle cx="12" cy="13" r="4" />
    </Icon>
  );
}

export function MapPinIcon(props) {
  return (
    <Icon {...props}>
      <path d="M12 21s7-5.3 7-11a7 7 0 1 0-14 0c0 5.7 7 11 7 11Z" />
      <circle cx="12" cy="10" r="2.5" />
    </Icon>
  );
}

export function CheckIcon(props) {
  return (
    <Icon {...props}>
      <path d="m5 12 5 5 9-10" />
    </Icon>
  );
}

export function StarIcon(props) {
  return (
    <Icon {...props}>
      <path d="m12 3.5 2.4 4.9 5.4.8-3.9 3.8.9 5.4L12 16.2l-4.8 2.6.9-5.4-3.9-3.8 5.4-.8L12 3.5Z" />
    </Icon>
  );
}

export function UploadIcon(props) {
  return (
    <Icon {...props}>
      <path d="M12 16V5" />
      <path d="m8 9 4-4 4 4" />
      <path d="M5 19h14" />
    </Icon>
  );
}

export function DownloadIcon(props) {
  return (
    <Icon {...props}>
      <path d="M12 5v11" />
      <path d="m8 12 4 4 4-4" />
      <path d="M5 19h14" />
    </Icon>
  );
}

export function PrinterIcon(props) {
  return (
    <Icon {...props}>
      <path d="M6 9V3.5h12V9" />
      <path d="M6 18H4.5A1.5 1.5 0 0 1 3 16.5v-5A1.5 1.5 0 0 1 4.5 10h15A1.5 1.5 0 0 1 21 11.5v5a1.5 1.5 0 0 1-1.5 1.5H18" />
      <rect x="6" y="14.5" width="12" height="6" rx="1" />
    </Icon>
  );
}

export function ClockIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 8v5l3 2" />
    </Icon>
  );
}

export function CalendarIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2" />
      <path d="M8 3.5v3M16 3.5v3M3.5 10h17" />
    </Icon>
  );
}

export function BuildingIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4 20V7.5L12 4l8 3.5V20" />
      <path d="M9 20v-6h6v6" />
      <path d="M9 10h.01M15 10h.01M9 14h.01M15 14h.01" />
    </Icon>
  );
}

export function BriefcaseIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="7.5" width="17" height="12" rx="2" />
      <path d="M8 7.5V6a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v1.5" />
      <path d="M3.5 13h17" />
    </Icon>
  );
}

export function MailIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
      <path d="m4 7 8 6 8-6" />
    </Icon>
  );
}

export function GraduationIcon(props) {
  return (
    <Icon {...props}>
      <path d="m3 9 9-4 9 4-9 4-9-4Z" />
      <path d="M7 11.5v4.2c0 .4 2.2 2.3 5 2.3s5-1.9 5-2.3v-4.2" />
      <path d="M21 9v6" />
    </Icon>
  );
}

export function IdCardIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3" y="5.5" width="18" height="13" rx="2" />
      <circle cx="9" cy="12" r="2" />
      <path d="M14 10.5h4M14 13.5h4" />
    </Icon>
  );
}

export function ChevronRightIcon(props) {
  return (
    <Icon {...props}>
      <path d="m9 6 6 6-6 6" />
    </Icon>
  );
}

export function ShieldIcon(props) {
  return (
    <Icon {...props}>
      <path d="M12 3.5 5 6.5v5.2c0 4.2 2.9 7.3 7 8.8 4.1-1.5 7-4.6 7-8.8V6.5L12 3.5Z" />
    </Icon>
  );
}

export function LayoutDashboardIcon(props) {
  return (
    <Icon {...props}>
      <rect x="3.5" y="3.5" width="7.5" height="7.5" rx="1.5" />
      <rect x="13" y="3.5" width="7.5" height="4.5" rx="1.5" />
      <rect x="13" y="10" width="7.5" height="10.5" rx="1.5" />
      <rect x="3.5" y="13" width="7.5" height="7.5" rx="1.5" />
    </Icon>
  );
}

export function ClipboardListIcon(props) {
  return (
    <Icon {...props}>
      <rect x="6" y="4.5" width="12" height="16" rx="2" />
      <path d="M9 4.5V3.5h6v1" />
      <path d="M9 10h6M9 13.5h6M9 17h4" />
    </Icon>
  );
}

export function SearchIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="11" cy="11" r="6" />
      <path d="m16 16 4 4" />
    </Icon>
  );
}

export function RefreshIcon(props) {
  return (
    <Icon {...props}>
      <path d="M20 12a8 8 0 1 1-2.2-5.5" />
      <path d="M20 4v5h-5" />
    </Icon>
  );
}

export function LockIcon(props) {
  return (
    <Icon {...props}>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
    </Icon>
  );
}

export function XIcon(props) {
  return (
    <Icon {...props}>
      <path d="M6 6l12 12M18 6 6 18" />
    </Icon>
  );
}

export function ChevronLeftIcon(props) {
  return (
    <Icon {...props}>
      <path d="m15 6-6 6 6 6" />
    </Icon>
  );
}

export function ExternalLinkIcon(props) {
  return (
    <Icon {...props}>
      <path d="M14 5h5v5" />
      <path d="M13 11 19 5" />
      <path d="M19 13.5V18A1.5 1.5 0 0 1 17.5 19.5h-11A1.5 1.5 0 0 1 5 18V7A1.5 1.5 0 0 1 6.5 5.5H11" />
    </Icon>
  );
}

export function AlertTriangleIcon(props) {
  return (
    <Icon {...props}>
      <path d="m12 4 9 16H3L12 4Z" />
      <path d="M12 10v4M12 17h.01" />
    </Icon>
  );
}

export function InfoIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 11v5M12 8h.01" />
    </Icon>
  );
}

export function CheckCircleIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="m8.5 12.5 2.5 2.5 4.5-5" />
    </Icon>
  );
}

export function BarChartIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4 19h16" />
      <path d="M7 16v-5M12 16V8M17 16v-8" />
    </Icon>
  );
}

export function DatabaseIcon(props) {
  return (
    <Icon {...props}>
      <ellipse cx="12" cy="6" rx="7.5" ry="2.5" />
      <path d="M4.5 6v6c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5V6" />
      <path d="M4.5 12v6c0 1.4 3.4 2.5 7.5 2.5s7.5-1.1 7.5-2.5v-6" />
    </Icon>
  );
}

export function UsersIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="9" cy="8" r="3" />
      <path d="M3.5 19a5.5 5.5 0 0 1 11 0" />
      <circle cx="17" cy="9" r="2.4" />
      <path d="M16 19a4.8 4.8 0 0 1 4.5-4.6" />
    </Icon>
  );
}

export function LinkIcon(props) {
  return (
    <Icon {...props}>
      <path d="M10 13a5 5 0 0 0 7.1 0l1.4-1.4a5 5 0 0 0-7.1-7.1L10 5.9" />
      <path d="M14 11a5 5 0 0 0-7.1 0L5.5 12.4a5 5 0 0 0 7.1 7.1L14 18.1" />
    </Icon>
  );
}

export function HashIcon(props) {
  return (
    <Icon {...props}>
      <path d="M5 9h14M5 15h14M9.5 4 8 20M16 4l-1.5 16" />
    </Icon>
  );
}

export function SlidersIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4 7h16M4 17h16" />
      <circle cx="9" cy="7" r="2.2" />
      <circle cx="15" cy="17" r="2.2" />
    </Icon>
  );
}

export function FileIcon(props) {
  return (
    <Icon {...props}>
      <path d="M14 3.5H8A2.5 2.5 0 0 0 5.5 6v12A2.5 2.5 0 0 0 8 20.5h8A2.5 2.5 0 0 0 18.5 18V8.5L14 3.5Z" />
      <path d="M14 3.5V8.5h4.5" />
    </Icon>
  );
}

export function InboxIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4.5 13.5 7 4.5h10l2.5 9v6A1.5 1.5 0 0 1 18 21H6a1.5 1.5 0 0 1-1.5-1.5v-6Z" />
      <path d="M4.5 13.5h4.2l1 2h4.6l1-2h4.2" />
    </Icon>
  );
}

export function PercentIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="7.5" cy="7.5" r="2.2" />
      <circle cx="16.5" cy="16.5" r="2.2" />
      <path d="M17 7 7 17" />
    </Icon>
  );
}

export function GripIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="9" cy="7" r="1.1" fill="currentColor" />
      <circle cx="15" cy="7" r="1.1" fill="currentColor" />
      <circle cx="9" cy="12" r="1.1" fill="currentColor" />
      <circle cx="15" cy="12" r="1.1" fill="currentColor" />
      <circle cx="9" cy="17" r="1.1" fill="currentColor" />
      <circle cx="15" cy="17" r="1.1" fill="currentColor" />
    </Icon>
  );
}

export function MoreVerticalIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="12" cy="6" r="1.15" fill="currentColor" />
      <circle cx="12" cy="12" r="1.15" fill="currentColor" />
      <circle cx="12" cy="18" r="1.15" fill="currentColor" />
    </Icon>
  );
}

export function CopyIcon(props) {
  return (
    <Icon {...props}>
      <rect x="8" y="8" width="11" height="11" rx="1.5" />
      <path d="M5 16V6.5A1.5 1.5 0 0 1 6.5 5H16" />
    </Icon>
  );
}

export function EyeIcon(props) {
  return (
    <Icon {...props}>
      <path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z" />
      <circle cx="12" cy="12" r="3" />
    </Icon>
  );
}

export function ChevronDownIcon(props) {
  return (
    <Icon {...props}>
      <path d="m6 9 6 6 6-6" />
    </Icon>
  );
}

export function ChevronUpIcon(props) {
  return (
    <Icon {...props}>
      <path d="m6 15 6-6 6 6" />
    </Icon>
  );
}

export function LayersIcon(props) {
  return (
    <Icon {...props}>
      <path d="M12 4 3 9l9 5 9-5-9-5Z" />
      <path d="m3 14 9 5 9-5" />
    </Icon>
  );
}

export function CoffeeIcon(props) {
  return (
    <Icon {...props}>
      <path d="M5 8h11v7.5A3.5 3.5 0 0 1 12.5 19h-4A3.5 3.5 0 0 1 5 15.5V8Z" />
      <path d="M16 10h1.8A2.2 2.2 0 0 1 20 12.2v.6A2.2 2.2 0 0 1 17.8 15H16" />
      <path d="M7 4.5c.4.8.4 1.6 0 2.4M10 4.5c.4.8.4 1.6 0 2.4" />
    </Icon>
  );
}

export function UtensilsIcon(props) {
  return (
    <Icon {...props}>
      <path d="M6 4v6a1.5 1.5 0 0 0 3 0V4" />
      <path d="M7.5 10v10" />
      <path d="M16 4v7.5c0 1.4-.6 2.5-2 2.5h0V20" />
      <path d="M14 4v5M18 4v5" />
    </Icon>
  );
}

export function ScissorsIcon(props) {
  return (
    <Icon {...props}>
      <circle cx="7" cy="7.5" r="2.2" />
      <circle cx="7" cy="16.5" r="2.2" />
      <path d="M9 8.8 19 18M9 15.2 19 6" />
    </Icon>
  );
}

export function SparklesIcon(props) {
  return (
    <Icon {...props}>
      <path d="M12 4.5 13.4 9 18 10.4 13.4 11.8 12 16.5 10.6 11.8 6 10.4 10.6 9 12 4.5Z" />
      <path d="M18 14.5v4M16 16.5h4" />
    </Icon>
  );
}

export function BedIcon(props) {
  return (
    <Icon {...props}>
      <path d="M4 18v-6.5A2.5 2.5 0 0 1 6.5 9H20v9" />
      <path d="M4 14h16" />
      <path d="M8 9V7.5A1.5 1.5 0 0 1 9.5 6h3A1.5 1.5 0 0 1 14 7.5V9" />
    </Icon>
  );
}
