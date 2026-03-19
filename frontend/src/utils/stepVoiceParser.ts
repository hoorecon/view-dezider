/**
 * Universal Voice Command Parser for all PRR Decision Steps
 * 
 * Supports different command patterns per step:
 * 
 * Step 1 (Context): "Title [text]", "Context [text]"
 * Step 2 (Factors): "Add [factor name]", "Remove [factor name]"
 * Step 3 (Classify): "[factor] Primary/Secondary"
 * Step 4 (Prioritize): "Move [factor] up/down", "[factor] first/last"
 * Step 6 (Options): "Add [option name]", "Remove [option name]"
 * Step 7 (Assess): "[factor] High/Medium/Low", "[factor] [number] percent", "All High"
 * Step 8 (Results): "Choose [option]", "Select [option]", "Best case/Worst case"
 * Step 9 (Reflection): Dictation mode - raw text
 * Step 10 (Notes): Dictation mode - raw text
 */

export type StepCommandType =
  | 'set_title'
  | 'set_context'
  | 'add_factor'
  | 'remove_factor'
  | 'classify_factor'
  | 'move_factor'
  | 'add_option'
  | 'remove_option'
  | 'assess_factor'
  | 'assess_all'
  | 'choose_option'
  | 'set_case'
  | 'dictation'
  | 'unknown';

export interface StepVoiceCommand {
  type: StepCommandType;
  step: number;
  // Factor/Option identification
  factorId?: string;
  factorName?: string;
  optionId?: string;
  optionName?: string;
  // Values
  value?: number;
  mode?: 'L' | 'M' | 'H' | 'custom';
  text?: string;
  category?: 'primary' | 'secondary';
  direction?: 'up' | 'down' | 'first' | 'last';
  caseType?: 'best' | 'worst' | 'most_likely';
  allFactors?: boolean;
  // Meta
  confidence: number;
  raw: string;
}

interface Factor {
  id: string;
  name: string;
  rating: number;
  category?: string;
}

interface Option {
  id: string;
  name: string;
}

// Value keywords for assessment
const VALUE_KEYWORDS: Record<string, { value: number; mode: 'L' | 'M' | 'H' }> = {
  'low': { value: 25, mode: 'L' },
  'lo': { value: 25, mode: 'L' },
  'medium': { value: 50, mode: 'M' },
  'med': { value: 50, mode: 'M' },
  'mid': { value: 50, mode: 'M' },
  'middle': { value: 50, mode: 'M' },
  'high': { value: 75, mode: 'H' },
  'hi': { value: 75, mode: 'H' },
};

// Noise words to filter
const NOISE_WORDS = new Set([
  'set', 'make', 'change', 'update', 'put', 'is', 'to', 'at', 'the',
  'for', 'as', 'a', 'an', 'please', 'can', 'you', 'percent', 'percentage',
  '%', 'it', 'this', 'that', 'factor', 'assessment', 'value', 'rate', 'rating',
]);

// String similarity (Dice coefficient)
function similarity(s1: string, s2: string): number {
  if (s1 === s2) return 1;
  if (s1.length < 2 || s2.length < 2) return 0;
  const bigrams1 = new Map<string, number>();
  for (let i = 0; i < s1.length - 1; i++) {
    const bigram = s1.substring(i, i + 2);
    bigrams1.set(bigram, (bigrams1.get(bigram) || 0) + 1);
  }
  let intersectionSize = 0;
  for (let i = 0; i < s2.length - 1; i++) {
    const bigram = s2.substring(i, i + 2);
    const count = bigrams1.get(bigram) || 0;
    if (count > 0) {
      bigrams1.set(bigram, count - 1);
      intersectionSize++;
    }
  }
  return (2 * intersectionSize) / (s1.length + s2.length - 2);
}

