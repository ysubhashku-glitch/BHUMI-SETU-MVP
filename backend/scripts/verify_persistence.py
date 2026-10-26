"""
BhumiSetu Data Persistence Across Container Restart Verification Script.
Validates that persistent Docker named volumes (staging_pgdata and staging_miniodata)
actually preserve written state across container stop/start/restart cycles.

Usage:
    python -m scripts.verify_persistence seed
    # (operator / CI restarts containers: docker compose restart db minio app worker)
    python -m scripts.verify_persistence verify
"""
import sys
import os
import uuid
import hashlib
import logging
import argparse
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

# Ensure backend root is on sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from app.config import settings
from app.core.logging_config import setup_logging
from app.core.storage import get_document_storage
from app.models.organization import Organization
from app.models.parcel import Parcel

setup_logging(settings.ENVIRONMENT)
logger = logging.getLogger("bhumisetu.persistence_validator")

MARKER_BHUMI_ID = "BR-PERSISTENCE-CHECK-RESTART-001"
MARKER_ORG_SLUG = "org-persistence-check-restart"
MARKER_STORAGE_FILE = "persistence_verification_marker.txt"
MARKER_STORAGE_PAYLOAD = b"BHUMISETU_PERSISTENT_VOLUME_VERIFICATION_PAYLOAD_2026_OK\n"


def seed_persistence_marker() -> bool:
    """Writes identifiable test state to both PostgreSQL and MinIO."""
    logger.info("--- Seeding Persistence Verification State ---")

    # 1. Seed Database Record
    logger.info(f"Connecting to database: {settings.DATABASE_URL.split('@')[-1]}")
    engine = sa.create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Idempotently find or create test organization
        org = session.query(Organization).filter(Organization.slug == MARKER_ORG_SLUG).first()
        if not org:
            org = Organization(name="Persistence Verification Org", slug=MARKER_ORG_SLUG)
            session.add(org)
            session.flush()

        # Remove previous marker if present
        existing_parcel = session.query(Parcel).filter(Parcel.bhumi_id == MARKER_BHUMI_ID).first()
        if existing_parcel:
            session.delete(existing_parcel)
            session.flush()

        parcel = Parcel(
            org_id=org.org_id,
            bhumi_id=MARKER_BHUMI_ID,
            state_code="BR",
            district_name="Patna",
            subdistrict_anchal_name="Danapur",
            halka_number="01",
            mauza_village_name="Digha",
            census_village_code="245001",
            khata_number="999",
            plot_khesra_number="999",
            recorded_area_acres=10.50,
            land_nature="AGRICULTURAL_RAIYATI",
            authoritative_boundary="SRID=4326;POLYGON((85.10 25.60, 85.12 25.60, 85.12 25.62, 85.10 25.62, 85.10 25.60))"
        )
        session.add(parcel)
        session.commit()
        logger.info(f"[OK] Database marker seeded: {MARKER_BHUMI_ID} (10.50 acres)")
    except Exception as e:
        session.rollback()
        logger.error(f"[FAIL] Failed to seed database marker: {e}")
        return False
    finally:
        session.close()

    # 2. Seed Object Storage Object
    try:
        storage = get_document_storage()
        if hasattr(storage, "ensure_bucket_exists"):
            storage.ensure_bucket_exists()

        storage_res = storage.put(
            content=MARKER_STORAGE_PAYLOAD,
            destination_name=MARKER_STORAGE_FILE,
            mime_type="text/plain",
            metadata={"purpose": "restart_persistence_verification"}
        )
        logger.info(f"[OK] Storage marker seeded: {MARKER_STORAGE_FILE} (SHA-256: {storage_res.get('sha256_hash')})")
    except Exception as e:
        logger.error(f"[FAIL] Failed to seed storage marker: {e}")
        return False

    print("[SUCCESS] Persistence markers written to database and storage. Ready for container restart.")
    return True


def verify_persistence_marker() -> bool:
    """Verifies that the seeded state still exists after container restart, then cleans up."""
    logger.info("--- Verifying Persistence State After Restart ---")
    verified = True

    # 1. Verify Database Record
    logger.info(f"Querying database: {settings.DATABASE_URL.split('@')[-1]}")
    engine = sa.create_engine(settings.DATABASE_URL, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        parcel = session.query(Parcel).filter(Parcel.bhumi_id == MARKER_BHUMI_ID).first()
        if not parcel:
            logger.error(f"[FAIL] Database marker {MARKER_BHUMI_ID} WAS NOT FOUND after restart!")
            verified = False
        else:
            if parcel.recorded_area_acres != 10.50:
                logger.error(f"[FAIL] Database marker corrupted: expected 10.50 acres, got {parcel.recorded_area_acres}")
                verified = False
            else:
                logger.info(f"[OK] Database marker verified intact: {parcel.bhumi_id} ({parcel.recorded_area_acres} acres)")

            # Cleanup marker parcel
            session.delete(parcel)

            # Cleanup marker org
            org = session.query(Organization).filter(Organization.slug == MARKER_ORG_SLUG).first()
            if org:
                session.delete(org)
            session.commit()
            logger.info("[OK] Database marker cleaned up.")
    except Exception as e:
        session.rollback()
        logger.error(f"[FAIL] Database verification error: {e}")
        verified = False
    finally:
        session.close()

    # 2. Verify Storage Object
    try:
        storage = get_document_storage()
        expected_hash = hashlib.sha256(MARKER_STORAGE_PAYLOAD).hexdigest()
        target_ref = f"{expected_hash}.txt"

        if not storage.exists(target_ref):
            if storage.exists(MARKER_STORAGE_FILE):
                target_ref = MARKER_STORAGE_FILE
            else:
                logger.error(f"[FAIL] Storage marker {target_ref} WAS NOT FOUND after restart!")
                verified = False

        if verified:
            retrieved = storage.get(target_ref)
            actual_hash = hashlib.sha256(retrieved).hexdigest()
            if actual_hash != expected_hash:
                logger.error(f"[FAIL] Storage marker hash mismatch: expected {expected_hash}, got {actual_hash}")
                verified = False
            else:
                logger.info(f"[OK] Storage marker verified intact with matching SHA-256 digest ({actual_hash})")

            # Cleanup marker object
            storage.delete(target_ref)
            logger.info("[OK] Storage marker cleaned up.")
    except Exception as e:
        logger.error(f"[FAIL] Storage verification error: {e}")
        verified = False

    if verified:
        print("[SUCCESS] Data persistence verified across container restart! Both PostgreSQL and MinIO retained data.")
    else:
        print("[ERROR] Persistence verification FAILED: data did not survive container restart.")

    return verified


def main():
    parser = argparse.ArgumentParser(description="BhumiSetu Container Persistence Validator")
    parser.add_argument("action", choices=["seed", "verify"], help="seed marker before restart, or verify marker after restart")
    args = parser.parse_args()

    if args.action == "seed":
        success = seed_persistence_marker()
    elif args.action == "verify":
        success = verify_persistence_marker()
    else:
        parser.print_help()
        sys.exit(1)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
