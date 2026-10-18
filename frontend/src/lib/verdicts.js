// Verdict presentation. Neutral verb phrasing, no scores, no big check/cross icons.
// Full Tailwind class strings are written literally so the content scanner keeps them.
export const VERDICT_META = {
  Hallucinated: {
    label: 'Not supported by evidence',
    chip: 'bg-flag-hallucinated text-on-flag',
    highlight: 'bg-flag-hallucinated/10 underline decoration-flag-hallucinated decoration-2 underline-offset-4',
    dot: 'bg-flag-hallucinated',
  },
  Uncertain: {
    label: 'Could not verify',
    chip: 'bg-flag-uncertain text-on-flag',
    highlight: 'bg-flag-uncertain/10 underline decoration-flag-uncertain decoration-2 underline-offset-4',
    dot: 'bg-flag-uncertain',
  },
  Verified: {
    label: 'Supported by evidence',
    chip: 'bg-flag-verified text-on-flag',
    // PRD FR-06: verified claims are highlighted GREEN (red / amber / green)
    highlight: 'bg-flag-verified/10 underline decoration-flag-verified decoration-2 underline-offset-4',
    dot: 'bg-flag-verified',
  },
}

// Curated demo claims (from DEMO_CLAIMS.md): a dependable mix, both languages.
export const EXAMPLES = [
  { lang: 'en', label: 'Capital of France', text: 'The capital of France is Paris.' },
  { lang: 'en', label: 'Capital of Japan (wrong)', text: 'The capital of Japan is Beijing.' },
  { lang: 'en', label: 'Gandhi', text: 'Mahatma Gandhi was a leader of the Indian independence movement.' },
  { lang: 'en', label: 'Dengue (wrong)', text: 'Dengue fever is a type of bone cancer.' },
  { lang: 'hi', label: 'पेरिस', text: 'पेरिस फ्रांस की राजधानी है।' },
  { lang: 'hi', label: 'ताजमहल (गलत)', text: 'ताजमहल फ्रांस में स्थित है।' },
]
