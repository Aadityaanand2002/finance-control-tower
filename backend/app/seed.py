"""Convenience entry: python -m app.seed from backend/ with PYTHONPATH=. """

from app.services.seed import seed_database

if __name__ == "__main__":
    print(seed_database())
