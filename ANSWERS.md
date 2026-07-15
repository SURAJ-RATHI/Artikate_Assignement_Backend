# Section 1: Incident Investigation Log

I started by checking whether the deployment changed the database shape, because the view itself supposedly did not change. For this kind of regression I would first compare migrations, indexes, and dependency versions. A missing index can easily turn an 80 ms endpoint into a timeout, but the detail that only users with 200+ orders were affected made me suspicious of work growing per row.

The next thing I would check is query count with django-debug-toolbar or django-silk. I care about query count before looking at CPU because Django ORM lazy loading can hide the real issue. A loop that looks harmless can run one query for the page, then one query per order, then one query per line item.

In the reproduction here, the broken view loads 25 orders and then touches `order.customer`, `order.lines.all()`, and `line.product` inside Python loops. Django evaluates the base `QuerySet` lazily, then each relation access triggers more SQL because the relation cache is empty.

Profiler evidence from the included test fixture:

```text
broken view: 126 SQL queries for 25 orders
fixed view: 2 SQL queries for 25 orders
```

For 200 orders with multiple lines each, that shape gets bad quickly. The latency grows almost linearly with order count, which matches an N+1 query regression more than a single missing index. A missing index usually shows up as one or two slow queries. This showed up as many small queries.

The root cause category is N+1 query caused by Django ORM lazy loading. The fix is in `orders/views.py`.

`select_related("customer")` makes Django use a SQL join for the single-valued foreign key. The customer columns come back in the same query as the orders, and Django fills the related-object cache on each `Order`.

`prefetch_related(Prefetch("lines", queryset=OrderLine.objects.select_related("product")))` runs a second query for all order lines belonging to those orders. Django then stitches the lines back onto their parent orders in memory. Inside that prefetch query, `select_related("product")` joins product rows, so `line.product.sku` does not trigger another query.

I also added indexes on `(tenant, -created_at)` and `(tenant, status)`. They are not the main fix, but they are realistic for the endpoint: most dashboards filter by tenant and sort recent orders.

# Section 2: SIGKILL Behavior

If a Celery worker process is `SIGKILL`'d mid-task, Python does not run cleanup code. No `finally` block, no graceful exception handling, nothing. The broker semantics matter at that point.

This project sets `acks_late=True`, so Celery acknowledges the Redis message only after the task completes. It also sets `reject_on_worker_lost=True`, which prevents Celery from treating a lost worker as a successful task. With Redis, the task can be redelivered after the broker's visibility timeout path.

That gives at-least-once processing. It does not magically give exactly-once email delivery. If the provider accepted the email and the worker died before the DB row was updated, the retry may send again. The practical fix is an idempotency key passed to the provider, usually the `EmailJob.id`. I left the DB row and idempotency check in place because they are still useful even without provider support.

# Section 3: Tenant Isolation Notes

The tenant manager returns `queryset.none()` when no tenant is bound. I prefer that over returning every row because a missing tenant context should fail safe. It can be annoying in tests because you must explicitly set a tenant, but that annoyance is cheaper than a data leak.

The included `TenantScopedOrder` model uses:

```python
objects = TenantManager()
unscoped = models.Manager()
```

I included `unscoped` deliberately for internal maintenance and tests. In a stricter production codebase I would hide that behind a separate module or service and block it in application code review. Django always has escape hatches: raw SQL, `_base_manager`, a second manager, or direct database access. ORM-level scoping reduces accidental leaks; it is not a replacement for database row-level security in a high-risk multi-tenant system.

The middleware binds tenant context for the whole request from `X-Tenant-Slug` or subdomain and resets it in `finally`. The reset matters because workers and ASGI threads are reused.

The prompt asks about thread-local failure modes in async Django. Plain `threading.local()` is unsafe there because multiple async tasks can interleave on the same OS thread. One request can set tenant A, yield during an await, then another request on the same thread can set tenant B. When the first request resumes, it may read the wrong tenant. That is a nasty leak because it only appears under concurrency.

I used Python `contextvars.ContextVar` instead. `contextvars` flow with async task context, so each request keeps its own tenant even when execution hops across awaits. If this project had to support older sync-only code, I would still keep `contextvars`; it works fine in sync code and avoids having two context mechanisms.

# Section 4A: Django Admin Performance

A primary key index does not help much if the admin is doing expensive work around the table.

The first thing I would check is `list_display`. If it calls model methods that touch related objects, the changelist can become an N+1 query problem. For example, `customer_email()` calling `obj.customer.email` will query once per row unless the admin uses `list_select_related = ("customer",)`. For many-to-many or reverse relations, I would use `get_queryset()` and add `prefetch_related()`, but I would avoid showing large reverse counts per row unless the business really needs them.

Second, I would check search. `search_fields = ("name", "email")` on a 500k row table can be painful, especially with `icontains` on PostgreSQL. I would either narrow search to indexed fields like `=id` or `^email`, or add a trigram index and use a custom search path if partial text search is genuinely required. The admin default is convenient, but it can quietly become a table scan.

Third, I would check pagination count. Django admin's paginator calls `COUNT(*)`, and on large filtered tables that can be slow. I would set `show_full_result_count = False` on `ModelAdmin` and, if needed, use a custom paginator that avoids exact counts. The trade-off is that the admin no longer shows a perfect total. Usually that is fine for operations screens.

# Section 4B: Pagination Trade-offs

Offset pagination is easy for clients and developers. `?limit=50&offset=100` maps cleanly to SQL `LIMIT/OFFSET`, and it supports jumping to page 10. I would use it for admin-ish screens where users need page numbers and the dataset is not changing too fast.

At scale it has two problems. First, deep offsets get slower because the database still has to walk past the skipped rows before returning the next page. An index helps ordering, but it does not make `OFFSET 50000` free. Second, mobile infinite scroll behaves badly when rows are inserted or deleted between requests. A user can see duplicates or miss records because page boundaries move.

Cursor pagination is better for feeds and infinite scroll. The cursor usually encodes the last seen ordered values, like `(created_at, id)`, and the next query becomes `WHERE (created_at, id) < (...) ORDER BY created_at DESC, id DESC LIMIT 50`. That plays nicely with a composite index and handles new rows more predictably.

The downside is developer experience. Cursors are harder to debug, harder to jump around with, and require stable ordering. If the API sorts by a non-unique field, I would include `id` as a tie-breaker. For a mobile app scrolling through 10,000 records, I would choose cursor pagination. For a small back-office table where page numbers matter, offset is acceptable.