// Find best matching item from a list
function findBestMatch(transcript: string, items: { id: string; name: string }[]): { item: { id: string; name: string }; confidence: number } | null {
  let best: { item: { id: string; name: string }; confidence: number } | null = null;
  const lower = transcript.toLowerCase();

  for (const item of items) {
    const itemName = item.name.toLowerCase().trim();
    // Exact substring match
    if (lower.includes(itemName)) {
      const conf = 1.0;
      if (!best || conf > best.confidence || itemName.length > best.item.name.length) {
        best = { item, confidence: conf };
      }
      continue;
    }
    // Fuzzy match
    const sim = similarity(lower, itemName);
    if (sim > 0.5 && (!best || sim > best.confidence)) {
      best = { item, confidence: sim };
    }
    // Word-level match
    const itemWords = itemName.split(/\s+/);
    const transcriptWords = lower.split(/\s+/);
    let matched = 0;
    for (const iw of itemWords) {
      for (const tw of transcriptWords) {
        if (tw === iw || similarity(tw, iw) > 0.7) {
          matched++;
          break;
        }
      }
    }
    const wordConf = itemWords.length > 0 ? matched / itemWords.length : 0;
    if (wordConf >= 0.5 && matched >= 1 && (!best || wordConf > best.confidence)) {
      best = { item, confidence: wordConf };
    }
  }
  return best;
}

// Extract number from words
function extractNumber(words: string[]): number | null {
  for (const word of words) {
    const cleaned = word.replace(/[^0-9]/g, '');
    if (cleaned) {
      const num = parseInt(cleaned, 10);
      if (!isNaN(num) && num >= 0 && num <= 100) return num;
    }
  }
  const numberWords: Record<string, number> = {
    'zero': 0, 'five': 5, 'ten': 10, 'fifteen': 15, 'twenty': 20,
    'twenty-five': 25, 'twenty five': 25, 'thirty': 30, 'thirty-five': 35,
    'forty': 40, 'forty-five': 45, 'fifty': 50, 'fifty-five': 55,
    'sixty': 60, 'sixty-five': 65, 'seventy': 70, 'seventy-five': 75,
    'eighty': 80, 'eighty-five': 85, 'ninety': 90, 'ninety-five': 95,
    'hundred': 100, 'one hundred': 100,
  };
  const text = words.join(' ');
  const sorted = Object.entries(numberWords).sort((a, b) => b[0].length - a[0].length);
  for (const [word, num] of sorted) {
    if (text.includes(word)) return num;
  }
  return null;
}

// Extract L/M/H or custom value
function extractValue(words: string[]): { value: number; mode: 'L' | 'M' | 'H' | 'custom' } | null {
  for (const word of words) {
    const clean = word.replace(/[^a-z]/g, '');
    if (VALUE_KEYWORDS[clean]) return VALUE_KEYWORDS[clean];
  }
  const num = extractNumber(words);
  if (num !== null) return { value: Math.min(100, Math.max(0, num)), mode: 'custom' };
  return null;
}

/**
 * Parse Step 1: Context & Title
 */
function parseStep1(transcript: string): StepVoiceCommand | null {
  const lower = transcript.toLowerCase().trim();
  const raw = transcript;

  // "title [text]" or "decision title [text]"
  const titleMatch = lower.match(/(?:title|name|called|decision)\s*[:.]?\s*(.+)/);
  if (titleMatch) {
    return { type: 'set_title', step: 1, text: titleMatch[1].trim(), confidence: 0.9, raw };
  }

  // "context [text]" or "description [text]" or "about [text]"
  const contextMatch = lower.match(/(?:context|description|about|describe)\s*[:.]?\s*(.+)/);
  if (contextMatch) {
    return { type: 'set_context', step: 1, text: contextMatch[1].trim(), confidence: 0.9, raw };
  }

  // Default: treat as dictation for context
  if (transcript.trim().length > 5) {
    return { type: 'dictation', step: 1, text: transcript.trim(), confidence: 0.6, raw };
  }
  return null;
}

/**
 * Parse Step 2: List Factors
 */
