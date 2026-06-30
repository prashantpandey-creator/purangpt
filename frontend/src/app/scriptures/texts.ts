/**
 * texts.ts — canonical, typed catalogue of the scriptures that get their own
 * programmatic-SEO landing page under /scriptures/<slug>.
 *
 * ADDITIVE & SELF-CONTAINED: pure data, no imports, no side effects. Consumed by
 * the /scriptures index page, the /scriptures/[slug] dynamic page (params +
 * metadata + JSON-LD), and the sitemap. Edit summaries with care — this is a
 * sacred-text app; keep every line factually accurate and reverent, and never
 * invent specific verse numbers.
 */

export interface ScriptureText {
  /** URL slug, e.g. "bhagavad-gita" → /scriptures/bhagavad-gita */
  slug: string;
  /** Display name in English/transliteration. */
  name: string;
  /** Name in Devanagari. */
  sanskritName: string;
  /** High-level grouping shown as the card eyebrow. */
  category: string;
  /** 2–3 reverent, factually-accurate sentences. */
  summary: string;
  /** Major themes a seeker would search for. */
  themes: string[];
  /** 3–5 real long-tail questions a seeker would type into Google. */
  sampleQuestions: string[];
  /**
   * Slugs of genuinely related texts (shared epic, same category, or a direct
   * textual relationship). Powers the "Related Scriptures" cross-links that bind
   * the /scriptures cluster into a topical authority graph. Every entry must be
   * a real slug in this catalogue and a real relationship — no arbitrary links.
   */
  relatedTexts?: string[];
}

