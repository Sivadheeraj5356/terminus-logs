import numpy as np
from django.core.management.base import BaseCommand
from sklearn.datasets import make_classification

from monitoring.models import DriftEvaluation, InferenceRecord

FEATURE_NAMES = ("feature_0", "feature_1", "feature_2", "feature_3")


class Command(BaseCommand):
    help = "Seed deterministic inference batches"

    def handle(self, *args, **options):
        InferenceRecord.objects.all().delete()
        DriftEvaluation.objects.all().delete()

        reference, _ = make_classification(
            n_samples=240,
            n_features=4,
            n_informative=4,
            n_redundant=0,
            weights=[0.61, 0.39],
            class_sep=0.9,
            random_state=31415,
        )

        shifted, _ = make_classification(
            n_samples=57,
            n_features=4,
            n_informative=4,
            n_redundant=0,
            class_sep=0.7,
            shift=6.0,
            random_state=99,
        )
        shifted_rows = [
            InferenceRecord(
                id=index,
                batch_id="batch-shifted",
                features={
                    name: float(value)
                    for name, value in zip(FEATURE_NAMES, row, strict=True)
                },
            )
            for index, row in enumerate(shifted, start=101)
        ]
        InferenceRecord.objects.bulk_create(shifted_rows)

        rng = np.random.default_rng(2026)
        indices = rng.choice(len(reference), size=43, replace=True)
        stable_rows = [
            InferenceRecord(
                id=index,
                batch_id="batch-stable",
                features={
                    name: float(reference[source_index, feature_index])
                    for feature_index, name in enumerate(FEATURE_NAMES)
                },
            )
            for index, source_index in enumerate(indices, start=2001)
        ]
        InferenceRecord.objects.bulk_create(stable_rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(shifted_rows) + len(stable_rows)} inference records"
            )
        )
