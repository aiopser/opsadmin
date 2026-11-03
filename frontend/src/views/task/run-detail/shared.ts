type AnsiColor = 'black' | 'red' | 'green' | 'yellow' | 'blue' | 'magenta' | 'cyan' | 'white';

export interface AnsiSegment {
  text: string;
  color: AnsiColor | null;
  bold: boolean;
}

const ansiColors: readonly AnsiColor[] = ['black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'];

function applySgr(codes: number[], current: Pick<AnsiSegment, 'color' | 'bold'>): Pick<AnsiSegment, 'color' | 'bold'> {
  return codes.reduce((style, code) => {
    if (code === 0) return { color: null, bold: false };
    if (code === 1) return { ...style, bold: true };
    if (code === 22) return { ...style, bold: false };
    if (code === 39) return { ...style, color: null };
    if ((code >= 30 && code <= 37) || (code >= 90 && code <= 97)) {
      return { ...style, color: ansiColors[code >= 90 ? code - 90 : code - 30] ?? null };
    }
    return style;
  }, current);
}

export function parseAnsiOutput(output: string): AnsiSegment[] {
  // ANSI SGR 使用 ESC 控制字符，限定只解析颜色和字重序列。
  // eslint-disable-next-line no-control-regex
  const escapeSequence = /\x1B\[([\d;]*)m/g;
  const segments: AnsiSegment[] = [];
  let style: Pick<AnsiSegment, 'color' | 'bold'> = { color: null, bold: false };
  let offset = 0;

  for (const match of output.matchAll(escapeSequence)) {
    const index = match.index ?? 0;
    if (index > offset) segments.push({ text: output.slice(offset, index), ...style });
    style = applySgr((match[1] || '0').split(';').map(Number), style);
    offset = index + match[0].length;
  }

  if (offset < output.length) segments.push({ text: output.slice(offset), ...style });
  return segments;
}
