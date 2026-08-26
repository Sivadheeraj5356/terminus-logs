# Why this trial exists

The deployment target can host either LibTorch through DJL's PyTorch engine or ONNX Runtime through DJL's ONNX engine. Both exported graphs came from the same fine-tuned MobileNetV3-Large checkpoint, but graph conversion, native kernels, tensor layout, and batching can still change numerical results. This experiment therefore treats the complete probability vector as evidence; agreement on one winning label alone is insufficient.

The supplied images are synthetic color controls rather than diagnostic specimens. They exercise tensor construction and engine equivalence without making a claim about clinical accuracy. The report is a portability result for the exported artifacts, not a validation of the underlying DIBaS classifier or dataset.
