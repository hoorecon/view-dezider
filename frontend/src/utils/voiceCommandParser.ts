/**
 * Voice Command Parser for PRR Assessment Step
 * 
 * Parses spoken text like:
 * - "Decision Power High" → { factorName: "Decision Power", value: 75, mode: "H" }
 * - "Upfront Investment 60 percent" → { factorName: "Upfront Investment", value: 60, mode: "custom" }
 * - "Timeline Low" → { factorName: "Timeline", value: 25, mode: "L" }
 * - "All High" → { allFactors: true, value: 75, mode: "H" }
 */

export interface ParsedVoiceCommand {
  factorId?: string;
  factorName?: string;
  value: number;
  mode: 'L' | 'M' | 'H' | 'custom';
  allFactors?: boolean;
  confidence: number;
  raw: string;
}

interface Factor {
  id: string;
  name: string;
  rating: number;
}

// Value keywords mapping
const VALUE_KEYWORDS: Record<string, { value: number; mode: 'L' | 'M' | 'H' }> = {
  'low': { value: 25, mode: 'L' },
  'lo': { value: 25, mode: 'L' },
  'l': { value: 25, mode: 'L' },
  'medium': { value: 50, mode: 'M' },
  'med': { value: 50, mode: 'M' },
  'mid': { value: 50, mode: 'M' },
  'middle': { value: 50, mode: 'M' },
  'm': { value: 50, mode: 'M' },
  'high': { value: 75, mode: 'H' },
  'hi': { value: 75, mode: 'H' },
  'h': { value: 75, mode: 'H' },
};

// Words to strip from the transcript
const NOISE_WORDS = new Set([
  'set', 'make', 'change', 'update', 'put', 'is', 'to', 'at', 'the',
  'for', 'as', 'a', 'an', 'please', 'can', 'you', 'percent', 'percentage',
  '%', 'it', 'this', 'that', 'factor', 'assessment', 'value', 'rate', 'rating',
]);

/**
 * Calculate similarity between two strings (Dice coefficient)
 */
