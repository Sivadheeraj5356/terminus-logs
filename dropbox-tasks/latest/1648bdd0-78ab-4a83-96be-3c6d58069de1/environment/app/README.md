# Model release service

`/app/p/wf` packages a repeatedly cross-validated random-forest champion and submits Prefect-orchestrated drift evidence to a local Django REST API. The release includes calibrated probability, tree disagreement, pairwise dependence, per-tree leaf occupancy, and joint leaf-path sketch profiles; inference batches are cursor-paginated and page-digest bound. The training policy, bundle schema, CLI defaults, API contract, and orchestration names are under `/app/config/` and `/app/docs/`.

For manual API testing, run `python manage.py migrate --noinput`, `python manage.py seed_records`, and `python manage.py runserver 127.0.0.1:8000 --noreload` from `/app/django_api`.
