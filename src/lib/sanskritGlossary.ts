// ---------------------------------------------------------------------------
// Sanskrit glossary — the in-app dictionary used to educate seekers.
// ---------------------------------------------------------------------------
// Key terms that appear in answers are auto-detected and made clickable; a tap
// opens a beautiful dictionary card (see SanskritTermCard). Definitions are
// kept tight, evocative and accurate. `match` holds the lowercased surface
// forms (incl. plurals + Devanagari) we detect in prose.
// ---------------------------------------------------------------------------

export interface GlossaryEntry {
  slug: string;
  /** Romanised display form, e.g. "Dharma". */
  term: string;
  /** Diacritical IAST transliteration, e.g. "dharma". */
  iast: string;
  /** Devanagari script. */
  devanagari: string;
  /** Short literal gloss shown as a chip. */
  translation: string;
  /** One to three sentences — the heart of the card. */
  meaning: string;
  /** Lowercased surface forms to detect in prose (variants, plurals, Devanagari). */
  match: string[];
  /**
   * True for terms that have entered general English vocabulary (yoga, karma,
   * guru, mantra, avatar, nirvana, om, chakra…). These are NEVER auto-linked —
   * a seeker already knows them, so linking them is noise. We only highlight the
   * genuinely unheard terms that actually expand the seeker's vocabulary.
   */
  common?: boolean;
}

