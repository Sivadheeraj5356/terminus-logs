from django.db import models


class InferenceRecord(models.Model):
    batch_id = models.CharField(max_length=64, db_index=True)
    features = models.JSONField()

    class Meta:
        ordering = ["id"]


class DriftEvaluation(models.Model):
    batch_id = models.CharField(max_length=64)
    model_version = models.CharField(max_length=64)
    champion = models.CharField(max_length=64)
    training_oof_f1 = models.FloatField()
    training_calibrated_brier = models.FloatField()
    decision_threshold = models.FloatField()
    source_page_count = models.IntegerField()
    batch_source_digest = models.CharField(max_length=71)
    prediction_count = models.IntegerField()
    positive_predictions = models.IntegerField()
    mean_raw_positive_probability = models.FloatField()
    mean_positive_probability = models.FloatField()
    prediction_digest = models.CharField(max_length=71)
    prediction_psi = models.FloatField()
    prediction_drifted = models.BooleanField()
    mean_tree_disagreement = models.FloatField()
    disagreement_psi = models.FloatField()
    disagreement_drifted = models.BooleanField()
    correlation_deltas = models.JSONField()
    correlation_drift_score = models.FloatField()
    correlation_drifted = models.BooleanField()
    leaf_js_divergences = models.JSONField()
    leaf_drift_score = models.FloatField()
    leaf_drifted = models.BooleanField()
    path_sketch_digest = models.CharField(max_length=71)
    path_sketch_js = models.FloatField()
    path_sketch_drifted = models.BooleanField()
    drift_detected = models.BooleanField()
    drifted_features = models.JSONField()
    feature_stats = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
