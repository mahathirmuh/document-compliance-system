export const isXlsxFile = (file: File): boolean =>
  file.name.toLowerCase().endsWith('.xlsx');