function parseStep2(transcript: string, factors: Factor[]): StepVoiceCommand | null {
  const lower = transcript.toLowerCase().trim();
  const raw = transcript;

  // "add [factor name]" or "new factor [name]"
  const addMatch = lower.match(/(?:add|new|include|create)\s+(?:factor\s+)?(.+)/);
  if (addMatch) {
    const name = addMatch[1].replace(/\bfactor\b/gi, '').trim();
    if (name.length > 1) {
      // Capitalize first letter of each word
      const formatted = name.replace(/\b\w/g, c => c.toUpperCase());
      return { type: 'add_factor', step: 2, text: formatted, confidence: 0.9, raw };
    }
  }

  // "remove [factor]" or "delete [factor]"
  const removeMatch = lower.match(/(?:remove|delete|drop)\s+(?:factor\s+)?(.+)/);
  if (removeMatch) {
    const match = findBestMatch(removeMatch[1], factors);
    if (match) {
      return { type: 'remove_factor', step: 2, factorId: match.item.id, factorName: match.item.name, confidence: match.confidence, raw };
    }
  }

  // Default: treat as adding a factor
  if (lower.length > 2 && !lower.match(/^(yes|no|ok|done|next|stop|cancel)/)) {
    const formatted = transcript.trim().replace(/\b\w/g, c => c.toUpperCase());
    return { type: 'add_factor', step: 2, text: formatted, confidence: 0.6, raw };
  }
  return null;
}

/**
 * Parse Step 3: Classify Factors
 */
function parseStep3(transcript: string, factors: Factor[]): StepVoiceCommand | null {
  const lower = transcript.toLowerCase().trim();
  const raw = transcript;

  // Check for "all primary" or "all secondary"
  if (/\b(all|every|everything)\b.*\bprimary\b/.test(lower)) {
    return { type: 'classify_factor', step: 3, allFactors: true, category: 'primary', confidence: 0.9, raw };
  }
  if (/\b(all|every|everything)\b.*\bsecondary\b/.test(lower)) {
    return { type: 'classify_factor', step: 3, allFactors: true, category: 'secondary', confidence: 0.9, raw };
  }

  // Check for "[factor] primary/secondary"
  const isPrimary = /\bprimary\b/.test(lower);
  const isSecondary = /\bsecondary\b/.test(lower);

  if (isPrimary || isSecondary) {
    const cleaned = lower.replace(/\b(primary|secondary|set|make|mark|as|is)\b/g, '').trim();
    const match = findBestMatch(cleaned, factors);
    if (match) {
      return {
        type: 'classify_factor', step: 3,
        factorId: match.item.id, factorName: match.item.name,
        category: isPrimary ? 'primary' : 'secondary',
        confidence: match.confidence, raw
      };
    }
  }
  return null;
}

/**
 * Parse Step 4: Prioritize Factors
 */
function parseStep4(transcript: string, factors: Factor[]): StepVoiceCommand | null {
  const lower = transcript.toLowerCase().trim();
  const raw = transcript;

  // "move [factor] up/down" or "[factor] up/down"
  const moveUp = /\b(up|higher|above|raise)\b/.test(lower);
  const moveDown = /\b(down|lower|below|drop)\b/.test(lower);
  const moveFirst = /\b(first|top|highest)\b/.test(lower);
  const moveLast = /\b(last|bottom|lowest)\b/.test(lower);

  if (moveUp || moveDown || moveFirst || moveLast) {
    const cleaned = lower.replace(/\b(move|put|set|up|down|higher|lower|above|below|raise|drop|first|top|highest|last|bottom|lowest|to|the)\b/g, '').trim();
    const match = findBestMatch(cleaned, factors);
    if (match) {
      const direction = moveFirst ? 'first' : moveLast ? 'last' : moveUp ? 'up' : 'down';
      return {
        type: 'move_factor', step: 4,
        factorId: match.item.id, factorName: match.item.name,
        direction, confidence: match.confidence, raw
      };
    }
  }
  return null;
}

/**
 * Parse Step 6: Define Options
 */
function parseStep6(transcript: string, options: Option[]): StepVoiceCommand | null {
  const lower = transcript.toLowerCase().trim();
  const raw = transcript;

  // "add [option]" or "new option [name]"
  const addMatch = lower.match(/(?:add|new|include|create)\s+(?:option\s+)?(.+)/);
  if (addMatch) {
    const name = addMatch[1].replace(/\boption\b/gi, '').trim();
    if (name.length > 1) {
      const formatted = name.replace(/\b\w/g, c => c.toUpperCase());
      return { type: 'add_option', step: 6, text: formatted, confidence: 0.9, raw };
    }
  }

  // "remove [option]"
  const removeMatch = lower.match(/(?:remove|delete|drop)\s+(?:option\s+)?(.+)/);
  if (removeMatch && options.length > 0) {
    const match = findBestMatch(removeMatch[1], options);
    if (match) {
      return { type: 'remove_option', step: 6, optionId: match.item.id, optionName: match.item.name, confidence: match.confidence, raw };
    }
  }

  // Default: add as option
  if (lower.length > 2 && !lower.match(/^(yes|no|ok|done|next|stop|cancel)/)) {
    const formatted = transcript.trim().replace(/\b\w/g, c => c.toUpperCase());
    return { type: 'add_option', step: 6, text: formatted, confidence: 0.6, raw };
  }
  return null;
}

