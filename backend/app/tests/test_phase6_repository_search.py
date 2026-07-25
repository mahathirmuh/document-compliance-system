"""Focused ordering and search-contract tests for Phase 6 repositories."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql, sqlite

from app.models.extracted_block import ExtractedBlock, ExtractedBlockType
from app.models.extracted_container import (
    ExtractedContainer,
    ExtractedContainerType,
)
from app.models.extracted_table import ExtractedTable
from app.models.extraction_run import ExtractionRun
from app.repositories.extracted_block_repository import (
    ExtractedBlockRepository,
    _block_search_predicate,
)
from app.repositories.extracted_table_repository import (
    ExtractedTableRepository,
)
from app.tests.test_phase6_persistence import (
    _document_graph,
    _job,
    _run,
)


def test_block_search_predicate_matches_postgresql_gin_expression() -> None:
    predicate = _block_search_predicate(
        "governance policy",
        extraction_run_id=UUID(int=1),
        dialect_name="postgresql",
        include_container_name=False,
    )

    sql = str(
        predicate.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert sql == (
        "to_tsvector("
        "'simple', extracted_blocks.normalised_text || ' ' || "
        "extracted_blocks.source_reference"
        ") "
        "@@ plainto_tsquery('simple', 'governance policy')"
    )


def test_postgresql_search_uses_indexed_container_subquery() -> None:
    predicate = _block_search_predicate(
        "Page One",
        extraction_run_id=UUID(int=1),
        dialect_name="postgresql",
        include_container_name=True,
    )

    sql = str(
        predicate.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "extracted_blocks.container_id IN (SELECT" in sql
    assert "extracted_containers.extraction_run_id =" in sql
    assert (
        "to_tsvector('simple', extracted_containers.name) "
        "@@ plainto_tsquery('simple', 'Page One')"
    ) in sql
    assert "ILIKE" not in sql


def test_block_search_predicate_has_sqlite_ilike_fallback() -> None:
    predicate = _block_search_predicate(
        "governance",
        extraction_run_id=UUID(int=1),
        dialect_name="sqlite",
        include_container_name=True,
    )

    sql = str(
        predicate.compile(
            dialect=sqlite.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "to_tsvector" not in sql
    assert "lower(extracted_blocks.normalised_text)" in sql
    assert "lower(extracted_blocks.source_reference)" in sql
    assert "lower(extracted_containers.name)" in sql
    assert "'%governance%'" in sql


def test_search_indexes_match_repository_expressions() -> None:
    block_indexes = {
        index.name: index
        for index in ExtractedBlock.__table__.indexes
    }
    container_indexes = {
        index.name: index
        for index in ExtractedContainer.__table__.indexes
    }

    block_index = block_indexes[
        "ix_extracted_blocks_normalised_text_search"
    ]
    assert str(block_index.expressions[0]) == (
        "to_tsvector("
        "'simple'::regconfig, "
        "(normalised_text || ' '::text) || source_reference::text"
        ")"
    )
    assert block_index.dialect_options["postgresql"]["using"] == "gin"

    container_index = container_indexes[
        "ix_extracted_containers_name_search"
    ]
    assert str(container_index.expressions[0]) == (
        "to_tsvector('simple', name)"
    )
    assert container_index.dialect_options["postgresql"]["using"] == "gin"


def test_phase6_migration_creates_and_drops_search_indexes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    migration = runpy.run_path(
        str(
            Path(__file__).parents[2]
            / "alembic"
            / "versions"
            / "20260725_0005_phase6_document_content_extraction.py"
        )
    )
    operations = _MigrationOperationRecorder()
    migration["upgrade"].__globals__["op"] = operations

    migration["upgrade"]()

    created_indexes = {
        args[0]: (args, kwargs)
        for operation, args, kwargs in operations.calls
        if operation == "create_index"
    }
    block_args, block_kwargs = created_indexes[
        "ix_extracted_blocks_normalised_text_search"
    ]
    assert str(block_args[2][0]) == (
        "to_tsvector("
        "'simple', normalised_text || ' ' || source_reference"
        ")"
    )
    assert block_kwargs["postgresql_using"] == "gin"

    container_args, container_kwargs = created_indexes[
        "ix_extracted_containers_name_search"
    ]
    assert str(container_args[2][0]) == "to_tsvector('simple', name)"
    assert container_kwargs["postgresql_using"] == "gin"

    monkeypatch.setattr(
        migration["sa"].Enum,
        "drop",
        lambda self, bind, checkfirst=True: None,
    )
    operations.calls.clear()
    migration["downgrade"]()
    dropped_indexes = {
        args[0]
        for operation, args, _ in operations.calls
        if operation == "drop_index"
    }
    assert {
        "ix_extracted_blocks_normalised_text_search",
        "ix_extracted_containers_name_search",
    }.issubset(dropped_indexes)


@pytest.mark.asyncio
async def test_content_repository_ordering_and_search_totals(
    session_factory,
) -> None:
    document, revision, document_file = _document_graph()
    job = _job(document, revision, document_file)
    run = _run(job, document, revision, document_file)
    first_container = ExtractedContainer(
        id=UUID(int=101),
        extraction_run=run,
        container_type=ExtractedContainerType.PDF_PAGE,
        container_index=1,
        name="First",
        raw_text="needle",
        normalised_text="needle",
        character_count=6,
        word_count=1,
    )
    second_container = ExtractedContainer(
        id=UUID(int=102),
        extraction_run=run,
        container_type=ExtractedContainerType.PDF_PAGE,
        container_index=2,
        name="Second",
        raw_text="needle",
        normalised_text="needle",
        character_count=6,
        word_count=1,
    )
    blocks = [
        _block(UUID(int=203), first_container, run, block_order=1),
        _block(UUID(int=202), first_container, run, block_order=1),
        _block(UUID(int=204), first_container, run, block_order=2),
        _block(UUID(int=205), second_container, run, block_order=1),
    ]
    blocks[0].source_reference = "reference-only"
    tables = [
        _table(UUID(int=303), first_container, run, table_index=1),
        _table(UUID(int=302), first_container, run, table_index=1),
        _table(UUID(int=304), first_container, run, table_index=2),
        _table(UUID(int=305), second_container, run, table_index=1),
    ]

    async with session_factory() as session:
        session.add_all(
            [
                document,
                revision,
                document_file,
                job,
                run,
                first_container,
                second_container,
                *blocks,
                *tables,
            ]
        )
        await session.commit()
        block_repository = ExtractedBlockRepository(session)
        table_repository = ExtractedTableRepository(session)

        blocks_ascending, block_total = await block_repository.list(
            run.id,
            page_size=10,
            sort_order="asc",
        )
        blocks_descending, _ = await block_repository.list(
            run.id,
            page_size=10,
            sort_order="desc",
        )
        block_matches, block_match_total = await block_repository.search(
            run.id,
            "needle",
            limit=2,
        )
        reference_matches, reference_total = await block_repository.list(
            run.id,
            search="reference-only",
        )
        container_matches, container_total = await block_repository.search(
            run.id,
            "Second",
        )
        table_items, table_total = await table_repository.list(
            run.id,
            page_size=10,
        )
        table_matches, table_match_total = await table_repository.search(
            run.id,
            "needle",
            limit=2,
        )

    assert block_total == 4
    assert [item.id for item in blocks_ascending] == [
        UUID(int=202),
        UUID(int=203),
        UUID(int=204),
        UUID(int=205),
    ]
    assert [item.id for item in blocks_descending] == [
        UUID(int=205),
        UUID(int=204),
        UUID(int=203),
        UUID(int=202),
    ]
    assert block_match_total == 4
    assert [item.id for item in block_matches] == [
        UUID(int=202),
        UUID(int=203),
    ]
    assert reference_total == 1
    assert [item.id for item in reference_matches] == [UUID(int=203)]
    assert container_total == 1
    assert [item.id for item in container_matches] == [UUID(int=205)]

    assert table_total == 4
    assert [item.id for item in table_items] == [
        UUID(int=302),
        UUID(int=303),
        UUID(int=304),
        UUID(int=305),
    ]
    assert table_match_total == 4
    assert [item.id for item in table_matches] == [
        UUID(int=302),
        UUID(int=303),
    ]


def _block(
    block_id: UUID,
    container: ExtractedContainer,
    run: ExtractionRun,
    *,
    block_order: int,
) -> ExtractedBlock:
    return ExtractedBlock(
        id=block_id,
        extraction_run=run,
        container=container,
        block_type=ExtractedBlockType.TEXT,
        block_order=block_order,
        source_reference=f"block-{block_id.int}",
        text="needle",
        normalised_text="needle",
        character_count=6,
        word_count=1,
    )


def _table(
    table_id: UUID,
    container: ExtractedContainer,
    run: ExtractionRun,
    *,
    table_index: int,
) -> ExtractedTable:
    return ExtractedTable(
        id=table_id,
        extraction_run=run,
        container=container,
        source_reference=f"table-{table_id.int}",
        table_index=table_index,
        row_count=1,
        column_count=1,
        raw_text="needle",
    )


class _MigrationOperationRecorder:
    def __init__(self) -> None:
        self.calls: list[
            tuple[str, tuple[object, ...], dict[str, object]]
        ] = []

    def __getattr__(self, operation: str) -> Any:
        def record(
            *args: object,
            **kwargs: object,
        ) -> None:
            self.calls.append((operation, args, kwargs))

        return record
