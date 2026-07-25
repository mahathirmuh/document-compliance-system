import { ExternalLink } from 'lucide-react';

interface SharePointLinkProps {
  url?: string | null;
  compact?: boolean;
}

export function SharePointLink({ compact = false, url }: SharePointLinkProps) {
  if (!url) {
    return <span className="text-xs text-slate-400">Not linked</span>;
  }

  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1.5 rounded-lg text-xs font-semibold text-blue-700 hover:text-blue-900 focus-visible:outline focus-visible:outline-2 focus-visible:outline-blue-600"
      title={url}
    >
      <ExternalLink className="size-3.5" aria-hidden="true" />
      {compact ? 'Open' : 'Open SharePoint'}
    </a>
  );
}