// Keyed by slug. Order doesn't matter — detection sorts by length.
export const GLOSSARY: Record<string, GlossaryEntry> = {
  dharma: {
    slug: "dharma", term: "Dharma", iast: "dharma", devanagari: "धर्म",
    translation: "sacred duty; cosmic order",
    meaning: "That which upholds and sustains — the moral law woven into the fabric of existence, and one's own rightful path within it. To live one's dharma is to act in harmony with the order of the cosmos and the truth of one's nature.",
    match: ["dharma", "dharmic", "धर्म"],
    common: true,
  },
  karma: {
    slug: "karma", term: "Karma", iast: "karma", devanagari: "कर्म",
    translation: "action and its fruit",
    meaning: "Action, and the unbroken law by which every action ripens into consequence across this life and the next. Not fate, but causation — the seeds we sow in thought and deed shaping the soil of who we become.",
    match: ["karma", "karmas", "कर्म"],
    common: true,
  },
  moksha: {
    slug: "moksha", term: "Moksha", iast: "mokṣa", devanagari: "मोक्ष",
    translation: "liberation; release",
    meaning: "The final freedom — release from the wheel of birth and death, when the soul knows itself as boundless and is no longer bound by ignorance, desire, or karma. The highest aim of human life.",
    match: ["moksha", "moksa", "mokṣa", "मोक्ष", "mukti", "मुक्ति"],
    common: true,
  },
  atman: {
    slug: "atman", term: "Atman", iast: "ātman", devanagari: "आत्मन्",
    translation: "the true Self; soul",
    meaning: "The innermost Self — pure, deathless awareness that is the witness behind every thought and sense. Distinct from body and mind, the Atman is, in its depth, one with Brahman, the ground of all being.",
    match: ["atman", "ātman", "आत्मन्", "आत्मा"],
  },
  brahman: {
    slug: "brahman", term: "Brahman", iast: "brahman", devanagari: "ब्रह्मन्",
    translation: "the Absolute; ultimate reality",
    meaning: "The infinite, formless ground of all that is — being, consciousness and bliss without limit. The one reality appearing as the many; the ocean of which every wave is a passing shape.",
    match: ["brahman", "ब्रह्मन्", "ब्रह्म"],
  },
  maya: {
    slug: "maya", term: "Maya", iast: "māyā", devanagari: "माया",
    translation: "illusion; cosmic appearance",
    meaning: "The veiling power by which the one appears as the many and the eternal seems to flicker as the fleeting world. Not unreal, but not the final truth — the magic show that hides the magician.",
    match: ["maya", "māyā", "माया"],
    common: true,
  },
  yoga: {
    slug: "yoga", term: "Yoga", iast: "yoga", devanagari: "योग",
    translation: "union; spiritual discipline",
    meaning: "To yoke — the disciplines that still the restless mind and unite the individual soul with the divine. From the stillness of meditation to selfless action and devotion, every path that leads inward is a yoga.",
    match: ["yoga", "yogic", "yogas", "योग"],
    common: true,
  },
  bhakti: {
    slug: "bhakti", term: "Bhakti", iast: "bhakti", devanagari: "भक्ति",
    translation: "loving devotion",
    meaning: "The path of the heart — surrender and love poured toward the Divine until the lover and the beloved are no longer two. The simplest and most tender of the yogas, open to all.",
    match: ["bhakti", "भक्ति"],
  },
  samsara: {
    slug: "samsara", term: "Samsara", iast: "saṃsāra", devanagari: "संसार",
    translation: "the cycle of rebirth",
    meaning: "The ceaseless round of birth, death and rebirth — the wandering of the soul through countless lives, driven by desire and karma, until liberation is won.",
    match: ["samsara", "saṃsāra", "samsaric", "संसार"],
    common: true,
  },
  guna: {
    slug: "guna", term: "Guna", iast: "guṇa", devanagari: "गुण",
    translation: "the three strands of nature",
    meaning: "The three qualities woven through all of nature — sattva (harmony and light), rajas (passion and motion) and tamas (inertia and darkness). Their ever-shifting balance shapes mind, matter and mood.",
    match: ["guna", "gunas", "guṇa", "guṇas", "गुण"],
  },
  sattva: {
    slug: "sattva", term: "Sattva", iast: "sattva", devanagari: "सत्त्व",
    translation: "purity, harmony, light",
    meaning: "The luminous strand of nature — clarity, peace, balance and goodness. When sattva prevails, the mind grows still and lucid, a clear lake reflecting the light of the Self.",
    match: ["sattva", "sattvic", "सत्त्व"],
  },
  rajas: {
    slug: "rajas", term: "Rajas", iast: "rajas", devanagari: "रजस्",
    translation: "passion, activity, restlessness",
    meaning: "The strand of movement and desire — drive, ambition and ceaseless craving. Rajas sets the world in motion, but unchecked it scatters the mind into longing and unrest.",
    match: ["rajas", "rajasic", "रजस्"],
  },
  tamas: {
    slug: "tamas", term: "Tamas", iast: "tamas", devanagari: "तमस्",
    translation: "inertia, darkness, dullness",
    meaning: "The heavy strand of nature — sloth, confusion and the veiling dark. Tamas binds through ignorance and lethargy; yet rest and dissolution, too, are its quiet gifts.",
    match: ["tamas", "tamasic", "तमस्"],
  },
  ahimsa: {
    slug: "ahimsa", term: "Ahimsa", iast: "ahiṃsā", devanagari: "अहिंसा",
    translation: "non-violence; non-harm",
    meaning: "The vow to wound no living being in thought, word or deed. The first and foremost of the yogic restraints, and the root of compassion — reverence for the one life shining in all.",
    match: ["ahimsa", "ahiṃsā", "अहिंसा"],
  },
  prana: {
    slug: "prana", term: "Prana", iast: "prāṇa", devanagari: "प्राण",
    translation: "vital breath; life-force",
    meaning: "The living breath of the cosmos coursing through every being — the subtle energy that animates body and mind. To master the breath is to gather the reins of the life-force itself.",
    match: ["prana", "prāṇa", "pranic", "प्राण"],
  },
  samadhi: {
    slug: "samadhi", term: "Samadhi", iast: "samādhi", devanagari: "समाधि",
    translation: "absorption; union in meditation",
    meaning: "The crown of meditation — total absorption, where the meditator, the act and the object dissolve into one. In samadhi the restless mind grows utterly still and tastes its own boundless depth.",
    match: ["samadhi", "samādhi", "समाधि"],
  },
  dhyana: {
    slug: "dhyana", term: "Dhyana", iast: "dhyāna", devanagari: "ध्यान",
    translation: "meditation; contemplation",
    meaning: "Sustained, unbroken contemplation — the steady flow of attention toward a single point, like oil poured in an unwavering thread. The seventh limb of yoga, ripening into samadhi.",
    match: ["dhyana", "dhyāna", "ध्यान"],
  },
  tapas: {
    slug: "tapas", term: "Tapas", iast: "tapas", devanagari: "तपस्",
    translation: "ascetic fire; spiritual austerity",
    meaning: "The inner heat of disciplined effort — the fire of self-restraint by which the seeker burns away impurity and forges the will. From this 'glowing' come both purification and creative power.",
    match: ["tapas", "tapasya", "तपस्", "तपस्या"],
  },
  sadhana: {
    slug: "sadhana", term: "Sadhana", iast: "sādhanā", devanagari: "साधना",
    translation: "spiritual practice",
    meaning: "The daily, deliberate practice that carries a seeker toward the goal — meditation, recitation, study and service patiently repeated. The path is walked not in leaps but in the faithful steps of sadhana.",
    match: ["sadhana", "sādhanā", "sadhanas", "साधना"],
  },
  guru: {
    slug: "guru", term: "Guru", iast: "guru", devanagari: "गुरु",
    translation: "spiritual teacher; dispeller of darkness",
    meaning: "One who leads from darkness to light — the realised teacher who, having crossed, turns to ferry others. In the lineage of the Puranas the guru's grace is the lamp by which the disciple's own inner flame is lit.",
    match: ["guru", "gurus", "गुरु"],
    common: true,
  },
  mantra: {
    slug: "mantra", term: "Mantra", iast: "mantra", devanagari: "मन्त्र",
    translation: "sacred sound; vibrational prayer",
    meaning: "A sacred syllable or verse whose very sound carries power — 'that which protects the one who reflects upon it.' Repeated with devotion, the mantra steadies the mind and tunes it to the divine.",
    match: ["mantra", "mantras", "मन्त्र", "मंत्र"],
    common: true,
  },
  om: {
    slug: "om", term: "Om", iast: "auṃ / oṃ", devanagari: "ॐ",
    translation: "the primordial sound",
    meaning: "The seed-sound from which all sound and creation arise — the sacred syllable that names the Absolute. Its three measures A-U-M hold waking, dream and deep sleep, and its silence holds the Self beyond all three.",
    match: ["aum", "ॐ", "praṇava", "pranava", "प्रणव"],
    common: true,
  },
  chakra: {
    slug: "chakra", term: "Chakra", iast: "cakra", devanagari: "चक्र",
    translation: "wheel; subtle energy centre",
    meaning: "A spinning wheel of subtle energy along the spine, where the currents of prana converge. As awakened force rises through the chakras, consciousness unfolds from the earthly toward the radiant.",
    match: ["chakra", "chakras", "cakra", "चक्र"],
    common: true,
  },
  kundalini: {
    slug: "kundalini", term: "Kundalini", iast: "kuṇḍalinī", devanagari: "कुण्डलिनी",
    translation: "the coiled serpent-power",
    meaning: "The dormant spiritual energy coiled like a sleeping serpent at the base of the spine. Roused by sadhana, she ascends through the chakras to unite with pure consciousness at the crown — the very awakening of the divine within.",
    match: ["kundalini", "kuṇḍalinī", "कुण्डलिनी"],
    common: true,
  },
  jnana: {
    slug: "jnana", term: "Jnana", iast: "jñāna", devanagari: "ज्ञान",
    translation: "wisdom; liberating knowledge",
    meaning: "Not mere information but realised knowing — the direct, liberating insight into the Self and the Absolute. The yoga of jnana cuts the knot of ignorance with the sword of discernment.",
    match: ["jnana", "jñāna", "gyan", "ज्ञान"],
  },
  vairagya: {
    slug: "vairagya", term: "Vairagya", iast: "vairāgya", devanagari: "वैराग्य",
    translation: "dispassion; non-attachment",
    meaning: "The serene letting-go of craving for the fleeting — neither hatred of the world nor flight from it, but a heart no longer enslaved by it. The twin wing, with practice, that lifts the soul toward freedom.",
    match: ["vairagya", "vairāgya", "वैराग्य"],
  },
  ananda: {
    slug: "ananda", term: "Ananda", iast: "ānanda", devanagari: "आनन्द",
    translation: "bliss; spiritual joy",
    meaning: "The unconditioned bliss that is the very nature of the Self — joy that depends on nothing, the sweetness at the core of pure being. With sat (being) and chit (consciousness) it names the Absolute itself.",
    match: ["ananda", "ānanda", "आनन्द", "आनंद"],
    common: true,
  },
  nirvana: {
    slug: "nirvana", term: "Nirvana", iast: "nirvāṇa", devanagari: "निर्वाण",
    translation: "extinction of the ego-flame",
    meaning: "The 'blowing out' of the fires of craving and the small self — the peace that remains when the ego is extinguished and the soul rests in its own infinite nature.",
    match: ["nirvana", "nirvāṇa", "निर्वाण"],
    common: true,
  },
  purusha: {
    slug: "purusha", term: "Purusha", iast: "puruṣa", devanagari: "पुरुष",
    translation: "pure consciousness; the witness",
    meaning: "The silent, changeless spirit — pure awareness that merely witnesses the dance of nature without acting. In Samkhya, the soul that must learn to distinguish itself from prakriti, the unfolding world.",
    match: ["purusha", "puruṣa", "पुरुष"],
  },
  prakriti: {
    slug: "prakriti", term: "Prakriti", iast: "prakṛti", devanagari: "प्रकृति",
    translation: "primordial nature; matter",
    meaning: "The creative ground of all material existence — body, mind and cosmos alike — woven of the three gunas. Ever-active prakriti dances before the silent witness, purusha, until he knows himself as free.",
    match: ["prakriti", "prakṛti", "प्रकृति"],
  },
  rishi: {
    slug: "rishi", term: "Rishi", iast: "ṛṣi", devanagari: "ऋषि",
    translation: "seer; sage of the Vedas",
    meaning: "A seer who, in the silence of deep meditation, 'heard' the eternal truths and gave them voice as the Vedas. The rishis are the ancient channels through which timeless wisdom entered human speech.",
    match: ["rishi", "rishis", "ṛṣi", "ऋषि"],
  },
  avatar: {
    slug: "avatar", term: "Avatar", iast: "avatāra", devanagari: "अवतार",
    translation: "divine descent; incarnation",
    meaning: "A 'crossing down' of the Divine into the world — God taking form, age after age, to restore dharma when it falters. As Krishna tells Arjuna: whenever righteousness declines, He is born again.",
    match: ["avatar", "avatara", "avatāra", "avatars", "अवतार"],
    common: true,
  },
  darshan: {
    slug: "darshan", term: "Darshan", iast: "darśana", devanagari: "दर्शन",
    translation: "sacred seeing; vision of the divine",
    meaning: "The blessed beholding of the divine — to see and be seen by deity, image or guru, and to receive grace through that meeting of eyes. Darshana also names the great schools of philosophical 'vision.'",
    match: ["darshan", "darshana", "darśana", "दर्शन"],
  },
  yajna: {
    slug: "yajna", term: "Yajna", iast: "yajña", devanagari: "यज्ञ",
    translation: "sacrificial offering; sacred rite",
    meaning: "The fire-offering at the heart of Vedic life — and, inwardly, every act done as offering rather than for gain. The Gita reveals all selfless action as yajna, sustaining the wheel of the worlds.",
    match: ["yajna", "yajña", "yagna", "yagya", "यज्ञ"],
  },
  lila: {
    slug: "lila", term: "Lila", iast: "līlā", devanagari: "लीला",
    translation: "divine play",
    meaning: "Creation as the spontaneous, joyous play of the Divine — the cosmos not laboured into being but danced, sung and sported forth for the sheer delight of it. The world as God's effortless game.",
    match: ["lila", "leela", "līlā", "लीला"],
  },
  shakti: {
    slug: "shakti", term: "Shakti", iast: "śakti", devanagari: "शक्ति",
    translation: "divine power; the Mother",
    meaning: "The dynamic, creative power of the Divine, worshipped as the Great Goddess — the energy without which the still Absolute could not stir. Shiva is the silent ground; Shakti is the living force that moves the worlds.",
    match: ["shakti", "śakti", "शक्ति"],
    common: true,
  },
  vedanta: {
    slug: "vedanta", term: "Vedanta", iast: "vedānta", devanagari: "वेदान्त",
    translation: "the culmination of the Vedas",
    meaning: "'The end of the Vedas' — the body of teaching, rooted in the Upanishads, that inquires into the Self and the Absolute and their ultimate oneness. The summit of Hindu philosophy.",
    match: ["vedanta", "vedānta", "वेदान्त"],
  },
  upanishad: {
    slug: "upanishad", term: "Upanishad", iast: "upaniṣad", devanagari: "उपनिषद्",
    translation: "the secret forest-teachings",
    meaning: "'Sitting near' the teacher — the contemplative scriptures that turn from ritual to the inner quest, revealing the identity of Atman and Brahman. The philosophical heart of the Vedas.",
    match: ["upanishad", "upanishads", "upaniṣad", "उपनिषद्"],
  },
  jiva: {
    slug: "jiva", term: "Jiva", iast: "jīva", devanagari: "जीव",
    translation: "the individual living soul",
    meaning: "The embodied soul — the Self seemingly bound within a particular body, mind and history, journeying through samsara. In truth the jiva is none other than the boundless Atman, only forgetful of its own vastness.",
    match: ["jiva", "jīva", "jivatman", "जीव"],
  },
  viveka: {
    slug: "viveka", term: "Viveka", iast: "viveka", devanagari: "विवेक",
    translation: "discernment; discrimination",
    meaning: "The clear discernment between the real and the unreal, the eternal and the passing, the Self and the not-self. The first instrument of the seeker, parting truth from illusion like a swan sipping milk from water.",
    match: ["viveka", "विवेक"],
  },
  santosha: {
    slug: "santosha", term: "Santosha", iast: "saṃtoṣa", devanagari: "संतोष",
    translation: "contentment",
    meaning: "Serene contentment with what is — a heart at rest, neither grasping for more nor recoiling from less. Among the yogic observances, santosha is said to bring a happiness no outer fortune can equal.",
    match: ["santosha", "saṃtoṣa", "संतोष"],
  },
  seva: {
    slug: "seva", term: "Seva", iast: "sevā", devanagari: "सेवा",
    translation: "selfless service",
    meaning: "Service offered without thought of reward — work as worship, in which the doer dissolves into the doing. Seva purifies the heart and quietly loosens the grip of the ego.",
    match: ["seva", "sevā", "सेवा"],
  },
  shanti: {
    slug: "shanti", term: "Shanti", iast: "śānti", devanagari: "शान्ति",
    translation: "peace",
    meaning: "Deep, abiding peace — not merely the absence of strife but the settled stillness of a mind at one with truth. Chanted thrice at the close of prayer, calling peace to body, world and spirit.",
    match: ["shanti", "śānti", "शान्ति", "शांति"],
  },
};