/**
 * Parse Step 7: Assess & Calculate
 */
function parseStep7(transcript: string, factors: Factor[]): StepVoiceCommand | null {
  const lower = transcript.toLowerCase().trim();
  const raw = transcript;
  const words = lower.split(/\s+/);

  // "all high/medium/low"
  if (/\b(all|everything|every factor)\b/.test(lower)) {
    const val = extractValue(words);
    if (val) {
      return { type: 'assess_all', step: 7, allFactors: true, value: val.value, mode: val.mode, confidence: 0.9, raw };
    }
  }

  // Find factor + value
  const factorMatch = findBestMatch(lower, factors);
  const val = extractValue(words);

  if (factorMatch && val) {
    return {
      type: 'assess_factor', step: 7,
      factorId: factorMatch.item.id, factorName: factorMatch.item.name,
      value: val.value, mode: val.mode,
      confidence: factorMatch.confidence, raw
    };
  }

  if (factorMatch) {
    return {
      type: 'assess_factor', step: 7,
      factorId: factorMatch.item.id, factorName: factorMatch.item.name,
      value: 0, mode: 'L', confidence: factorMatch.confidence * 0.5, raw
    };
  }
  return null;
}

/**
 * Parse Step 8: Results / Choose Option
 */
function parseStep8(transcript: string, options: Option[]): StepVoiceCommand | null {
  const lower = transcript.toLowerCase().trim();
  const raw = transcript;

  // Case type
  if (/\b(best\s*case|best\s*scenario|optimistic)\b/.test(lower)) {
    const match = findBestMatch(lower.replace(/\b(best|case|scenario|choose|select|pick|optimistic)\b/g, '').trim(), options);
    if (match) {
      return { type: 'choose_option', step: 8, optionId: match.item.id, optionName: match.item.name, caseType: 'best', confidence: match.confidence, raw };
    }
    return { type: 'set_case', step: 8, caseType: 'best', confidence: 0.8, raw };
  }
  if (/\b(worst\s*case|worst\s*scenario|pessimistic)\b/.test(lower)) {
    const match = findBestMatch(lower.replace(/\b(worst|case|scenario|choose|select|pick|pessimistic)\b/g, '').trim(), options);
    if (match) {
      return { type: 'choose_option', step: 8, optionId: match.item.id, optionName: match.item.name, caseType: 'worst', confidence: match.confidence, raw };
    }
    return { type: 'set_case', step: 8, caseType: 'worst', confidence: 0.8, raw };
  }
  if (/\b(most\s*likely|realistic|probable)\b/.test(lower)) {
    return { type: 'set_case', step: 8, caseType: 'most_likely', confidence: 0.8, raw };
  }

  // "choose/select/pick [option]"
  const chooseMatch = lower.match(/(?:choose|select|pick|go with)\s+(.+)/);
  if (chooseMatch && options.length > 0) {
    const match = findBestMatch(chooseMatch[1], options);
    if (match) {
      return { type: 'choose_option', step: 8, optionId: match.item.id, optionName: match.item.name, caseType: 'best', confidence: match.confidence, raw };
    }
  }

  // Just an option name
  if (options.length > 0) {
    const match = findBestMatch(lower, options);
    if (match && match.confidence > 0.7) {
      return { type: 'choose_option', step: 8, optionId: match.item.id, optionName: match.item.name, caseType: 'best', confidence: match.confidence, raw };
    }
  }
  return null;
}

/**
 * Parse Steps 9-10: Dictation (Reflection / Final Notes)
 */
function parseDictation(transcript: string, step: number): StepVoiceCommand | null {
  if (transcript.trim().length > 2) {
    return { type: 'dictation', step, text: transcript.trim(), confidence: 0.9, raw: transcript };
  }
  return null;
}

