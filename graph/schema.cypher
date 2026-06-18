CREATE CONSTRAINT knowledge_chunk_id IF NOT EXISTS
FOR (c:KnowledgeChunk) REQUIRE c.chunk_id IS UNIQUE;

CREATE INDEX knowledge_chunk_country IF NOT EXISTS
FOR (c:KnowledgeChunk) ON (c.country);

CREATE INDEX knowledge_chunk_category IF NOT EXISTS
FOR (c:KnowledgeChunk) ON (c.category);

CREATE VECTOR INDEX `knowledge-chunk-embeddings` IF NOT EXISTS
FOR (c:KnowledgeChunk) ON (c.embedding)
OPTIONS {indexConfig: {
  `vector.dimensions`: 768,
  `vector.similarity_function`: 'cosine'
}};