export const SCRIPTURES: ScriptureText[] = [
  {
    slug: "bhagavad-gita",
    name: "Bhagavad Gita",
    sanskritName: "भगवद्गीता",
    category: "Epic Dialogue",
    summary:
      "The Bhagavad Gita is a 700-verse dialogue set within the Mahabharata, spoken by Krishna to the warrior Arjuna on the battlefield of Kurukshetra as he despairs over the coming war. In it Krishna unfolds the paths of selfless action (karma yoga), devotion (bhakti yoga), and knowledge (jnana yoga), and reveals his universal form. It remains the most widely read and translated text of Hindu philosophy.",
    themes: [
      "Dharma and right action",
      "Karma yoga — selfless action",
      "Bhakti — loving devotion",
      "The eternal soul (atman)",
      "Detachment from the fruits of action",
    ],
    sampleQuestions: [
      "What does the Bhagavad Gita say about duty and dharma?",
      "What is karma yoga according to Krishna?",
      "Why does Arjuna refuse to fight at the start of the Gita?",
      "What does Krishna teach about the soul being eternal?",
      "How does the Gita describe the three paths of yoga?",
    ],
    relatedTexts: ["mahabharata", "upanishads", "bhagavata-purana"],
  },
  {
    slug: "ramayana",
    name: "Ramayana",
    sanskritName: "रामायणम्",
    category: "Itihasa — Epic",
    summary:
      "The Ramayana, traditionally attributed to the sage Valmiki, narrates the life of Prince Rama of Ayodhya — his exile, the abduction of his wife Sita by the demon king Ravana, and her rescue with the help of the monkey-god Hanuman. Across its books it explores ideal kingship, devotion, and the triumph of dharma over adharma. It is one of the two great epics (itihasas) of the Hindu tradition.",
    themes: [
      "Dharma and ideal conduct",
      "Devotion and loyalty (Hanuman, Sita)",
      "Exile and righteousness",
      "Good versus evil (Rama and Ravana)",
      "The ideal king and the ideal family",
    ],
    sampleQuestions: [
      "What is the main story of the Ramayana?",
      "Why was Rama exiled to the forest for fourteen years?",
      "How did Hanuman help Rama find Sita?",
      "What lessons does the Ramayana teach about dharma?",
      "Who wrote the Ramayana and when?",
    ],
    relatedTexts: ["mahabharata", "bhagavad-gita"],
  },
  {
    slug: "mahabharata",
    name: "Mahabharata",
    sanskritName: "महाभारतम्",
    category: "Itihasa — Epic",
    summary:
      "The Mahabharata, attributed to the sage Vyasa, is among the longest epic poems ever composed and tells of the dynastic struggle between the Pandavas and the Kauravas, culminating in the great war at Kurukshetra. Beyond its narrative, it is a vast repository of philosophy, statecraft, and ethics, and it contains the Bhagavad Gita. It is revered as the fifth Veda for the breadth of dharma it preserves.",
    themes: [
      "Dharma in conflict and dilemma",
      "The Kurukshetra war",
      "Duty, kinship, and rivalry",
      "Statecraft and ethics",
      "Fate, free will, and consequence",
    ],
    sampleQuestions: [
      "What is the Mahabharata about?",
      "What caused the war between the Pandavas and Kauravas?",
      "Who is the author of the Mahabharata?",
      "What is the role of the Bhagavad Gita within the Mahabharata?",
      "What does the Mahabharata teach about dharma in difficult choices?",
    ],
    relatedTexts: ["bhagavad-gita", "ramayana"],
  },
  {
    slug: "bhagavata-purana",
    name: "Bhagavata Purana",
    sanskritName: "श्रीमद्भागवतम्",
    category: "Mahapurana",
    summary:
      "The Bhagavata Purana, also called the Srimad Bhagavatam, is among the most revered of the eighteen Mahapuranas and centres on devotion (bhakti) to Vishnu and his avatars, most fully the life and play of Krishna. Composed largely as a dialogue and arranged into twelve books (skandhas), it weaves cosmology, the lives of devotees, and the lilas of Krishna into a single devotional vision. It is foundational to the Vaishnava bhakti traditions.",
    themes: [
      "Bhakti — loving devotion to Vishnu",
      "The avatars of Vishnu",
      "The life and lilas of Krishna",
      "Cosmology and creation",
      "Stories of great devotees",
    ],
    sampleQuestions: [
      "What is the Bhagavata Purana about?",
      "What does the Bhagavata Purana teach about Krishna's childhood?",
      "What are the ten avatars of Vishnu in the Bhagavata Purana?",
      "What is bhakti according to the Srimad Bhagavatam?",
      "How many books (skandhas) does the Bhagavata Purana have?",
    ],
    relatedTexts: ["vishnu-purana", "padma-purana", "bhagavad-gita"],
  },
  {
    slug: "vishnu-purana",
    name: "Vishnu Purana",
    sanskritName: "विष्णुपुराणम्",
    category: "Mahapurana",
    summary:
      "The Vishnu Purana is one of the eighteen Mahapuranas and is often regarded as a model of the Puranic genre for its clear treatment of the traditional five subjects: creation, dissolution and recreation, the lineages of gods and sages, the cosmic ages, and the genealogies of kings. Framed as a dialogue between the sage Parashara and his disciple Maitreya, it presents Vishnu as the supreme reality from whom all proceeds. It is a central text of Vaishnava tradition.",
    themes: [
      "Vishnu as the supreme reality",
      "Cosmology and the cycles of creation",
      "The cosmic ages (yugas)",
      "Genealogies of gods, sages, and kings",
      "Dharma and devotion",
    ],
    sampleQuestions: [
      "What is the Vishnu Purana about?",
      "What does the Vishnu Purana say about creation?",
      "What are the four yugas described in the Vishnu Purana?",
      "Who narrates the Vishnu Purana?",
      "How does the Vishnu Purana describe Vishnu?",
    ],
    relatedTexts: ["bhagavata-purana", "padma-purana", "garuda-purana"],
  },
  {
    slug: "shiva-purana",
    name: "Shiva Purana",
    sanskritName: "शिवपुराणम्",
    category: "Mahapurana",
    summary:
      "The Shiva Purana is one of the eighteen Mahapuranas and is devoted to the worship and glory of Shiva. It recounts his cosmic role as destroyer and regenerator, the sacred meaning of the lingam, his marriage to Parvati, and the practices of his devotees. It is a foundational scripture for the Shaiva traditions and a rich source of devotional and ritual lore.",
    themes: [
      "Devotion to Shiva",
      "The meaning of the lingam",
      "Shiva and Parvati",
      "Cosmic destruction and renewal",
      "Pilgrimage, fasting, and worship",
    ],
    sampleQuestions: [
      "What is the Shiva Purana about?",
      "What does the Shiva Purana say about the meaning of the lingam?",
      "What is the story of Shiva and Parvati's marriage?",
      "Why is Shiva called the destroyer in the Shiva Purana?",
      "What practices of devotion does the Shiva Purana describe?",
    ],
    relatedTexts: ["skanda-purana", "markandeya-purana"],
  },
  {
    slug: "markandeya-purana",
    name: "Markandeya Purana",
    sanskritName: "मार्कण्डेयपुराणम्",
    category: "Mahapurana",
    summary:
      "The Markandeya Purana is one of the oldest of the eighteen Mahapuranas, structured largely as answers given by the sage Markandeya. It is best known for containing the Devi Mahatmya (also called the Durga Saptashati), the celebrated hymn to the Great Goddess that recounts her victory over the demons Mahishasura, Shumbha, and Nishumbha. It is a central scripture for the worship of the Goddess (Shakti).",
    themes: [
      "The Great Goddess (Devi / Shakti)",
      "The Devi Mahatmya",
      "Victory of divine power over the demons",
      "Dharma and cosmic order",
      "Dialogues of the sage Markandeya",
    ],
    sampleQuestions: [
      "What is the Markandeya Purana about?",
      "What is the Devi Mahatmya in the Markandeya Purana?",
      "How does the Goddess defeat Mahishasura?",
      "Why is the Markandeya Purana important for Goddess worship?",
      "Who is the sage Markandeya?",
    ],
    relatedTexts: ["shiva-purana", "skanda-purana"],
  },
  {
    slug: "garuda-purana",
    name: "Garuda Purana",
    sanskritName: "गरुडपुराणम्",
    category: "Mahapurana",
    summary:
      "The Garuda Purana is one of the eighteen Mahapuranas, framed as a discourse from Vishnu to his mount Garuda. It is especially known for its detailed treatment of death, the soul's journey after death, the rites for the departed, and the fruits of karma. Alongside these eschatological teachings it covers cosmology, ethics, and devotion to Vishnu, and it is widely consulted in the context of funerary tradition.",
    themes: [
      "Death and the afterlife",
      "The journey of the soul",
      "Rites for the departed",
      "Karma and its fruits",
      "Devotion to Vishnu",
    ],
    sampleQuestions: [
      "What is the Garuda Purana about?",
      "What does the Garuda Purana say about life after death?",
      "Why is the Garuda Purana read after a death in the family?",
      "What does the Garuda Purana teach about karma?",
      "Who narrates the Garuda Purana?",
    ],
    relatedTexts: ["vishnu-purana", "bhagavata-purana"],
  },
  {
    slug: "skanda-purana",
    name: "Skanda Purana",
    sanskritName: "स्कन्दपुराणम्",
    category: "Mahapurana",
    summary:
      "The Skanda Purana is the largest of the eighteen Mahapuranas and takes its name from Skanda (Kartikeya), the son of Shiva. It is a vast compilation rich in accounts of sacred geography — pilgrimage sites (tirthas), temples, and the holiness of rivers and places — alongside myth, ritual, and devotional teaching. Its many sections (khandas) make it an extensive treasury of pilgrimage and legend.",
    themes: [
      "Skanda (Kartikeya), son of Shiva",
      "Sacred geography and pilgrimage (tirthas)",
      "Temple and place legends",
      "Devotion and ritual",
      "Myth and cosmology",
    ],
    sampleQuestions: [
      "What is the Skanda Purana about?",
      "Why is the Skanda Purana the largest Purana?",
      "Who is Skanda in the Skanda Purana?",
      "What does the Skanda Purana say about pilgrimage sites?",
      "What are the khandas of the Skanda Purana?",
    ],
    relatedTexts: ["shiva-purana", "markandeya-purana"],
  },
  {
    slug: "padma-purana",
    name: "Padma Purana",
    sanskritName: "पद्मपुराणम्",
    category: "Mahapurana",
    summary:
      "The Padma Purana is one of the eighteen Mahapuranas, taking its name from the lotus (padma) that arose from Vishnu at creation. Organised into several books (khandas), it spans cosmology, sacred geography, the glory of holy places, and devotional accounts centred on Vishnu, along with retellings of well-known stories. It is a substantial Vaishnava scripture valued for its breadth of myth and devotion.",
    themes: [
      "Devotion to Vishnu",
      "Creation and the cosmic lotus",
      "Sacred places and pilgrimage",
      "Myth and retold epic stories",
      "Ritual and the fruits of devotion",
    ],
    sampleQuestions: [
      "What is the Padma Purana about?",
      "Why is it called the Padma Purana?",
      "What does the Padma Purana teach about Vishnu?",
      "What are the main sections of the Padma Purana?",
      "What sacred places does the Padma Purana describe?",
    ],
    relatedTexts: ["bhagavata-purana", "vishnu-purana"],
  },
  {
    slug: "upanishads",
    name: "The Upanishads",
    sanskritName: "उपनिषदः",
    category: "Vedanta — Collection",
    summary:
      "The Upanishads are a collection of philosophical texts that form the concluding portion of the Vedas and the foundation of Vedanta. Through dialogues and contemplations they inquire into the nature of ultimate reality (Brahman), the self (atman), and their relationship, articulating insights such as the identity of the individual self with the absolute. The principal Upanishads are among the most influential philosophical writings of the Hindu tradition.",
    themes: [
      "Brahman — ultimate reality",
      "Atman — the self",
      "The unity of self and absolute",
      "Liberation (moksha)",
      "Meditation and inner inquiry",
    ],
    sampleQuestions: [
      "What are the Upanishads about?",
      "What is Brahman according to the Upanishads?",
      "What does 'Tat Tvam Asi' mean in the Upanishads?",
      "How many Upanishads are there?",
      "What do the Upanishads teach about the self (atman)?",
    ],
    relatedTexts: ["vedas", "bhagavad-gita"],
  },
  {
    slug: "vedas",
    name: "The Vedas",
    sanskritName: "वेदाः",
    category: "Shruti — Collection",
    summary:
      "The Vedas are the oldest and most authoritative scriptures of the Hindu tradition, regarded as shruti — revealed knowledge preserved through oral transmission. They comprise four collections — the Rigveda, Yajurveda, Samaveda, and Atharvaveda — each containing hymns, ritual formulas, and chants, along with later layers of the Brahmanas, Aranyakas, and Upanishads. They are the root from which the wider corpus of Hindu thought and practice grows.",
    themes: [
      "Shruti — revealed knowledge",
      "The four Vedas",
      "Hymns, mantras, and ritual",
      "Cosmic order (rta) and the deities",
      "The roots of later Hindu philosophy",
    ],
    sampleQuestions: [
      "What are the four Vedas?",
      "What is the difference between the Rigveda and the other Vedas?",
      "What do the Vedas contain?",
      "Why are the Vedas considered shruti?",
      "How old are the Vedas?",
    ],
    relatedTexts: ["upanishads", "bhagavad-gita"],
  },
];

/** Lookup by slug — used by the dynamic [slug] page. */
export function getScriptureBySlug(slug: string): ScriptureText | undefined {
  return SCRIPTURES.find((t) => t.slug === slug);
}