// ── Detection ──────────────────────────────────────────────────────────────

// At most this many terms are linked in a single answer. The goal is an
// invitation, not an index — a couple of genuinely unfamiliar words glowing in
// the prose, the rest left to read cleanly. (Lookups by slug via getTerm()
// still resolve every entry, common or not — the cap is only for auto-linking.)
export const MAX_LINKS = 3;

// Map every surface form → its slug, and compile one detection regex.
// COMMON terms (yoga, karma, guru, om…) are deliberately EXCLUDED from the
// detection map: a general reader already knows them, so linking them is noise.
// They remain fully available via getTerm()/GLOSSARY for any explicit lookup.
const FORM_TO_SLUG: Record<string, string> = {};
for (const [slug, entry] of Object.entries(GLOSSARY)) {
  if (entry.common) continue; // never auto-link words already in common usage
  for (const f of entry.match) FORM_TO_SLUG[f.toLowerCase()] = slug;
}

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Longest forms first so multi-word / longer matches win over shorter ones.
const FORMS = Object.keys(FORM_TO_SLUG).sort((a, b) => b.length - a.length);

// Unicode-aware word boundaries: not preceded/followed by a letter or combining
// mark, so "yoga" inside "Yogeshwari" or "karma" inside "karmic" won't match.
const TERM_RE = new RegExp(
  `(?<![\\p{L}\\p{M}])(${FORMS.map(escapeRegExp).join("|")})(?![\\p{L}\\p{M}])`,
  "giu"
);

