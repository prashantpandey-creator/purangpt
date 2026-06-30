import Foundation

// MARK: - Library / Explorer wire models
//
// Mirror the live FastAPI responses (confirmed against prod):
//   GET /api/puranas            -> { puranas: [PuranaRef] }
//   GET /api/explore/{id}/intro -> ExploreIntro
//   GET /api/text/{id}?page&size -> TextPage
// Keep field names in sync with backend/main.py; decoding is lenient (optionals)
// so a backend addition never breaks the screen.

/// One entry in the text catalog (`/api/puranas` → `puranas[]`).
struct PuranaRef: Codable, Identifiable, Hashable {
    let id: String
    let name: String
    let category: String?
    let tradition: String?
    let lang: String?
    let bias: String?
    let gretil: Bool?
    let downloaded: Bool?
}

/// AI-generated guide intro for a text (`/api/explore/{id}/intro`).
struct ExploreIntro: Codable, Hashable {
    let textId: String
    let textName: String
    let tagline: String?
    let whatItIs: String?
    let whyItMatters: String?
    let famousStories: [Story]?
    let entryChapters: [EntryChapter]?
    let oneLinePitch: String?

    struct Story: Codable, Hashable, Identifiable {
        var id: String { title }
        let title: String
        let chapterHint: String?
        let description: String?
        enum CodingKeys: String, CodingKey {
            case title
            case chapterHint = "chapter_hint"
            case description
        }
    }

    struct EntryChapter: Codable, Hashable, Identifiable {
        var id: String { (chapterHint ?? "") + (label ?? "") }
        let chapterHint: String?
        let label: String?
        let forReader: String?
        enum CodingKeys: String, CodingKey {
            case chapterHint = "chapter_hint"
            case label
            case forReader = "for_reader"
        }
    }

    enum CodingKeys: String, CodingKey {
        case textId = "text_id"
        case textName = "text_name"
        case tagline
        case whatItIs = "what_it_is"
        case whyItMatters = "why_it_matters"
        case famousStories = "famous_stories"
        case entryChapters = "entry_chapters"
        case oneLinePitch = "one_line_pitch"
    }
}

/// One item from `/api/verses/{chunk_id}/similar`. NOTE: this endpoint's items
/// have a DIFFERENT shape than SourceRef — no `text_name`, they carry `id` +
/// `purana` instead. Confirmed against prod; do not force-fit SourceRef here.
struct SimilarVerse: Codable, Identifiable, Hashable {
    let id: String
    let purana: String?
    let reference: String?
    let verseRange: String?
    let text: String
    let language: String?
    let score: Double?

    enum CodingKeys: String, CodingKey {
        case id
        case purana
        case reference
        case verseRange = "verse_range"
        case text
        case language
        case score
    }
}

/// A paginated slice of raw text lines (`/api/text/{id}`).
struct TextPage: Codable, Hashable {
    let textId: String
    let lines: [String]
    let page: Int
    let totalPages: Int?
    let totalLines: Int?
    let startLine: Int?

    enum CodingKeys: String, CodingKey {
        case textId = "text_id"
        case lines
        case page
        case totalPages = "total_pages"
        case totalLines = "total_lines"
        case startLine = "start_line"
    }
}
