"""Simple CLI worker that pulls queued ingestion jobs and runs them."""

import argparse

from sqlalchemy import select

from app.db import SessionLocal, init_db
from app.models.ingestion_job import IngestionJob
from app.models.manual_version import ManualVersion
from app.services.ingestion import IngestionService
from app.services.storage import StorageService


class IngestionWorker:
    def __init__(self) -> None:
        init_db()
        self.ingestion_service = IngestionService()
        self.storage_service = StorageService()

    def _claim_job(self, db, job_id: str | None) -> IngestionJob | None:
        if job_id:
            return db.get(IngestionJob, job_id)

        statement = (
            select(IngestionJob)
            .where(IngestionJob.status == "queued")
            .order_by(IngestionJob.created_at)
            .limit(1)
        )
        return db.scalar(statement)

    def process(self, job_id: str | None = None) -> IngestionJob | None:
        with SessionLocal() as db:
            job = self._claim_job(db, job_id)
            if job is None:
                return None

            job.status = "processing"
            job.detail = "Worker picked up the ingestion job."
            db.commit()

            version = db.get(ManualVersion, job.manual_version_id)
            if version is None or version.source_file_asset is None:
                job.status = "failed"
                job.detail = "Manual version or source file asset missing."
                db.commit()
                return job

            try:
                content = self.storage_service.download_bytes(version.source_file_asset.object_key)
            except Exception as exc:  # noqa: BLE001
                job.status = "failed"
                job.detail = f"Failed to download source file: {exc}"
                db.commit()
                return job

            self.ingestion_service.process_manual_version(
                db=db,
                version=version,
                job=job,
                filename=version.source_file_asset.original_filename,
                content=content,
            )
            db.commit()
            return job

    def process_all(self) -> list[IngestionJob]:
        jobs: list[IngestionJob] = []

        while True:
            job = self.process()
            if job is None:
                return jobs
            jobs.append(job)


def main() -> None:
    parser = argparse.ArgumentParser(description="Process a pending ingestion job.")
    parser.add_argument("--job-id", help="Optional job id to process explicitly.")
    parser.add_argument("--all", action="store_true", help="Process all queued ingestion jobs.")
    args = parser.parse_args()

    worker = IngestionWorker()
    if args.all:
        jobs = worker.process_all()
        if not jobs:
            print("No queued ingestion jobs found.")
            return
        for job in jobs:
            print(f"Ingestion job {job.id} finished with status {job.status}: {job.detail}")
        return

    job = worker.process(job_id=args.job_id)
    if job is None:
        print("No queued ingestion job found.")
        return

    print(f"Ingestion job {job.id} finished with status {job.status}: {job.detail}")


if __name__ == "__main__":
    main()