// Protect code fences, inline code, images and existing markdown links from
// term-linking (so we never rewrite inside them).
const PROTECTED_RE = /(```[\s\S]*?```|`[^`]*`|!?\[[^\]]*\]\([^)]*\))/g;

export function getTerm(slug: string): GlossaryEntry | undefined {
  return GLOSSARY[slug];
}

/**
 * Rewrite the first occurrence of up to {@link MAX_LINKS} genuinely-unfamiliar
 * Sanskrit terms in `md` into `[term](term:slug)` markdown links. Two rules keep
 * the prose breathing rather than turning into a glossary:
 *   1. Words already in common English (yoga, karma, om…) are never linked —
 *      they aren't in the detection map at all (see FORM_TO_SLUG above).
 *   2. A hard cap of MAX_LINKS total per answer, first-come, one link per term.
 * Code fences, inline code, images and existing links are left untouched.
 */
export function linkifyTerms(md: string): string {
  if (!md) return md;
  const used = new Set<string>();

  // split() with a capturing group alternates [text, protected, text, ...].
  const parts = md.split(PROTECTED_RE);
  for (let i = 0; i < parts.length; i++) {
    if (i % 2 === 1) continue; // odd indices are protected captures — leave them
    parts[i] = parts[i].replace(TERM_RE, (match) => {
      if (used.size >= MAX_LINKS) return match; // density cap reached
      const slug = FORM_TO_SLUG[match.toLowerCase()];
      if (!slug || used.has(slug)) return match;
      used.add(slug);
      return `[${match}](term:${slug})`;
    });
  }
  return parts.join("");
}
