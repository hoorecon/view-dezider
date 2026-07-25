// Safe expression evaluator — mirror of backend/core/formula_engine.py.
//
// Used by the Formula editor modal for live preview and by the Expected
// Values step to auto-fill computed cells. Only supports the same
// whitelist of tokens the backend accepts, so evaluation results always
// match between client and server.

export class FormulaError extends Error {
  constructor(msg: string) {
    super(msg);
    this.name = 'FormulaError';
  }
}

const ALLOWED_FUNCS: Record<string, (...a: number[]) => number> = {
  abs: (x) => Math.abs(x),
  min: (...a) => Math.min(...a),
  max: (...a) => Math.max(...a),
  pow: (b, e) => Math.pow(b, e),
  sqrt: (x) => Math.sqrt(x),
  log: (x) => Math.log(x),
  exp: (x) => Math.exp(x),
  round: (x, digits = 0) => {
    const p = Math.pow(10, digits);
    return Math.round(x * p) / p;
  },
};

// Tokenizer for numbers, identifiers, operators.
type Tok = { type: string; value: string };

function tokenize(src: string): Tok[] {
  const tokens: Tok[] = [];
  let i = 0;
  while (i < src.length) {
    const c = src[i];
    if (/\s/.test(c)) { i += 1; continue; }
    if (/[0-9.]/.test(c)) {
      let j = i;
      while (j < src.length && /[0-9.]/.test(src[j])) j += 1;
      tokens.push({ type: 'num', value: src.slice(i, j) });
      i = j;
      continue;
    }
    if (/[a-zA-Z_]/.test(c)) {
      let j = i;
      while (j < src.length && /[a-zA-Z0-9_]/.test(src[j])) j += 1;
      tokens.push({ type: 'ident', value: src.slice(i, j) });
      i = j;
      continue;
    }
    // Check `**` (exponent) BEFORE the single `*` to avoid it being tokenized
    // as two consecutive `*`. Also accept `^` as a friendlier alias.
    if (c === '*' && src[i + 1] === '*') {
      tokens.push({ type: 'op', value: '**' });
      i += 2;
      continue;
    }
    if (c === '^') {
      tokens.push({ type: 'op', value: '**' });
      i += 1;
      continue;
    }
    if ('+-*/%(),'.includes(c)) {
      tokens.push({ type: 'op', value: c });
      i += 1;
      continue;
    }
    throw new FormulaError(`Unexpected character: ${c}`);
  }
  return tokens;
}

