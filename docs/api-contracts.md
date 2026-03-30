# API Contracts

## Public App Routes

- `GET /api/v1/health`
- `GET /api/v1/manuals`
- `POST /api/v1/manuals`
- `GET /api/v1/manuals/{manualId}/versions`
- `POST /api/v1/manuals/{manualId}/upload`
- `POST /api/v1/search`
- `GET /api/v1/sections/{sectionId}`

## Search Contract

Input:

- `query`
- `language`
- `manualIds`
- `topK`

Output:

- ranked section list
- snippet
- score
- source page range
- detail route

## Section Detail Contract

Output:

- grounded summary
- citations
- related images
- viewer links

## Current Implementation Notes

- upload flow stores file assets and creates manual versions
- ingestion currently parses `txt`, `md`, `docx`, and basic `pdf`
- source pages, sections, and chunks are stored during ingestion
- chunks now store embeddings for hybrid keyword plus semantic retrieval
