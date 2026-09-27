import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export const SAMPLE_PARAGRAPH =
  'The Taj Mahal is located in Agra, India. It was commissioned in 1632 by the Mughal emperor Shah Jahan. The capital of Japan is Beijing. Dengue fever is transmitted by the Anopheles mosquito.'

export const EXAMPLES: { label: string; text: string; language: 'en' | 'hi' }[] = [
  { label: 'Sample paragraph', text: SAMPLE_PARAGRAPH, language: 'en' },
  { label: 'Paris is the capital of France.', text: 'Paris is the capital of France.', language: 'en' },
  { label: 'The capital of Japan is Beijing.', text: 'The capital of Japan is Beijing.', language: 'en' },
  { label: 'पेरिस फ्रांस की राजधानी है।', text: 'पेरिस फ्रांस की राजधानी है।', language: 'hi' },
  { label: 'ताजमहल फ्रांस में स्थित है।', text: 'ताजमहल फ्रांस में स्थित है।', language: 'hi' },
]

const dateFmt = new Intl.DateTimeFormat('en-GB', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
})

export function formatDate(iso: string): string {
  const d = new Date(iso)
  return Number.isNaN(d.getTime()) ? '' : dateFmt.format(d)
}

export function formatElapsed(ms: number): string {
  const s = Math.floor(ms / 1000)
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`
}

/** Language of a passage from its script: Devanagari -> Hindi, Latin -> English.
 * Null when there are too few letters to tell. Transliterated Hindi (Latin
 * letters) cannot be told from English by script and is reported as English. */
export function detectLanguage(text: string): { language: 'en' | 'hi'; mixed: boolean } | null {
  const deva = text.match(/\p{Script=Devanagari}/gu)?.length ?? 0
  const latin = text.match(/\p{Script=Latin}/gu)?.length ?? 0
  if (deva + latin < 3) return null
  const language = deva > latin ? 'hi' : 'en'
  const minority = Math.min(deva, latin) / (deva + latin)
  return { language, mixed: minority >= 0.2 }
}