// Recursive-descent parser (expr → term → factor → unary → primary).
// Precedence: (), unary +/-, * / %, + -.
function parse(tokens: Tok[]): (syms: Record<string, any>) => number {
  let pos = 0;
  const peek = () => tokens[pos];
  const eat = () => tokens[pos++];

  function parseExpression(): (s: Record<string, any>) => number {
    let left = parseTerm();
    while (peek() && peek().type === 'op' && (peek().value === '+' || peek().value === '-')) {
      const op = eat().value;
      const right = parseTerm();
      const L = left; const R = right;
      left = (s) => (op === '+' ? L(s) + R(s) : L(s) - R(s));
    }
    return left;
  }
  function parseTerm(): (s: Record<string, any>) => number {
    let left = parsePower();
    while (peek() && peek().type === 'op' && '*/%'.includes(peek().value)) {
      const op = eat().value;
      const right = parsePower();
      const L = left; const R = right;
      left = (s) => {
        const l = L(s); const r = R(s);
        if (op === '*') return l * r;
        if (op === '/') { if (r === 0) throw new FormulaError('Division by zero'); return l / r; }
        return l % r;
      };
    }
    return left;
  }
  // Exponentiation — RIGHT-associative: 2**3**2 = 2**(3**2) = 512.
  // Sits between multiplicative and unary in precedence (Python-style).
  function parsePower(): (s: Record<string, any>) => number {
    const base = parseUnary();
    if (peek() && peek().type === 'op' && peek().value === '**') {
      eat();
      const exp = parsePower(); // right-assoc via recursion
      return (s) => Math.pow(base(s), exp(s));
    }
    return base;
  }
  function parseUnary(): (s: Record<string, any>) => number {
    if (peek() && peek().type === 'op' && (peek().value === '+' || peek().value === '-')) {
      const op = eat().value;
      const inner = parseUnary();
      return (s) => (op === '-' ? -inner(s) : inner(s));
    }
    return parsePrimary();
  }
  function parsePrimary(): (s: Record<string, any>) => number {
    const t = eat();
    if (!t) throw new FormulaError('Unexpected end of expression');
    if (t.type === 'num') {
      const n = parseFloat(t.value);
      if (!isFinite(n)) throw new FormulaError(`Invalid number: ${t.value}`);
      return () => n;
    }
    if (t.type === 'op' && t.value === '(') {
      const inner = parseExpression();
      const close = eat();
      if (!close || close.value !== ')') throw new FormulaError('Missing )');
      return inner;
    }
    if (t.type === 'ident') {
      // function call?
      if (peek() && peek().type === 'op' && peek().value === '(') {
        eat();
        const args: ((s: Record<string, any>) => number)[] = [];
        if (peek() && peek().value !== ')') {
          args.push(parseExpression());
          while (peek() && peek().value === ',') { eat(); args.push(parseExpression()); }
        }
        const close = eat();
        if (!close || close.value !== ')') throw new FormulaError('Missing )');
        const fn = ALLOWED_FUNCS[t.value];
        if (!fn) throw new FormulaError(`Unknown function: ${t.value}`);
        return (s) => fn(...args.map((a) => a(s)));
      }
      // variable reference
      return (s) => {
        if (!(t.value in s)) throw new FormulaError(`Unknown variable: ${t.value}`);
        const v = s[t.value];
        if (v === null || v === undefined || v === '') {
          throw new FormulaError(`Value for ${t.value} is not set`);
        }
        const n = typeof v === 'number' ? v : parseFloat(String(v));
        if (!isFinite(n)) throw new FormulaError(`Value for ${t.value} is not numeric: ${v}`);
        return n;
      };
    }
    throw new FormulaError(`Unexpected token: ${t.value}`);
  }

  const fn = parseExpression();
  if (pos < tokens.length) throw new FormulaError(`Trailing input: ${tokens[pos].value}`);
  return fn;
}

export function evaluate(expression: string, symbols: Record<string, any>): number {
  const src = (expression || '').trim();
  if (!src) throw new FormulaError('Expression is empty');
  const tokens = tokenize(src);
  const evaluator = parse(tokens);
  return evaluator(symbols);
}

export function usedVariables(expression: string): string[] {
  try {
    const tokens = tokenize(expression || '');
    const names = new Set<string>();
    tokens.forEach((t, i) => {
      if (t.type === 'ident' && !(t.value in ALLOWED_FUNCS)) {
        const next = tokens[i + 1];
        // Skip function calls (ident followed by `(`)
        if (!(next && next.type === 'op' && next.value === '(')) {
          names.add(t.value);
        }
      }
    });
    return Array.from(names).sort();
  } catch {
    return [];
  }
}

// Topologically evaluate a list of formulas against a base symbols map.
// Returns the enriched symbols map + per-target error messages.
export function applyFormulas(
  formulas: { target: string; expression: string }[],
  baseSymbols: Record<string, any>,
): { symbols: Record<string, any>; errors: Record<string, string> } {
  const targets = new Set(formulas.map((f) => f.target));
  const errors: Record<string, string> = {};
  const symbols = { ...baseSymbols };
  let remaining = [...formulas];
  const done = new Set<string>();
  // Simple iterative passes; O(n^2) is fine for < 100 formulas.
  while (remaining.length) {
    let progressed = false;
    const nextRound: typeof remaining = [];
    for (const f of remaining) {
      const deps = usedVariables(f.expression).filter((v) => targets.has(v));
      if (deps.every((d) => done.has(d))) {
        try {
          symbols[f.target] = evaluate(f.expression, symbols);
        } catch (e: any) {
          errors[f.target] = e.message || String(e);
        }
        done.add(f.target);
        progressed = true;
      } else {
        nextRound.push(f);
      }
    }
    if (!progressed) {
      nextRound.forEach((f) => { errors[f.target] = 'Circular / unresolved formula'; });
      break;
    }
    remaining = nextRound;
  }
  return { symbols, errors };
}
