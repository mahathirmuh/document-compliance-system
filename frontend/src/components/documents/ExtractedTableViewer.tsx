import type { ExtractedTable } from '../../types/extractedContent';

export function ExtractedTableViewer({
  tables,
}: {
  tables: readonly ExtractedTable[];
}) {
  if (tables.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-slate-300 p-5 text-center text-xs text-slate-500">
        No structured tables were detected in this container.
      </p>
    );
  }
  return (
    <div className="space-y-5">
      {tables.map((table) => {
        const cellsByRow = new Map<number, typeof table.cells>();
        table.cells.forEach((cell) => {
          cellsByRow.set(cell.rowIndex, [
            ...(cellsByRow.get(cell.rowIndex) ?? []),
            cell,
          ]);
        });
        const rows = [...cellsByRow.entries()]
          .sort(([left], [right]) => left - right)
          .map(
            ([rowIndex, cells]) =>
              [
                rowIndex,
                [...cells].sort((left, right) => left.columnIndex - right.columnIndex),
              ] as const,
          );
        const metadataTotalCells = table.metadata?.totalCells;
        const totalCells =
          typeof metadataTotalCells === 'number' &&
          Number.isFinite(metadataTotalCells) &&
          metadataTotalCells >= 0
            ? Math.floor(metadataTotalCells)
            : table.cells.length;
        const cellsTruncated = table.metadata?.cellsTruncated === true;
        return (
          <section
            key={table.id}
            className="overflow-hidden rounded-2xl border border-slate-200 bg-white"
          >
            <div className="border-b border-slate-200 bg-slate-50 px-4 py-3">
              <p className="text-xs font-semibold text-slate-900">
                Table {table.tableIndex}
              </p>
              <p className="mt-1 font-mono text-[10px] text-slate-500">
                {table.sourceReference} / {table.rowCount.toLocaleString()} rows /{' '}
                {table.columnCount.toLocaleString()} columns
              </p>
            </div>
            {cellsTruncated && (
              <p
                role="status"
                className="border-b border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-800"
              >
                Showing {table.cells.length.toLocaleString()} of{' '}
                {totalCells.toLocaleString()} table cells. The inline preview is capped;
                export the extraction result for the complete table.
              </p>
            )}
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse">
                <tbody>
                  {rows.map(([rowIndex, cells]) => (
                    <tr key={rowIndex} className="border-b border-slate-100">
                      {cells.map((cell) => (
                        <td
                          key={cell.id}
                          rowSpan={Math.max(1, cell.rowSpan)}
                          colSpan={Math.max(1, cell.columnSpan)}
                          className="min-w-32 border-r border-slate-100 px-3 py-2 align-top text-xs text-slate-700"
                        >
                          {cell.coordinate && (
                            <span className="mb-1 block font-mono text-[9px] text-slate-400">
                              {cell.coordinate}
                            </span>
                          )}
                          <span className="whitespace-pre-wrap">{cell.text}</span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </div>
  );
}