/**
 * Main parser - routes to step-specific parser
 */
export function parseStepVoiceCommand(
  step: number,
  transcript: string,
  factors: Factor[],
  options: Option[]
): StepVoiceCommand | null {
  if (!transcript || transcript.trim().length === 0) return null;

  switch (step) {
    case 1: return parseStep1(transcript);
    case 2: return parseStep2(transcript, factors);
    case 3: return parseStep3(transcript, factors);
    case 4: return parseStep4(transcript, factors);
    case 5: return null; // Auto-calculation step
    case 6: return parseStep6(transcript, options);
    case 7: return parseStep7(transcript, factors);
    case 8: return parseStep8(transcript, options);
    case 9: return parseDictation(transcript, 9);
    case 10: return parseDictation(transcript, 10);
    default: return null;
  }
}

/**
 * Get voice hints per step
 */
export function getStepVoiceHints(step: number): { examples: string[]; description: string } {
  switch (step) {
    case 1: return {
      description: 'Set title or describe context',
      examples: ['"Title Choose best job offer"', '"Context Comparing two career paths"'],
    };
    case 2: return {
      description: 'Add or remove factors',
      examples: ['"Add Salary"', '"Add Work-Life Balance"', '"Remove Location"'],
    };
    case 3: return {
      description: 'Classify factors as Primary or Secondary',
      examples: ['"Salary Primary"', '"Location Secondary"', '"All Primary"'],
    };
    case 4: return {
      description: 'Reorder factor priority',
      examples: ['"Move Salary up"', '"Career Growth first"', '"Location down"'],
    };
    case 6: return {
      description: 'Add or remove options',
      examples: ['"Add Company A"', '"Add Startup Inc"', '"Remove Option B"'],
    };
    case 7: return {
      description: 'Rate factors for each option',
      examples: ['"Salary High"', '"Career Growth 80 percent"', '"All Medium"'],
    };
    case 8: return {
      description: 'Choose your decision',
      examples: ['"Choose Company A"', '"Select best case"', '"Go with Startup"'],
    };
    case 9: return {
      description: 'Dictate your reflection',
      examples: ['"I feel confident about this choice because..."'],
    };
    case 10: return {
      description: 'Dictate final notes',
      examples: ['"Key takeaway: always prioritize growth..."'],
    };
    default: return { description: '', examples: [] };
  }
}

/**
 * Describe a command in human-readable format
 */
export function describeStepCommand(cmd: StepVoiceCommand): string {
  switch (cmd.type) {
    case 'set_title': return `Title → "${cmd.text}"`;
    case 'set_context': return `Context → "${cmd.text?.substring(0, 40)}..."`;
    case 'add_factor': return `+ Factor: ${cmd.text}`;
    case 'remove_factor': return `- Factor: ${cmd.factorName}`;
    case 'classify_factor':
      if (cmd.allFactors) return `All → ${cmd.category}`;
      return `${cmd.factorName} → ${cmd.category}`;
    case 'move_factor': return `${cmd.factorName} → ${cmd.direction}`;
    case 'add_option': return `+ Option: ${cmd.text}`;
    case 'remove_option': return `- Option: ${cmd.optionName}`;
    case 'assess_factor': {
      const val = cmd.mode === 'custom' ? `${cmd.value}%` : cmd.mode === 'H' ? 'High' : cmd.mode === 'M' ? 'Medium' : 'Low';
      return `${cmd.factorName} → ${val}`;
    }
    case 'assess_all': {
      const val = cmd.mode === 'custom' ? `${cmd.value}%` : cmd.mode === 'H' ? 'High' : cmd.mode === 'M' ? 'Medium' : 'Low';
      return `All factors → ${val}`;
    }
    case 'choose_option': return `Choose: ${cmd.optionName} (${cmd.caseType})`;
    case 'set_case': return `Case: ${cmd.caseType}`;
    case 'dictation': return `"${cmd.text?.substring(0, 50)}${(cmd.text?.length || 0) > 50 ? '...' : ''}"`;
    default: return cmd.raw;
  }
}

// Re-export old interface for backward compatibility
export type { StepVoiceCommand as ParsedVoiceCommand };