function similarity(s1: string, s2: string): number {
  if (s1 === s2) return 1;
  if (s1.length < 2 || s2.length < 2) return 0;
  
  const bigrams1 = new Map<string, number>();
  for (let i = 0; i < s1.length - 1; i++) {
    const bigram = s1.substring(i, i + 2);
    const count = (bigrams1.get(bigram) || 0) + 1;
    bigrams1.set(bigram, count);
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

/**
 * Find the best matching factor from the transcript
 */
function findFactor(words: string[], factors: Factor[]): { factor: Factor; matchedWords: string[]; confidence: number } | null {
  let bestMatch: { factor: Factor; matchedWords: string[]; confidence: number } | null = null;
  
  const transcript = words.join(' ');
  
  for (const factor of factors) {
    const factorName = factor.name.toLowerCase().trim();
    const factorWords = factorName.split(/\s+/);
    
    // Try exact substring match first
    if (transcript.includes(factorName)) {
      const confidence = 1.0;
      if (!bestMatch || confidence > bestMatch.confidence || factorName.length > (bestMatch.factor.name.length || 0)) {
        bestMatch = { factor, matchedWords: factorWords, confidence };
      }
      continue;
    }
    
    // Try fuzzy match on the full factor name
    const sim = similarity(transcript, factorName);
    if (sim > 0.5) {
      if (!bestMatch || sim > bestMatch.confidence) {
        bestMatch = { factor, matchedWords: factorWords, confidence: sim };
      }
      continue;
    }
    
    // Try matching individual factor words
    let matchedCount = 0;
    const matched: string[] = [];
    for (const fw of factorWords) {
      for (const tw of words) {
        if (tw === fw || similarity(tw, fw) > 0.7) {
          matchedCount++;
          matched.push(tw);
          break;
        }
      }
    }
    
    const wordConfidence = factorWords.length > 0 ? matchedCount / factorWords.length : 0;
    if (wordConfidence >= 0.5 && matchedCount >= 1) {
      if (!bestMatch || wordConfidence > bestMatch.confidence) {
        bestMatch = { factor, matchedWords: matched, confidence: wordConfidence };
      }
    }
  }
  
  return bestMatch;
}

/**
 * Extract a numeric value from the transcript
 */
function extractNumber(words: string[]): number | null {
  for (const word of words) {
    const num = parseInt(word, 10);
    if (!isNaN(num) && num >= 0 && num <= 100) {
      return num;
    }
  }
  
  // Check for number words
  const numberWords: Record<string, number> = {
    'zero': 0, 'ten': 10, 'twenty': 20, 'thirty': 30, 'forty': 40,
    'fifty': 50, 'sixty': 60, 'seventy': 70, 'eighty': 80, 'ninety': 90,
    'hundred': 100, 'one hundred': 100,
  };
  
  const text = words.join(' ');
  for (const [word, num] of Object.entries(numberWords)) {
    if (text.includes(word)) return num;
  }
  
  return null;
}

/**
 * Extract the assessment value (L/M/H or custom percentage)
 */
function extractValue(words: string[]): { value: number; mode: 'L' | 'M' | 'H' | 'custom' } | null {
  // Check for L/M/H keywords first
  for (const word of words) {
    const clean = word.replace(/[^a-z]/g, '');
    if (VALUE_KEYWORDS[clean]) {
      return VALUE_KEYWORDS[clean];
    }
  }
  
  // Check for numeric percentage
  const num = extractNumber(words);
  if (num !== null) {
    return { value: Math.min(100, Math.max(0, num)), mode: 'custom' };
  }
  
  return null;
}

/**
 * Parse a voice transcript into an assessment command
 */
export function parseVoiceCommand(transcript: string, factors: Factor[]): ParsedVoiceCommand | null {
  if (!transcript || !factors.length) return null;
  
  const raw = transcript;
  const cleaned = transcript.toLowerCase().trim();
  
  // Check for "all" commands first
  const allPattern = /\b(all|everything|every factor)\b/;
  if (allPattern.test(cleaned)) {
    const words = cleaned.split(/\s+/);
    const value = extractValue(words);
    if (value) {
      return {
        allFactors: true,
        value: value.value,
        mode: value.mode,
        confidence: 0.9,
        raw,
      };
    }
  }
  
  // Split into words and filter noise
  const allWords = cleaned.split(/\s+/).filter(w => w.length > 0);
  const meaningfulWords = allWords.filter(w => !NOISE_WORDS.has(w));
  
  // Try to find factor and value
  const factorMatch = findFactor(allWords, factors);
  const value = extractValue(allWords);
  
  // If we only got a value (no factor), return it as a single-value command
  if (!factorMatch && value) {
    return {
      value: value.value,
      mode: value.mode,
      confidence: 0.5,
      raw,
    };
  }
  
  // If we got both factor and value, great!
  if (factorMatch && value) {
    return {
      factorId: factorMatch.factor.id,
      factorName: factorMatch.factor.name,
      value: value.value,
      mode: value.mode,
      confidence: factorMatch.confidence,
      raw,
    };
  }
  
  // If we only got a factor match, return it (caller can prompt for value)
  if (factorMatch) {
    return {
      factorId: factorMatch.factor.id,
      factorName: factorMatch.factor.name,
      value: 0,
      mode: 'L',
      confidence: factorMatch.confidence * 0.5, // Lower confidence without value
      raw,
    };
  }
  
  return null;
}

/**
 * Generate a human-readable description of a parsed command
 */
export function describeCommand(cmd: ParsedVoiceCommand): string {
  const valueStr = cmd.mode === 'custom' ? `${cmd.value}%` : 
    cmd.mode === 'H' ? 'High (75%)' : 
    cmd.mode === 'M' ? 'Medium (50%)' : 'Low (25%)';
  
  if (cmd.allFactors) {
    return `Set all factors → ${valueStr}`;
  }
  
  if (cmd.factorName) {
    return `${cmd.factorName} → ${valueStr}`;
  }
  
  return `Set → ${valueStr}`;
}
