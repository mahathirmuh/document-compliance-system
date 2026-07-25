import { Fragment } from 'react';

export function SafeHighlight({ query, text }: { text: string; query: string }) {
  const trimmedQuery = query.trim();
  if (!trimmedQuery) {
    return text;
  }

  const lowerText = text.toLocaleLowerCase();
  const lowerQuery = trimmedQuery.toLocaleLowerCase();
  const parts: Array<{ text: string; highlighted: boolean }> = [];
  let cursor = 0;
  let matchIndex = lowerText.indexOf(lowerQuery);

  while (matchIndex >= 0) {
    if (matchIndex > cursor) {
      parts.push({ text: text.slice(cursor, matchIndex), highlighted: false });
    }
    const end = matchIndex + trimmedQuery.length;
    parts.push({ text: text.slice(matchIndex, end), highlighted: true });
    cursor = end;
    matchIndex = lowerText.indexOf(lowerQuery, cursor);
  }
  if (cursor < text.length) {
    parts.push({ text: text.slice(cursor), highlighted: false });
  }

  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={`${index}-${part.text}`}>
          {part.highlighted ? (
            <mark className="rounded bg-amber-200 px-0.5 text-inherit">
              {part.text}
            </mark>
          ) : (
            part.text
          )}
        </Fragment>
      ))}
    </>
  );
}
