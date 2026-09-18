import {
  Home,
  Grid,
  Search,
  Upload,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  X,
  MoreHorizontal,
  Download,
  Edit,
  Trash2,
  Image,
  FileText,
  Send,
  ArrowRight,
  Loader2,
  Check,
  XCircle,
  AlertCircle,
  Info,
} from 'lucide-react';

export interface IconProps {
  name: 'home' | 'grid' | 'search' | 'upload' | 'settings' | 'chevronLeft' | 'chevronRight' | 'chevronDown' | 'x' | 'moreHorizontal' | 'download' | 'edit' | 'trash' | 'image' | 'file' | 'send' | 'arrowRight' | 'loader' | 'check' | 'xCircle' | 'alertCircle' | 'info';
  size?: number;
  className?: string;
}

const iconMap = {
  home: Home,
  grid: Grid,
  search: Search,
  upload: Upload,
  settings: Settings,
  chevronLeft: ChevronLeft,
  chevronRight: ChevronRight,
  chevronDown: ChevronDown,
  x: X,
  moreHorizontal: MoreHorizontal,
  download: Download,
  edit: Edit,
  trash: Trash2,
  image: Image,
  file: FileText,
  send: Send,
  arrowRight: ArrowRight,
  loader: Loader2,
  check: Check,
  xCircle: XCircle,
  alertCircle: AlertCircle,
  info: Info,
};

export function Icon({ name, size = 15, className }: { name: keyof typeof iconMap; size?: number; className?: string }) {
  const IconComponent = iconMap[name];
  if (!IconComponent) {
    console.warn(`Icon "${name}" not found`);
    return null;
  }
  return <IconComponent size={size} className={className} />;
}

export const icons = {
  home: 'home',
  grid: 'grid',
  search: 'search',
  upload: 'upload',
  settings: 'settings',
  chevronLeft: 'chevronLeft',
  chevronRight: 'chevronRight',
  chevronDown: 'chevronDown',
  x: 'x',
  moreHorizontal: 'moreHorizontal',
  download: 'download',
  edit: 'edit',
  trash: 'trash',
  image: 'image',
  file: 'file',
  send: 'send',
  arrowRight: 'arrowRight',
  loader: 'loader',
  check: 'check',
  xCircle: 'xCircle',
  alertCircle: 'alertCircle',
  info: 'info',
} as const;