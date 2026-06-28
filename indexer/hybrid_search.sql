-- hybrid_search, fixed for the pgvector 0.5.1 HNSW post-filter trap (incident
-- 2026-06-28): when a metadata filter is present, the HNSW index returns its
-- global ANN candidates first and applies WHERE post-hoc, so a selective filter
-- can drop every candidate → 0 rows (the scripture floor was silently broken).
-- Fix: branch on the filter. No filter → original fast HNSW path, unchanged.
-- Filter present → materialize the filtered subset FIRST, then exact KNN over it.
CREATE OR REPLACE FUNCTION public.hybrid_search(query_text text, query_embedding vector, match_count integer, filter_metadata jsonb DEFAULT '{}'::jsonb)
 RETURNS TABLE(id text, content text, metadata jsonb, similarity double precision)
 LANGUAGE plpgsql
AS $function$
BEGIN
  IF filter_metadata = '{}'::jsonb THEN
    RETURN QUERY
    WITH query_terms AS (
        SELECT websearch_to_tsquery('simple', regexp_replace(trim(query_text), '\s+', ' OR ', 'g')) AS q
    ),
    semantic_search AS (
        SELECT pv.id, pv.content, pv.metadata,
               1 - (pv.embedding <=> query_embedding) AS sim,
               ROW_NUMBER() OVER (ORDER BY pv.embedding <=> query_embedding) AS semantic_rank
        FROM purana_verses pv
        WHERE pv.embedding IS NOT NULL
        ORDER BY pv.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    keyword_search AS (
        SELECT pv.id, ts_rank(pv.fts, qt.q) AS fts_rank,
               ROW_NUMBER() OVER (ORDER BY ts_rank(pv.fts, qt.q) DESC) AS keyword_rank
        FROM purana_verses pv CROSS JOIN query_terms qt
        WHERE pv.fts @@ qt.q
        ORDER BY fts_rank DESC
        LIMIT match_count * 2
    )
    SELECT COALESCE(ss.id, ks.id) AS id,
           COALESCE(ss.content, (SELECT p.content FROM purana_verses p WHERE p.id = ks.id)) AS content,
           COALESCE(ss.metadata, (SELECT p.metadata FROM purana_verses p WHERE p.id = ks.id)) AS metadata,
           (COALESCE(1.0 / (60 + ss.semantic_rank), 0.0) + COALESCE(1.0 / (60 + ks.keyword_rank), 0.0))::FLOAT AS similarity
    FROM semantic_search ss
    FULL OUTER JOIN keyword_search ks ON ss.id = ks.id
    ORDER BY similarity DESC
    LIMIT match_count;
  ELSE
    RETURN QUERY
    WITH query_terms AS (
        SELECT websearch_to_tsquery('simple', regexp_replace(trim(query_text), '\s+', ' OR ', 'g')) AS q
    ),
    filtered AS MATERIALIZED (
        SELECT pv.id, pv.content, pv.metadata, pv.embedding, pv.fts
        FROM purana_verses pv
        WHERE pv.embedding IS NOT NULL
          AND pv.metadata @> filter_metadata
    ),
    semantic_search AS (
        SELECT f.id, f.content, f.metadata,
               1 - (f.embedding <=> query_embedding) AS sim,
               ROW_NUMBER() OVER (ORDER BY f.embedding <=> query_embedding) AS semantic_rank
        FROM filtered f
        ORDER BY f.embedding <=> query_embedding
        LIMIT match_count * 2
    ),
    keyword_search AS (
        SELECT f.id, ts_rank(f.fts, qt.q) AS fts_rank,
               ROW_NUMBER() OVER (ORDER BY ts_rank(f.fts, qt.q) DESC) AS keyword_rank
        FROM filtered f CROSS JOIN query_terms qt
        WHERE f.fts @@ qt.q
        ORDER BY fts_rank DESC
        LIMIT match_count * 2
    )
    SELECT COALESCE(ss.id, ks.id) AS id,
           COALESCE(ss.content, (SELECT p.content FROM purana_verses p WHERE p.id = ks.id)) AS content,
           COALESCE(ss.metadata, (SELECT p.metadata FROM purana_verses p WHERE p.id = ks.id)) AS metadata,
           (COALESCE(1.0 / (60 + ss.semantic_rank), 0.0) + COALESCE(1.0 / (60 + ks.keyword_rank), 0.0))::FLOAT AS similarity
    FROM semantic_search ss
    FULL OUTER JOIN keyword_search ks ON ss.id = ks.id
    ORDER BY similarity DESC
    LIMIT match_count;
  END IF;
END;
$function$;
