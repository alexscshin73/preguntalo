# Database Schema Notes

This document converts the architecture plan into implementation-oriented tables.

## Core Tables

- `manuals`: logical manual identity
- `manual_versions`: uploaded revisions of a manual
- `file_assets`: stored files in S3 or MinIO
- `sections`: heading-level semantic units
- `chunks`: retrieval units with vectors and keyword fields
- `images`: extracted image assets tied to sections and pages

## Relationships

- one `manual` has many `manual_versions`
- one `manual_version` has many `sections`, `chunks`, `source_pages`, and `images`
- one `section` has many `chunks`
- one `source_page` can have many `images`

## Indexing Plan

- btree on `manual_id`, `manual_version_id`, `language`, `status`
- pgvector index on `chunks.embedding`
- full text or trigram index for keyword retrieval on `chunks.normalized_text`

## Design Notes

- keep source page numbers on both sections and chunks for accurate viewer jumps
- do not store images only as URLs; tie them to extracted page and section metadata
- support future organization scoping from the start
