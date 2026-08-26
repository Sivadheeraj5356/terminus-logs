from django.urls import path

from monitoring.views import (
    DriftEvaluationListCreateView,
    HealthView,
    InferenceBatchDetailView,
)

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path(
        "inference-batches/<str:batch_id>/",
        InferenceBatchDetailView.as_view(),
        name="inference-batch",
    ),
    path(
        "drift-evaluations/",
        DriftEvaluationListCreateView.as_view(),
        name="drift-evaluations",
    ),
]
