from app.db.connection import db
from app.db.migrate import run_migrations
from app.db.registry import Knights


def main() -> None:
    run_migrations(db)

    # Example ORM usage
    Knights.insert({"name": "Arthur", "age": 40})
    print([item.q.name for item in Knights.filter().all()])


if __name__ == "__main__":
    main()
