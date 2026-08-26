import hashlib
import json
from pathlib import Path

from django.http import JsonResponse
from django.views import View
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from monitoring.models import DriftEvaluation, InferenceRecord
from monitoring.serializers import DriftEvaluationSerializer, InferenceRecordSerializer

CONFIG_PATH = Path("/app/config/repro_config.json")


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


class HealthView(View):
    def get(self, request):
        return JsonResponse({"status": "ok"})


class InferenceBatchDetailView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request, batch_id: str):
        cursor_text = request.query_params.get("cursor")
        cursor = None
        if cursor_text is not None:
            try:
                cursor = int(cursor_text)
            except ValueError:
                return Response(
                    {"detail": "cursor must be an integer"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        queryset = InferenceRecord.objects.filter(batch_id=batch_id).order_by("id")
        if cursor is not None:
            queryset = queryset.filter(id__gt=cursor)
        if not InferenceRecord.objects.filter(batch_id=batch_id).exists():
            return Response(
                {"detail": "batch not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        policy = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        page_size = int(policy["inference_page_size"])
        selected = list(queryset[: page_size + 1])
        has_more = len(selected) > page_size
        page_records = selected[:page_size]
        serialized = InferenceRecordSerializer(page_records, many=True).data
        records = list(reversed(serialized))
        next_cursor = int(page_records[-1].id) if has_more and page_records else None
        binding = {
            "batch_id": batch_id,
            "cursor": cursor,
            "records": records,
            "next_cursor": next_cursor,
        }
        payload = {
            **binding,
            "page_sha256": "sha256:"
            + hashlib.sha256(_canonical_bytes(binding)).hexdigest(),
        }
        return Response(payload)


class DriftEvaluationListCreateView(generics.ListCreateAPIView):
    authentication_classes = []
    permission_classes = []
    queryset = DriftEvaluation.objects.all()
    serializer_class = DriftEvaluationSerializer
    pagination_class = None
