#!/usr/bin/env swift
//
// Decode test for the Library/Explorer wire models against REAL prod fixtures.
// Run:  swift test_library_decode.swift   (exits 0 on pass, fatalError on fail)
//
// Precondition-A: the CodingKeys mapping (snake_case nested inside stories and
// chapters) is a deterministic decode contract. We prove it decodes the actual
// captured /api/puranas and /api/explore/agni/intro responses — the exact bytes
// the app will receive — not handcrafted JSON.
//
// The struct definitions below are copied verbatim from LibraryModels.swift; if
// you change one, change both.

import Foundation

struct PuranaRef: Codable {
    let id: String; let name: String
    let category: String?; let tradition: String?
    let lang: String?; let bias: String?
    let gretil: Bool?; let downloaded: Bool?
}

struct ExploreIntro: Codable {
    let textId: String; let textName: String
    let tagline: String?; let whatItIs: String?; let whyItMatters: String?
    let famousStories: [Story]?; let entryChapters: [EntryChapter]?
    let oneLinePitch: String?

    struct Story: Codable {
        let title: String; let chapterHint: String?; let description: String?
        enum CodingKeys: String, CodingKey { case title; case chapterHint = "chapter_hint"; case description }
    }
    struct EntryChapter: Codable {
        let chapterHint: String?; let label: String?; let forReader: String?
        enum CodingKeys: String, CodingKey { case chapterHint = "chapter_hint"; case label; case forReader = "for_reader" }
    }
    enum CodingKeys: String, CodingKey {
        case textId = "text_id"; case textName = "text_name"
        case tagline; case whatItIs = "what_it_is"; case whyItMatters = "why_it_matters"
        case famousStories = "famous_stories"; case entryChapters = "entry_chapters"
        case oneLinePitch = "one_line_pitch"
    }
}

func assert(_ cond: Bool, _ msg: String) { if !cond { fatalError("ASSERT FAILED: \(msg)") } }

let here = URL(fileURLWithPath: #filePath).deletingLastPathComponent()

// --- Catalog ---
struct CatalogEnvelope: Codable { let puranas: [PuranaRef] }
let catalogData = try! Data(contentsOf: here.appendingPathComponent("catalog_fixture.json"))
let catalog = try! JSONDecoder().decode(CatalogEnvelope.self, from: catalogData)
assert(catalog.puranas.count >= 20, "expected 20+ texts, got \(catalog.puranas.count)")
let agni = catalog.puranas.first { $0.id == "agni" }
assert(agni != nil, "agni not found in catalog")
assert(agni?.name == "Agni Purana", "agni name wrong: \(String(describing: agni?.name))")
assert(agni?.gretil == true, "agni gretil flag wrong")

// --- Explore intro (the nested-CodingKeys gauntlet) ---
let introData = try! Data(contentsOf: here.appendingPathComponent("intro_fixture.json"))
let intro = try! JSONDecoder().decode(ExploreIntro.self, from: introData)
assert(intro.textId == "agni", "intro text_id wrong: \(intro.textId)")
assert(intro.tagline?.isEmpty == false, "tagline empty")
assert((intro.famousStories?.count ?? 0) >= 4, "expected 4+ stories, got \(intro.famousStories?.count ?? 0)")
// The nested chapter_hint must decode (this is the bit a naive decoder drops).
let firstStory = intro.famousStories!.first!
assert(firstStory.chapterHint != nil, "story.chapter_hint did not decode")
let firstChapter = intro.entryChapters!.first!
assert(firstChapter.chapterHint != nil, "entry chapter.chapter_hint did not decode")
assert(firstChapter.forReader != nil, "entry chapter.for_reader did not decode")

// --- Similar verses (the no-text_name shape that would CRASH SourceRef) ---
struct SimilarVerse: Codable {
    let id: String; let purana: String?; let reference: String?
    let verseRange: String?; let text: String; let language: String?; let score: Double?
    enum CodingKeys: String, CodingKey {
        case id; case purana; case reference; case verseRange = "verse_range"
        case text; case language; case score
    }
}
struct SimilarEnvelope: Codable { let similar: [SimilarVerse] }
let simData = try! Data(contentsOf: here.appendingPathComponent("similar_fixture.json"))
let sim = try! JSONDecoder().decode(SimilarEnvelope.self, from: simData)
assert(sim.similar.count >= 1, "expected similar verses, got \(sim.similar.count)")
assert(sim.similar[0].text.isEmpty == false, "similar verse text empty")
assert(sim.similar[0].id.isEmpty == false, "similar verse id empty")
// The whole point: these items have NO text_name — decoding must not require it.
print("✅ similar decode passed (\(sim.similar.count) verses, no text_name shape OK)")

print("✅ library decode passed (\(catalog.puranas.count) texts; intro: \(intro.famousStories!.count) stories, \(intro.entryChapters!.count) chapters, nested snake_case OK)")
