"""Re-score every document in Vespa with safety.is_adult() and fix the `adult` field where it changed.

    python update_adult.py                 # dry run: report what would change (default)
    python update_adult.py --apply         # send partial updates (only changed docs, only the adult field)
    python update_adult.py --mode cloud    # override VESPA_MODE from .env

Run it after editing safety.py, or after adding the `adult` field to an index that already has data.
Updates go both ways: newly flagged docs become adult=true, and docs no longer flagged become false.
"""

import argparse

from config import connect_vespa
from safety import is_adult

SCHEMA = "fineweb_schema"
CLUSTER = "fineweb_content"  # <content id="..."> in services.xml: '<app name>_content'


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write the changes (default is a dry run)")
    ap.add_argument("--mode", choices=["local", "cloud"], help="override VESPA_MODE from .env")
    ap.add_argument("--cluster", default=CLUSTER, help=f"content cluster name (default {CLUSTER})")
    ap.add_argument("--show", type=int, default=10, help="how many changed URLs to print per direction")
    args = ap.parse_args()

    app = connect_vespa(args.mode)

    total = flagged_now = 0
    changes: list[tuple[str, str, bool]] = []  # (doc id, url, new value)
    for slice_ in app.visit(content_cluster_name=args.cluster, schema=SCHEMA, wanted_document_count=200):
        for response in slice_:
            for doc in response.documents:
                f = doc.get("fields", {})
                total += 1
                new = is_adult(f.get("text", ""), f.get("url", ""))
                flagged_now += new
                if new != bool(f.get("adult", False)):  # a missing field counts as false
                    changes.append((doc["id"].split("::")[-1], f.get("url", ""), new))
        print(f"\rscanned {total} docs", end="", flush=True)
    print()

    to_true = [c for c in changes if c[2]]
    to_false = [c for c in changes if not c[2]]
    print(f"{total} docs scanned, {flagged_now} flagged adult ({100 * flagged_now / max(total, 1):.2f}%)")
    print(f"{len(changes)} need updating: {len(to_true)} -> adult=true, {len(to_false)} -> adult=false")
    for label, rows in (("-> true", to_true), ("-> false", to_false)):
        for _, url, _ in rows[: args.show]:
            print(f"  {label}  {url[:100]}")

    if not changes:
        print("nothing to update")
        return
    if not args.apply:
        print("dry run: nothing written. Re-run with --apply to update.")
        return

    failed = []

    def callback(response, doc_id):
        if not response.is_successful():
            failed.append(doc_id)
            print(f"update failed for {doc_id}: {response.get_json()}")

    # pyvespa wraps each field in {"assign": ...} itself for updates, so pass plain values
    app.feed_iterable(
        ({"id": doc_id, "fields": {"adult": value}} for doc_id, _, value in changes),
        schema=SCHEMA,
        operation_type="update",
        callback=callback,
    )
    print(f"updated {len(changes) - len(failed)} docs, {len(failed)} failed")


if __name__ == "__main__":
    main()
